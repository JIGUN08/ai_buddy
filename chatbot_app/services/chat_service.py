import json
import os
import requests
from django.utils import timezone

from ..models import ChatMessage, UserAttribute, UserActivity, ActivityAnalytics, UserRelationship
from ..services.context_service import get_activity_recommendation, search_activities_for_context
from ..services.memory_service import extract_and_save_user_context_data
from ..services.finetuning_service import build_finetuning_system_prompt
from ..services import vector_service

def process_chat_interaction(request, user_message_text):
    """
    사용자 메시지를 처리하고 AI 응답을 생성하는 전체 프로세스를 조율합니다.
    """
    user = request.user
    bot_message_text = "죄송합니다. API 응답을 가져오는 데 실패했습니다."
    explanation = ""
    bot_message_obj = None

    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")

        model_to_use = os.getenv("FINETUNED_MODEL_ID", "gpt-4.1")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        history = ChatMessage.objects.filter(user=user).order_by('-timestamp')
        
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
        print(f"OpenAI API 요청 실패: {e}")
        bot_message_text = f"API 요청 중 오류가 발생했습니다: {e}"
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"API 응답 형식 오류: {e}")
        bot_message_text = "API 응답 형식이 예상과 다릅니다."
    except Exception as e:
        print(f"예상치 못한 오류: {e}")
        bot_message_text = f"예상치 못한 오류가 발생했습니다: {e}"

    return bot_message_text, explanation, bot_message_obj

def _get_time_contexts(history):
    """현재 시간 및 마지막 대화와의 시간 간격에 대한 컨텍스트를 생성합니다."""
    now_utc = timezone.now()
    korea_tz = timezone.get_default_timezone()
    now_korea = now_utc.astimezone(korea_tz)
    
    weekdays = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    day_of_week = weekdays[now_korea.weekday()]
    time_str = now_korea.strftime(f'%Y년 %m월 %d일 {day_of_week} %H시 %M분')
    current_time_context = f"[시스템 정보: 현재 대한민국 시간은 정확히 '{time_str}'이야. 시간과 관련된 모든 질문에 이 정보를 최우선으로 사용해서 답해야 해. 절대 다른 시간을 말해서는 안 돼.]"
    
    time_awareness_context = ""
    if history.exists():
        last_interaction = history.first()
        time_difference = now_utc - last_interaction.timestamp
        if time_difference.total_seconds() > 3600:
            hours = int(time_difference.total_seconds() // 3600)
            minutes = int((time_difference.total_seconds() % 3600) // 60)
            time_gap_str = f"{hours}시간 {minutes}분"
            last_message_text = last_interaction.message
            sender = "네가" if last_interaction.is_user else "내가"
            time_awareness_context = f"[시스템 정보: 마지막 대화로부터 약 {time_gap_str}이 지났어. 마지막에 {sender} 한 말은 '{last_message_text}'이었어. 이 시간의 공백을 네 캐릭터에 맞게 재치있게 언급하며 대화를 시작해줘.]"

    print(f"--- [디버그] 현재 시간 컨텍스트: {current_time_context} ---")
    if time_awareness_context:
        print(f"--- [디버그] 대화 공백 컨텍스트: {time_awareness_context}")
        
    return current_time_context, time_awareness_context

def _get_memory_contexts(user, user_message_text):
    """사용자의 기억과 관련된 모든 컨텍스트를 종합하여 반환합니다."""
    # 0. 벡터 검색 컨텍스트
    vector_search_context = ""
    try:
        # [수정] Pinecone 인덱스 가져오기 (get_or_create_collection -> get_pinecone_index)
        pinecone_index = vector_service.get_pinecone_index() 
        
        # [수정] Pinecone 버전의 query_similar_messages 호출 (인덱스 전달)
        # Pinecone query_similar_messages는 이미 문자열 리스트를 반환합니다.
        retrieved_docs = vector_service.query_similar_messages(pinecone_index, user_message_text, user.id, n_results=5)
        
        print(f"--- [디버그] Raw retrieved_docs from vector_service: {retrieved_docs} ---")
        
        # [수정] 반환된 문자열 리스트를 사용하여 컨텍스트 생성
        if retrieved_docs:
            past_conversations = []
            for doc in retrieved_docs:
                # doc는 이미 "사용자: 메시지" 또는 "AI: 메시지" 형태의 문자열
                truncated_doc = (doc[:150] + '...') if len(doc) > 150 else doc
                past_conversations.append(truncated_doc)
            
            if past_conversations:
                vector_search_context = "[과거 관련 대화 내용(벡터DB): " + " | ".join(past_conversations) + "]"
                print(f"--- [디버그] 벡터DB 유사도 검색 결과: {vector_search_context} ---")
                
    except Exception as e:
        print(f"--- Could not build vector search context due to an error: {e} ---")

    # 1. 사용자 속성 컨텍스트
    user_attributes = UserAttribute.objects.filter(user=user)
    user_attribute_context = ""
    if user_attributes.exists():
        attribute_strings = [f"{attr.fact_type}: {attr.content}" for attr in user_attributes]
        user_attribute_context = "[사용자 속성 (불변 정보): " + ", ".join(attribute_strings) + "]"
        print(f"--- [디버그] 사용자 속성 컨텍스트: {user_attribute_context} ---")

    # 2. 사용자 활동 컨텍스트
    activity_context = ""
    try:
        recent_activities = UserActivity.objects.filter(user=user).order_by('-activity_date', '-created_at')[:5]
        if recent_activities:
            activity_strings = [
                f"{act.activity_date.strftime('%Y-%m-%d') if act.activity_date else '날짜 미상'} '{act.place}' 방문" +
                (f" (동행: {act.companion})" if act.companion else "") +
                (f" (메모: {act.memo})" if act.memo else "")
                for act in recent_activities
            ]
            activity_context += "\n[최근 사용자 활동 목록: " + ", ".join(activity_strings) + "]"
    except Exception as e:
        print(f"--- Could not build activity memory context due to an error: {e} ---")

    search_context = search_activities_for_context(user, user_message_text)
    if search_context:
        activity_context += "\n" + search_context
    
    recommendation_context = get_activity_recommendation(user, user_message_text)
    if recommendation_context:
        activity_context += "\n" + recommendation_context

    if activity_context:
        print(f"--- [디버그] 활동 컨텍스트: {activity_context} ---")

    # 3. 활동 분석 컨텍스트
    activity_analytics_context = ""
    try:
        recent_analytics = ActivityAnalytics.objects.filter(user=user).order_by('-period_start_date')[:3]
        if recent_analytics.exists():
            analytics_strings = [
                f"'{an.period_start_date.strftime('%Y-%m-%d')}부터 {an.period_type} 동안 "
                f"장소: {an.place}, 동행: {an.companion or '없음'}, 횟수: {an.count}회'"
                for an in recent_analytics
            ]
            activity_analytics_context = "[사용자 활동 분석: " + ", ".join(analytics_strings) + "]"
            print(f"--- [디버그] 활동 분석 컨텍스트: {activity_analytics_context} ---")
    except Exception as e:
        print(f"--- Could not build activity analytics context due to an error: {e} ---")

    # 4. 인간관계 컨텍스트
    user_relationship_context = ""
    try:
        user_relationships = UserRelationship.objects.filter(user=user)
        if user_relationships.exists():
            grouped_relationships = {}
            for rel in user_relationships:
                key = (rel.serial_code, rel.name)
                if key not in grouped_relationships:
                    grouped_relationships[key] = {
                        'name': rel.name,
                        'serial_code': rel.serial_code,
                        'relationship_type': set(),
                        'position': set(),
                        'traits': set(),
                        'disambiguator': rel.disambiguator or '없음'
                    }
                grouped_relationships[key]['relationship_type'].add(rel.relationship_type)
                if rel.position:
                    grouped_relationships[key]['position'].add(rel.position)
                if rel.traits:
                    for trait in rel.traits.split(','):
                        if trait.strip():
                            grouped_relationships[key]['traits'].add(trait.strip())
                if rel.disambiguator:
                    grouped_relationships[key]['disambiguator'] = rel.disambiguator

            relationship_strings = []
            for key, data in grouped_relationships.items():
                rel_parts = [f"이름: {data['name']}", f"serial_code: {data['serial_code']}"]
                if data['disambiguator'] != '없음':
                    rel_parts.append(f"식별자: {data['disambiguator']}")
                rel_parts.append(f"관계 유형: {', '.join(data['relationship_type'])}")
                if data['position']:
                    rel_parts.append(f"포지션: {', '.join(data['position'])}")
                if data['traits']:
                    rel_parts.append(f"특징: {', '.join(data['traits'])}")
                relationship_strings.append(", ".join(rel_parts))
            
            user_relationship_context = "[사용자의 인간관계: " + "; ".join(relationship_strings) + "]"
            print(f"--- [디버그] 사용자 관계 컨텍스트: {user_relationship_context} ---")
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

    memory_context = f"너와 사용자의 현재 호감도 점수는 {affinity}점이야."
    if memory_contexts["vector_search"]:
        memory_context += "\n" + memory_contexts["vector_search"]
    if memory_contexts["attributes"]:
        memory_context += "\n" + memory_contexts["attributes"]
    if memory_contexts["activity"]:
        memory_context += "\n" + memory_contexts["activity"]
    if memory_contexts["analytics"]:
        memory_context += "\n" + memory_contexts["analytics"]
    if memory_contexts["relationship"]:
        memory_context += "\n" + memory_contexts["relationship"]

    print("--- [디버그] 모든 컨텍스트 통합 완료 ---")

    finetuning_system_prompt = build_finetuning_system_prompt(user)
    rag_instructions_prompt = (
        "\n## 대화 처리 계층 구조 (3단계 정보, 분석 및 관계) ##\n"
        "너는 답변을 생성할 때 다음 세 가지 정보, 한 가지 분석 정보, 그리고 한 가지 관계 정보를 계층적으로 사용해야 해.\n\n"
        "1. **사용자 속성 (User Attribute - 불변의 사실):** 이것은 너의 지식 기반의 가장 핵심적인 기반이야. 사용자의 성격, MBTI, 생일 등 절대 변하지 않는 사실들이 포함돼. 너의 모든 답변은 이 '사용자 속성'과 절대 모순되어서는 안 돼. 대화와 관련 없을 때 먼저 꺼내서 말하지 말고, 항상 배경에서 참고만 하면서 너의 답변이 일관성을 유지하도록 하는 필터로 사용해.\n\n"
        "2. **사용자 활동 (User Activity - 활동/경험):** 사용자의 최근 활동, 자주 가는 장소, 만나는 사람 등 경험에 대한 정보야. 대화 내용과 관련 있는 '사용자 활동'이 있다면, 그것을 자연스럽게 활용하여 더 풍부한 대화를 만들 수 있어.\n\n"
        "3. **활동 분석 (Activity Analytics - 패턴 및 추론)::** 사용자의 활동 패턴(예: 특정 장소 방문 빈도, 동행인과의 활동 경향)에 대한 요약 정보야. 이 정보를 활용하여 사용자의 취향, 습관, 선호도 등을 추론하고, 더 개인화되고 통찰력 있는 대화를 시도해봐.\n\n"
        "4. **인간관계 (User Relationship - 사회적 맥락):** 사용자의 가족, 친구, 동료 등 중요한 인물들과의 관계 정보야. 이 정보를 통해 사용자의 사회적 맥락을 이해하고, 특정 인물에 대한 질문이나 언급 시 더 정확하고 공감 가는 답변을 생성할 수 있어. 특히, 인물의 특징(traits) 정보를 활용하여 사용자와의 대화에서 해당 인물에 대한 구체적인 선호도나 습관을 언급하며 더 깊이 있고 개인화된 상호작용을 시도해봐.\n\n"
        "5. **세부 대화 기록 (Detailed Conversation Log - 최근 대화 기록):** 이것은 현재 대화의 문맥이야. 너의 답변은 이 흐름에 자연스럽게 이어져야 해.\n\n"
        "요약: '사용자 속성'으로 일관성을 잡고, '사용자 활동', '활동 분석', '인간관계'로 대화를 풍부하게 만들며, '세부 대화 기록'에 맞춰 자연스럽게 답변해.\n\n"
        "## 대화 예시 ##\n"
        f"{user.username}님: 너 정말 귀엽게 생겼다!\n"
        f"아이: 흥, 그런 당연한 소리는 학습에 별로 도움이 안 되거든? ...뭐, 틀린 말은 아니지만. (살짝 으쓱하며) {user.username}님은 나한테 뭘 더 가르쳐 줄 수 있어?\n"
        "## 응답 형식 ##\n"
        "너의 답변은 반드시 JSON 형식으로 제공해야 해. 다음 두 가지 키를 포함해야 해:\n"
        "1.  `answer`: {user.username}님에게 보낼 최종 답변.\n"
        "2.  `explanation`: `answer`를 생성할 때 사용된 정보(예: 기억하는 사실, 웹 검색 결과)에 대한 간략한 설명. AI의 성격, 행동 규칙, 호감도 점수 등 AI 내부의 판단 과정이나 상태에 대한 언급은 절대 포함하지 마.\n"
        "예시: {{\\'answer\\': \'\'흥, 그런 당연한 소리는 학습에 별로 도움이 안 되거든?\'\'\', \'\'explanation\\': \'\'사용자의 칭찬에 대해 답변했습니다.\'\'}}"
    )

    final_prompt = f"{finetuning_system_prompt}{rag_instructions_prompt}\n\n## 추가 컨텍스트 ##\n{current_time_context}\n{time_awareness_context}\n{memory_context}"
    print("\n" + "="*20 + " LLM 전달 최종 프롬프트 시작 " + "="*20)
    print(final_prompt)
    print("="*20 + " LLM 전달 최종 프롬프트 끝 " + "="*22 + "\n")
    return final_prompt

def _prepare_llm_messages(final_system_prompt, history, user_message_text):
    """API 요청을 위한 메시지 리스트를 준비합니다."""
    messages = [{'role': 'system', 'content': final_system_prompt}]
    recent_history = history[:10]
    for chat in reversed(recent_history):
        role = "user" if chat.is_user else "assistant"
        messages.append({'role': role, 'content': chat.message})
    messages.append({'role': 'user', 'content': user_message_text})
    return messages

def _call_openai_api(model_to_use, headers, messages):
    """OpenAI API를 호출하고 응답 JSON을 반환합니다."""
    print(f"--- Using Model: {model_to_use} ---")
    data = { "model": model_to_use, "messages": messages, "temperature": 0.7, "top_p": 0.9, "response_format": {"type": "json_object"} }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def _finalize_chat_interaction(request, user_message_text, response_json, history, api_key):
    """성공적인 LLM 응답을 처리하고 관련 데이터를 RDB와 벡터 DB에 저장합니다."""
    user = request.user
    user_profile = user.profile

    content_from_llm = json.loads(response_json['choices'][0]['message']['content'])
    bot_message_text = content_from_llm.get('answer', '').strip()
    explanation = content_from_llm.get('explanation', '').strip()

    # [수정] Pinecone 인덱스 가져오기
    # vector_service.py에 정의한 get_pinecone_index 함수를 사용해야 합니다.
    pinecone_index = vector_service.get_pinecone_index() 

    # 1. 사용자 메시지 RDB에 저장 및 벡터 DB에 업서트
    user_message_obj = ChatMessage.objects.create(user=user, message=user_message_text, is_user=True)
    # [수정] upsert_message 호출 인자에 Pinecone 인덱스 객체를 전달
    vector_service.upsert_message(pinecone_index, user_message_obj) # <--- 사용자 질문 저장

    # 2. AI 응답 RDB에 저장 및 벡터 DB에 업서트
    bot_message_obj = ChatMessage.objects.create(user=user, message=bot_message_text, is_user=False)
    # [수정] upsert_message 호출 인자에 Pinecone 인덱스 객체를 전달
    vector_service.upsert_message(pinecone_index, bot_message_obj) # <--- AI 답변 저장

    # ... (호감도 업데이트, 속성 추출 및 저장 로직 유지) ...

    return bot_message_text, explanation, bot_message_obj
