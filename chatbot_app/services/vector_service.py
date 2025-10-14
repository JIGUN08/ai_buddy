import os
import json
from pinecone import Pinecone, ServerlessSpec # 기존 import는 유지
from pinecone.exceptions import ApiException # ApiException을 정확한 위치에서 가져옵니다.
from openai import OpenAI, AuthenticationError # 필요한 모듈 임포트
from typing import List, Dict, Union

# --- 전역 변수 설정 ---
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSION = 1024

# OpenAI 클라이언트 인스턴스 (지연 초기화될 변수)
client_openai = None

# Pinecone 인덱스 인스턴스 캐시 변수
# None: 초기화되지 않음, False: 초기화 시도 중 오류 발생/환경 변수 누락
pinecone_index_instance = None 

# ----------------- 유틸리티 함수 -----------------

def _get_openai_client() -> OpenAI:
    """
    OpenAI 클라이언트를 지연 초기화합니다.
    (파일 로드 시 status 1 오류 방지)
    """
    global client_openai
    if client_openai is None:
        try:
            # 환경 변수가 없으면 여기서 AuthenticationError 발생
            client_openai = OpenAI()
        except AuthenticationError as e:
            # 환경 변수 오류를 명확한 EnvironmentError로 전환하여 처리
            raise EnvironmentError("OPENAI_API_KEY 환경 변수가 설정되지 않았거나 유효하지 않아 OpenAI 클라이언트 초기화에 실패했습니다.") from e
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
        # _get_openai_client에서 발생한 환경 변수 오류를 상위로 전파
        raise
    except Exception as e:
        # OpenAI API 호출 중 발생하는 기타 오류
        raise Exception(f"OpenAI 임베딩 생성 중 오류 발생: {e}")


# ----------------- Pinecone 연결 및 관리 -----------------

def get_or_create_collection():
    """
    Pinecone 클라이언트를 초기화하고 인덱스 객체를 반환합니다.
    환경 변수 누락 또는 연결 오류 시 None을 반환하고 그 결과를 캐시합니다.
    """
    global pinecone_index_instance

    # 1. 캐시 확인
    if pinecone_index_instance is not None:
        return None if pinecone_index_instance is False else pinecone_index_instance
    
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    
    # 2. 환경 변수 체크 (배포 시작을 막지 않고, 기능만 비활성화)
    if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
        print("--- [경고] 필수 Pinecone 환경 변수(API_KEY, INDEX_NAME)가 설정되지 않았습니다. 벡터 DB 기능이 비활성화됩니다. ---")
        pinecone_index_instance = False # 실패 기록 캐시
        return None

    try:
        # 3. Pinecone 클라이언트 초기화
        pc = Pinecone(api_key=PINECONE_API_KEY)
        
        # 4. 인덱스 존재 여부 확인 및 생성
        if PINECONE_INDEX_NAME not in pc.list_indexes().names:
            print(f"Pinecone 인덱스 '{PINECONE_INDEX_NAME}'가 존재하지 않아 새로 생성합니다.")
            pc.create_index(
                name=PINECONE_INDEX_NAME, 
                dimension=EMBEDDING_DIMENSION, 
                metric='cosine',
                spec=ServerlessSpec(cloud='aws', region='us-west-2')
            )

        # 5. 인덱스 연결 및 캐시 저장
        index = pc.Index(PINECONE_INDEX_NAME)
        pinecone_index_instance = index
        return index

    except ApiException as e:
        print(f"--- Pinecone API 연결/인증 오류이 발생했습니다. 벡터 DB 비활성화: {e} ---")
        pinecone_index_instance = False 
        return None
    except Exception as e:
        print(f"--- Pinecone 초기화 중 알 수 없는 오류가 발생했습니다. 벡터 DB 비활성화: {e} ---")
        pinecone_index_instance = False 
        return None

# ----------------- 벡터 DB 작업 -----------------

def upsert_message(pinecone_index, message_obj):
    """
    RDB ChatMessage 객체를 임베딩하여 Pinecone 인덱스에 저장(Upsert)합니다.
    """
    if pinecone_index is None:
        print("--- Pinecone 인덱스가 설정되지 않아 upsert를 건너킵니다. ---")
        return
        
    try:
        user_id = str(message_obj.user.id)
        message_id = str(message_obj.id)
        
        # 1. 임베딩 생성
        embedding = _get_embedding(message_obj.message)

        # 2. 메타데이터 구성
        metadata = {
            "text": message_obj.message,
            "speaker": "user" if message_obj.is_user else "ai",
            "user_id": user_id, 
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
    pinecone_index, query: str, user_id: int, n_results: int = 5
) -> Dict[str, Union[List[str], List[Dict]]]:
    """
    Pinecone에서 쿼리와 관련된 문서를 검색하고 ChatService의 예상 형식으로 반환합니다.
    """
    if pinecone_index is None:
        print("--- Pinecone 인덱스가 설정되지 않아 문서 검색을 건너뛰고 빈 결과를 반환합니다. ---")
        return {"documents": [], "metadatas": []}
        
    try:
        print(f"'{PINECONE_INDEX_NAME}' 인덱스에서 관련 문서를 검색합니다...")
        
        # 1. 쿼리 임베딩 생성
        query_embedding = _get_embedding(query)

        # 2. Pinecone 인덱스 쿼리
        results = pinecone_index.query(
            vector=query_embedding,
            top_k=n_results,
            filter={"user_id": str(user_id)}, # user_id는 upsert 시 문자열로 저장
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
