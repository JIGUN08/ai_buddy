import os
import json
from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import PineconeApiException, IndexExistsError, NotFoundException
from openai import OpenAI, AuthenticationError
from typing import List, Dict, Union

# Pinecone SDK v3+에서 예외 클래스 이름이 변경되어, 
# 하위 호환성을 위해 'ApiException'으로 별칭(alias)을 지정합니다.
ApiException = PineconeApiException

# --- 전역 상수 설정 ---
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSION = 1024

# OpenAI 클라이언트 인스턴스 (지연 초기화될 변수)
client_openai = None

# Pinecone 클라이언트 및 인덱스 관리 변수
_pinecone_client = None
_pinecone_index_instance = None
_vector_db_enabled = False # 벡터 DB 기능 활성화 상태 플래그
_initialization_attempted = False # 초기화 시도 여부를 기록하는 새로운 플래그

# ----------------- 유틸리티 함수 -----------------

def _get_openai_client() -> OpenAI:
    """OpenAI 클라이언트를 지연 초기화합니다."""
    global client_openai
    if client_openai is None:
        try:
            client_openai = OpenAI()
        except AuthenticationError as e:
            # 환경 설정이 제대로 안 된 경우 (API 키 누락/무효)
            raise EnvironmentError("OPENAI_API_KEY 환경 변수가 설정되지 않았거나 유효하지 않습니다.") from e
    return client_openai

def _get_embedding(text: str) -> List[float]:
    """OpenAI 임베딩 모델을 사용하여 텍스트의 벡터를 생성합니다."""
    try:
        client = _get_openai_client()
        response = client.embeddings.create(
            input=[text],
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSION
        )
        return response.data[0].embedding
        
    except EnvironmentError:
        raise
    except Exception as e:
        raise Exception(f"OpenAI 임베딩 생성 중 오류 발생: {e}")


# ----------------- Pinecone 연결 및 관리 -----------------

def _initialize_pinecone():
    """
    Pinecone 클라이언트를 초기화하고 인덱스 객체에 연결합니다.
    (list_indexes() 오류를 우회하기 위해 describe_index_stats()로 연결을 테스트)
    """
    global _pinecone_client, _pinecone_index_instance, _vector_db_enabled, _initialization_attempted
    
    _initialization_attempted = True # 시도 시작

    # 환경 변수 체크
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX_NAME")
    
    is_key_set = bool(PINECONE_API_KEY)
    is_name_set = bool(index_name)

    print(f"--- [Pinecone Debug] API_KEY 설정됨: {is_key_set} ---")
    print(f"--- [Pinecone Debug] INDEX_NAME 설정됨: {is_name_set}, 값: {index_name} ---")

    if not is_key_set or not is_name_set:
        print("--- [경고] 필수 Pinecone 환경 변수 누락. 벡터 DB 기능 비활성화. ---")
        _vector_db_enabled = False
        return

    try:
        # 1. Pinecone 클라이언트 초기화 
        _pinecone_client = Pinecone(api_key=PINECONE_API_KEY)
        
        # 2. 인덱스 객체 생성 (존재 여부와 상관없이 시도)
        index = _pinecone_client.Index(index_name)
        
        # 3. 연결 테스트: describe_index_stats() 호출을 통해 연결 확인
        try:
            stats = index.describe_index_stats()
            # 통계 정보가 성공적으로 반환되면 인덱스가 존재하고 연결도 잘 된 것으로 간주
            print(f"Pinecone 인덱스 '{index_name}'이 존재하며 연결에 성공했습니다. 벡터 수: {stats.total_vector_count}")
        
        except NotFoundException:
            # 인덱스가 존재하지 않으면, 이 시점에서 생성
            print(f"Pinecone 인덱스 '{index_name}'가 존재하지 않아 새로 생성합니다.")
            
            # 인덱스 생성 (IndexExistsError를 방지하기 위해 create_index 호출)
            try:
                _pinecone_client.create_index(
                    name=index_name, 
                    dimension=EMBEDDING_DIMENSION, 
                    metric='cosine',
                    spec=ServerlessSpec(cloud='aws', region='us-west-2')
                )
            except IndexExistsError:
                # 매우 드물지만, 동시에 생성 시도가 발생했을 경우의 대비책
                print(f"인덱스 '{index_name}'가 이미 생성 중이거나 방금 생성되었습니다.")
                pass
            
            # 새로 생성된 인덱스 객체 다시 연결 (최신 상태 보장)
            index = _pinecone_client.Index(index_name)
            
        # 4. 인덱스 객체 최종 캐시 및 성공 상태 설정
        _pinecone_index_instance = index
        _vector_db_enabled = True # 성공적으로 초기화 및 인덱스 연결 완료
        print(f"--- [Pinecone Success] 벡터 DB (인덱스: {index_name}) 활성화 ---")


    except ApiException as e:
        print(f"--- Pinecone API 연결/인증 오류가 발생했습니다. 벡터 DB 비활성화: {e} ---")
        _vector_db_enabled = False 
    except Exception as e:
        # list_indexes()를 우회했으므로, 이 예외는 다른 일반 네트워크 오류일 가능성이 높음
        print(f"--- Pinecone 초기화 중 치명적인 오류가 발생했습니다. 벡터 DB 비활성화: {e} ---")
        _vector_db_enabled = False
        
        
def is_vector_db_enabled():
    """벡터 DB 사용 가능 여부 반환"""
    return _vector_db_enabled

def get_or_create_collection():
    """
    초기화된 Pinecone 인덱스 객체를 반환합니다. (지연 초기화 로직 적용)
    """
    global _initialization_attempted
    
    # 1. 초기화를 시도한 적이 없다면, 지금 시도합니다.
    if not _initialization_attempted:
        print("--- 벡터 DB 최초 접근 시도: Pinecone 지연 초기화 실행 ---")
        _initialize_pinecone()
    
    # 2. 초기화 결과에 따라 인덱스 객체를 반환합니다.
    if not is_vector_db_enabled():
        return None
        
    return _pinecone_index_instance

# ----------------- 벡터 DB 작업 -----------------

def upsert_message(pinecone_index_dummy, message_obj):
    """
    RDB ChatMessage 객체를 임베딩하여 Pinecone 인덱스에 저장(Upsert)합니다.
    """
    # 호출 시점에 get_or_create_collection()으로 인덱스를 새로 가져와야 지연 초기화가 작동합니다.
    pinecone_index = get_or_create_collection() 
    
    if pinecone_index is None:
        print("--- [경고] 벡터 DB 비활성화 상태로 upsert_message 스킵 ---")
        return
        
    try:
        user_identifier = str(message_obj.user.username) 
        message_id = str(message_obj.id)
        
        # 1. 임베딩 생성
        embedding = _get_embedding(message_obj.message)

        # 2. 메타데이터 구성
        metadata = {
            "text": message_obj.message,
            "speaker": "user" if message_obj.is_user else "ai",
            "user_id": user_identifier, 
            "timestamp": message_obj.timestamp.isoformat()
        }
        
        # 3. Pinecone에 Upsert
        pinecone_index.upsert(
            vectors=[{
                "id": message_id, 
                "values": embedding, 
                "metadata": metadata
            }]
        )
        print(f"--- 벡터 DB에 메시지 ID {message_id} 저장 완료 (Pinecone) ---")

    except EnvironmentError as e:
        print(f"--- 환경 설정 오류로 Upsert 실패: {e} ---")
        pass 
    except Exception as e:
        print(f"--- Pinecone Upsert 중 일반 오류 발생 (ID: {message_obj.id}): {e} ---")
        pass


def query_similar_messages(
    pinecone_index_dummy, query: str, user_identifier: str, n_results: int = 5
) -> Dict[str, Union[List[str], List[Dict]]]:
    """
    Pinecone에서 쿼리와 관련된 문서를 검색하고 ChatService의 예상 형식으로 반환합니다.
    """
    # 호출 시점에 get_or_create_collection()으로 인덱스를 새로 가져와야 지연 초기화가 작동합니다.
    pinecone_index = get_or_create_collection() 
    
    if pinecone_index is None:
        print("--- [경고] 벡터 DB 비활성화 상태로 query_similar_messages 스킵 ---")
        return {"documents": [], "metadatas": []}
        
    try:
        print(f"벡터 DB에서 관련 문서를 검색합니다 (User: {user_identifier})...")
        
        # 1. 쿼리 임베딩 생성
        query_embedding = _get_embedding(query)

        # 2. Pinecone 인덱스 쿼리
        results = pinecone_index.query(
            vector=query_embedding,
            top_k=n_results,
            filter={"user_id": user_identifier}, 
            include_metadata=True
        )

        retrieved_docs = []
        retrieved_metadatas = []
        
        for match in results.matches:
            document_content = match.metadata.get('text', '문서 내용 없음')
            
            metadata = {
                'speaker': match.metadata.get('speaker', 'unknown'),
                'user_id': match.metadata.get('user_id'), 
                'timestamp': match.metadata.get('timestamp')
            }
            
            retrieved_docs.append(document_content)
            retrieved_metadatas.append(metadata)

        print(f"--- Pinecone 검색 결과: {len(retrieved_docs)}개 문서 ---")
        
        return {
            "documents": retrieved_docs,
            "metadatas": retrieved_metadatas
        }
        
    except EnvironmentError as e:
        print(f"--- 환경 설정 오류로 Pinecone 문서 검색 실패: {e} ---")
        return {"documents": [], "metadatas": []}
    except Exception as e:
        print(f"--- Pinecone 문서 검색 중 오류가 발생했습니다: {e} ---")
        return {"documents": [], "metadatas": []}
