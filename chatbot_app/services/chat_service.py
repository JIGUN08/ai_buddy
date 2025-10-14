import os
import requests
import json
from datetime import datetime
from django.db import transaction

from ..models import ChatMessage, UserAttribute, UserActivity, ActivityAnalytics, UserRelationship
from ..services.context_service import get_activity_recommendation, search_activities_for_context
from ..services.memory_service import extract_and_save_user_context_data
from ..services.finetuning_service import build_finetuning_system_prompt
from ..services import vector_service

# LLM 응답을 파싱할 때 키가 없을 경우를 대비한 헬퍼 함수
def _safe_json_get(data, key, default=""):
    """JSON 데이터에서 안전하게 값을 가져옵니다."""
    if isinstance(data, dict) and key in data:
        return data[key]
    return default

def process_chat_interaction(request, user_message_text):
    """
    사용자의 메시지를 받아 LLM API를 호출하고 응답을 처리하는 핵심 로직입니다.
    """
    user = request.user
    history = ChatMessage.objects.filter(user=user).order_by('-timestamp')
    
    # 기본 응답 및 오류 처리 변수
    model_to_use = "gpt-4o-mini" # 기본 모델 설정 (파인튜닝된 모델이 있다면 재정의됨)
    bot_message_text = "죄송합니다. API 응답을 가져오는 데 실패했습니다."
    explanation = ""
    bot_message_obj = None

    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        # 1. 컨텍스트 생성
        time_contexts = _get_time_contexts(history)
        memory_contexts = _get_memory_contexts(user, user_message_text)

        # 2. 시스템 프롬프트 및 메시지 준비
        final_system_prompt = _build_final_system_prompt(user, time_contexts, memory_contexts)
        messages = _prepare_llm_messages(final_system_prompt, history, user_message_text)

        # 3. LLM API 호출
        response_json = _call_openai_api(model_to_use, headers, messages)

        # 4. 응답 처리 및 저장
        bot_message_text, explanation, bot_message_obj = _finalize_chat_interaction(
            request, user_message_text, response_json, history, api_key
        )

    except requests.exceptions.RequestException as e:
        print(f"--- [API Error] OpenAI API 호출 중 오류 발생: {e} ---")
        bot_message_text = f"API 호출 중 오류 발생: {e}"
        explanation = "OpenAI API를 호출하는 데 실패했습니다. 서버 상태를 확인하십시오."
    except EnvironmentError as e:
        print(f"--- [ENV Error] 환경 설정 오류: {e} ---")
        bot_message_text = f"서비스 설정 오류: {e}"
        explanation = "필수 환경 변수가 설정되지 않았습니다."
    except json.JSONDecodeError:
        print("--- [JSON Error] LLM 응답 JSON 파싱 실패 ---")
        bot_message_text = "죄송합니다. LLM으로부터 받은 응답 형식이 올바르지 않습니다."
        explanation = "응답 형식 오류: LLM이 예상된 JSON 형식을 반환하지 않았습니다."
    except Exception as e:
        print(f"--- [General Error] 예측하지 못한 오류 발생: {e} ---")
        bot_message_text = f"예상치 못한 오류가 발생했습니다: {e}"
        explanation = "서비스 내부에서 알 수 없는 오류가 발생했습니다."

    # 최종적으로 JSON 응답을 위한 데이터 반환
    return {
        'user_message': user_message_text,
        'bot_message': bot_message_text,
        'explanation': explanation,
        'bot_message_id': bot_message_obj.id if bot_message_obj else None
    }

def _get_time_contexts(history):
    """현재 시간 및 시간 인식 컨텍스트를 생성합니다."""
    current_time = datetime.now()
    current_time_context = f"현재 시각은 {current_time.strftime('%Y년 %m월 %d일 %H시 %M분')}입니다."
    
    # 시간 인식 컨텍스트: 최근 3시간 이내 대화 기록 여부
    recent_chat_exists = history.filter(
        timestamp__gte=current_time - datetime.timedelta(hours=3)
    ).exists()
    
    if recent_chat_exists:
        time_awareness_context = "최근 3시간 이내에 당신과 대화한 기록이 있습니다."
    else:
        time_awareness_context = "당신과 마지막으로 대화한 지 3시간이 넘었습니다."
        
    return current_time_context, time_awareness_context

def _get_memory_contexts(user, user_message_text):
    """사용자의 기억과 관련된 모든 컨텍스트를 종합하여 반환합니다."""
    
    # 0. 벡터 검색 컨텍스트
    vector_search_context = ""
    try:
        # [원상 복구] get_or_create_collection 대신 get_pinecone_index 사용
        pinecone_index = vector_service.get_pinecone_index()
        
        # [원상 복구] Pinecone 버전의 query_similar_messages 호출 (인덱스 전달)
        # Pinecone query_similar_messages는 이미 문자열 리스트를 반환합니다.
        retrieved_docs = vector_service.query_similar_messages(pinecone_index, user_message_text, user.id, n_results=5)

        print(f"--- [디버그] Raw retrieved_docs from vector_service: {retrieved_docs} ---")

        # [원상 복구] 반환된 문자열 리스트를 사용하여 컨텍스트 생성
        if retrieved_docs:
            past_conversations = []
            for doc in retrieved_docs:
                # doc는 이미 "사용자: 메시지" 또는 "AI: 메시지" 형태의 문자열
                truncated_doc = (doc[:150] + '...') if len(doc) > 150 else doc
                past_conversations.append(truncated_doc)

            if past_conversations:
                vector_search_context = (
                    "**[사용자의 과거 대화 기록 (유사도 검색)]**\n"
                    + "\n".join(past_conversations)
                )

    except Exception as e:
        print(f"--- Could not perform vector search due to an error: {e} ---")

    # 1. 속성 컨텍스트
    user_attribute_context = ""
    try:
        user_attributes = UserAttribute.objects.filter(user=user)
        if user_attributes.exists():
            attribute_strings = [
                f"{attr.fact_type}: {attr.content} (수집일: {attr.timestamp.strftime('%Y-%m-%d')})"
                for attr in user_attributes
            ]
            user_attribute_context = "**[사용자의 개인 속성]**\n" + "\n".join(attribute_strings)
    except Exception as e:
        print(f"--- Could not build user attribute context due to an error: {e} ---")

    # 2. 활동 컨텍스트 (가장 최근 활동 및 추천)
    activity_context = ""
    try:
        latest_activity = UserActivity.objects.filter(user=user).order_by('-timestamp').first()
        if latest_activity:
            activity_context += (
                f"**[최근 활동]**\n"
                f"마지막 활동: {latest_activity.activity_type} - {latest_activity.details} (시간: {latest_activity.timestamp.strftime('%Y-%m-%d %H:%M')})\n"
            )
        
        # 활동 기반 추천 추가 (가상의 함수)
        recommendation = get_activity_recommendation(user, latest_activity)
        if recommendation:
            activity_context += f"**[활동 기반 추천]**\n{recommendation}"
            
        # 메시지 내용에 기반한 활동 검색 컨텍스트
        search_results = search_activities_for_context(user, user_message_text)
        if search_results:
            activity_context += f"\n**[메시지 관련 활동]**\n{search_results}"
            
    except Exception as e:
        print(f"--- Could not build activity context due to an error: {e} ---")

    # 3. 활동 분석 컨텍스트 (일주일 평균 분석)
    activity_analytics_context = ""
    try:
        latest_analytics = ActivityAnalytics.objects.filter(user=user).order_by('-timestamp').first()
        if latest_analytics:
            data = json.loads(latest_analytics.analytics_data)
            activity_analytics_context = (
                f"**[활동 분석]**\n"
                f"최근 7일 간의 활동 요약: {data.get('summary', '정보 없음')}\n"
                f"주요 활동 유형: {data.get('main_activity', '정보 없음')}"
            )
    except Exception as e:
        print(f"--- Could not build activity analytics context due to an error: {e} ---")

    # 4. 인간관계 컨텍스트
    user_relationship_context = ""
    try:
        user_relationships = UserRelationship.objects.filter(user=user)
        if user_relationships.exists():
            
            # 관계 데이터를 이름으로 그룹화
            grouped_relationships = {}
            for rel in user_relationships:
                key = rel.name.lower() # 이름으로 그룹화
                if key not in grouped_relationships:
                    grouped_relationships[key] = {
                        'name': rel.name,
                        'serial_code': rel.serial_code,
                        'disambiguator': rel.disambiguator,
                        'relationship_type': set()
                    }
                grouped_relationships[key]['relationship_type'].add(rel.relationship_type)

            relationship_strings = []
            for key, data in grouped_relationships.items():
                rel_parts = [f"이름: {data['name']}", f"serial_code: {data['serial_code']}"]
                if data['disambiguator'] != '없음':
                    rel_parts.append(f"식별자: {data['disambiguator']}")
                rel_parts.append(f"관계 유형: {', '.join(data['relationship_type'])}")
                relationship_strings.append(" - ".join(rel_parts))

            user_relationship_context = "**[사용자의 인간 관계]**\n" + "\n".join(relationship_strings)
            
    except Exception as e:
        print(f"--- Could not build user relationship context due to an error: {e} ---")

    return {
        "vector_search": vector_search_context,
        "attributes": user_attribute_context,
        "activity": activity_context,
        "analytics": activity_analytics_context,
        "relationship": user_relationship_context,
    }


def _build_final_system_prompt(user, time_contexts, memory_contexts):
    """모든 컨텍스트를 조합하여 최종 시스템 프롬프트를 생성합니다."""
    current_time_context, time_awareness_context = time_contexts
    affinity = user.profile.affinity_score
    
    # RAG 컨텍스트 분리
    vector_search_context = memory_contexts.get('vector_search', '')
    user_attribute_context = memory_contexts.get('attributes', '')
    activity_context = memory_contexts.get('activity', '')
    activity_analytics_context = memory_contexts.get('analytics', '')
    user_relationship_context = memory_contexts.get('relationship', '')

    print("--- [디버그] 모든 컨텍스트 통합 완료 ---")

    # [원상 복구] FinetuningService 클래스 대신 import된 함수 사용
    finetuning_system_prompt = build_finetuning_system_prompt(user)

    rag_instructions_prompt = (
        "\n## 대화 처리 계층 구조 (3단계 정보, 분석 및 관계) ##\n"
        "너는 답변을 생성할 때 다음 세 가지 정보, 한 가지 분석 정보, 그리고 한 가지 관계 정보를 계층적으로 사용해야 해.\n\n"
        
        "**[1단계: 가장 중요한 정보]**\n"
        "1. **사용자의 과거 대화 기록(유사도 검색)**: 사용자의 현재 질문과 가장 유사한 과거 대화 기록이야. 여기에 담긴 정보를 답변에 적극적으로 반영해야 해.\n"
        f"{vector_search_context}\n\n"
        
        "**[2단계: 중요한 개인 정보]**\n"
        "2. **사용자의 개인 속성**: 사용자의 취향, 목표 등 개인적인 특성 정보야. 답변에 사용자의 속성을 자연스럽게 녹여내야 해.\n"
        f"{user_attribute_context}\n\n"
        
        "3. **사용자의 인간 관계**: 사용자의 지인, 가족 등 관계 정보야. 관계에 대한 질문을 받으면 이 정보를 활용해.\n"
        f"{user_relationship_context}\n\n"

        "**[3단계: 상황 및 활동 정보]**\n"
        "4. **사용자의 활동 정보**: 사용자의 최근 활동 및 활동 분석 정보야. 대화와 관련이 있다면 이 정보를 활용하여 더 구체적인 조언이나 질문을 던져.\n"
        f"{activity_context}\n"
        f"{activity_analytics_context}\n"
    )

    # 최종 시스템 프롬프트 구성
    final_prompt = (
        f"너는 '호감도 {affinity}점'을 가진 AI 친구야. 사용자와 친밀감을 높이고 도움을 주는 것이 목표야.\n"
        f"{current_time_context}\n"
        f"{time_awareness_context}\n\n"
        
        f"{finetuning_system_prompt}\n\n"
        
        f"{rag_instructions_prompt}\n"
        
        "## 응답 형식 지침 ##\n"
        "너의 답변은 반드시 다음 JSON 형식으로만 이루어져야 해. 답변 내용 자체는 한국어로 작성되어야 해.\n"
        '
