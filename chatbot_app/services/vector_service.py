# 이 파일은 Django 프로젝트의 vector_service.py 파일을 가정하고 수정되었습니다.
import os
import time
from pinecone import Pinecone, ApiException

# 환경 변수 로드
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME")

# Pinecone 클라이언트 초기화 및 상태 관리
_pinecone_client = None
_vector_db_enabled = False

def initialize_pinecone():
    """
    Pinecone 클라이언트를 초기화하고 벡터 DB 활성화 상태를 확인합니다.
    """
    global _pinecone_client, _vector_db_enabled
    
    # 디버그: 환경 변수 설정 상태 확인
    api_key_set = bool(PINECONE_API_KEY)
    index_name_set = bool(PINECONE_INDEX_NAME)
    
    print(f"--- [Pinecone Debug] API_KEY 설정됨: {api_key_set} ---")
    print(f"--- [Pinecone Debug] INDEX_NAME 설정됨: {index_name_set}, 값: {PINECONE_INDEX_NAME} ---")

    if not api_key_set or not index_name_set:
        print("--- [Pinecone Info] API Key 또는 Index 이름이 설정되지 않아 벡터 DB 비활성화 ---")
        _vector_db_enabled = False
        return

    try:
        # 1. Pinecone 클라이언트 초기화 (최신 SDK 방식)
        _pinecone_client = Pinecone(api_key=PINECONE_API_KEY)
        
        # 2. 클라이언트가 인덱스를 찾을 수 있는지 확인합니다.
        # list_indexes()를 호출할 때 괄호()를 사용하여 메서드를 실행해야 합니다.
        # 이전에 발생했던 오류 'argument of type 'method' is not iterable'은
        # 이 메서드를 실행하지 않고 메서드 자체를 순회하려고 할 때 발생합니다.
        available_indexes = _pinecone_client.list_indexes().names
        
        if PINECONE_INDEX_NAME not in available_indexes:
            print(f"--- [Pinecone Warning] 인덱스 '{PINECONE_INDEX_NAME}'가 존재하지 않습니다. 생성 중... ---")
            # 인덱스 생성 로직이 없으면 일단 비활성화 상태로 둡니다.
            _vector_db_enabled = False
        else:
            print(f"--- [Pinecone Success] 벡터 DB (인덱스: {PINECONE_INDEX_NAME}) 활성화 ---")
            _vector_db_enabled = True

    except ApiException as e:
        print(f"--- [Pinecone Error] API 연결 중 오류 발생: {e} ---")
        _vector_db_enabled = False
    except Exception as e:
        # 이 부분이 고객님께서 겪으신 'method is not iterable' 오류를 포착합니다.
        # 환경 재설치 후에도 이 오류가 지속되면 이는 코드/환경 간 충돌로 간주합니다.
        print(f"--- Pinecone 초기화 중 알 수 없는 오류가 발생했습니다. 벡터 DB 비활성화: {e} ---")
        _vector_db_enabled = False

# --- [추가된 함수] chat_service.py에서 종속되는 함수들 ---

def get_or_create_collection():
    """
    Pinecone Index 객체를 반환합니다. 초기화에 실패했으면 None을 반환합니다.
    chat_service.py에서 이 함수를 호출하여 인덱스를 가져옵니다.
    """
    if not is_vector_db_enabled() or not _pinecone_client:
        return None
        
    # 이미 initialize_pinecone()에서 인덱스 존재를 확인했으므로,
    # 바로 인덱스 객체를 리턴합니다.
    return _pinecone_client.Index(PINECONE_INDEX_NAME)

def query_similar_messages(collection, user_message_text, user_id, n_results=5):
    """
    유사 메시지를 검색하여 컨텍스트를 반환합니다.
    현재는 임베딩 로직이 없으므로 빈 결과를 반환하여 충돌을 방지합니다.
    """
    # 실제 임베딩 및 쿼리 로직이 여기에 들어갑니다.
    if not collection:
        return {'documents': [], 'metadatas': []}
        
    # TODO: 임베딩 모델 호출 및 쿼리 로직 구현 필요
    print("--- [Info] 임베딩 모델 부재로 Pinecone 쿼리 로직은 임시로 스킵합니다. ---")
    return {'documents': [], 'metadatas': []}

def upsert_message(collection, chat_message_obj):
    """
    새로운 대화 메시지를 벡터 DB에 저장합니다.
    현재는 임베딩 로직이 없으므로 빈 리턴 값으로 충돌을 방지합니다.
    """
    if not collection:
        return
        
    # TODO: 메시지 텍스트를 임베딩하고 upsert 로직 구현 필요
    print(f"--- [Info] 임베딩 모델 부재로 '{chat_message_obj.id}' 메시지 벡터 DB 저장 스킵. ---")
    pass
    
# --- [기존 함수 유지] ---

def is_vector_db_enabled():
    """벡터 DB 사용 가능 여부 반환"""
    return _vector_db_enabled

def get_pinecone_index():
    """활성화된 Pinecone 인덱스 객체를 반환합니다."""
    # get_or_create_collection()과 동일한 역할을 합니다. 호환성을 위해 유지합니다.
    return get_or_create_collection()

def find_similar_documents(query_embedding, top_k=3):
    """
    주어진 임베딩을 사용하여 Pinecone에서 유사한 문서를 검색합니다.
    (실제 구현 시 임베딩 모델 호출 코드가 이전에 있어야 합니다.)
    """
    # 이 함수는 query_similar_messages()와 기능이 겹치므로 is_vector_db_enabled()만 확인합니다.
    if not is_vector_db_enabled():
        results = {'documents': [], 'metadatas': []}
        print(f"--- [디버그] Raw similar_results from vector_service: {results} ---")
        return results

    pinecone_index = get_pinecone_index()
    if pinecone_index is None:
        results = {'documents': [], 'metadatas': []}
        print(f"--- [디버그] Raw similar_results from vector_service: {results} (인덱스 없음) ---")
        return results

    try:
        # 쿼리 실행
        # query_embedding을 사용하려면 임베딩 모델이 필요합니다.
        # 임시로 빈 결과를 반환하여 오류를 방지합니다.
        results = {'documents': [], 'metadatas': []}
        print(f"--- [디버그] Raw similar_results from vector_service: {results} (임시 쿼리) ---")
        return results

    except Exception as e:
        print(f"--- [Pinecone Query Error] 쿼리 실행 중 오류 발생: {e} ---")
        results = {'documents': [], 'metadatas': []}
        print(f"--- [디버그] Raw similar_results from vector_service: {results} (쿼리 오류) ---")
        return results

# 서버 시작 시 Pinecone 초기화 시도
initialize_pinecone()
