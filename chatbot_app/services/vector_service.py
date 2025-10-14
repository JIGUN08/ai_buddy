import os
import json
from pinecone import Pinecone, ServerlessSpec, ApiException # ApiException 임포트 추가
from openai import OpenAI, AuthenticationError 
from typing import List, Dict, Union

# Pinecone 환경 변수 (전역 변수로 유지하되, 함수 내에서 안전하게 처리)
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# 임베딩 모델 설정
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSION = 1024

# OpenAI 클라이언트 인스턴스를 저장할 변수 (지연 초기화)
client_openai = None

def _get_openai_client() -> OpenAI:
    """
    OpenAI 클라이언트를 지연 초기화합니다.
    API 키가 환경 변수에 설정되어 있어야 합니다.
    """
    global client_openai
    if client_openai is None:
        try:
            # OpenAI()는 OPENAI_API_KEY 환경 변수를 자동으로 찾습니다.
            client_openai = OpenAI()
        except AuthenticationError as e:
            # API 키가 없으면 AuthenticationError가 발생합니다.
            raise EnvironmentError("OPENAI_API_KEY 환경 변수가 설정되지 않았거나 유효하지 않아 OpenAI 클라이언트 초기화에 실패했습니다.") from e
    return client_openai

def get_or_create_collection():
    """
    Pinecone 클라이언트를 초기화하고 인덱스 객체를 반환합니다.
    환경 변수 누락 시 치명적인 오류 대신 None을 반환하여 Gunicorn 시작 실패를 방지합니다.
    """
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    
    # 1. Pinecone 환경 변수 체크 (치명적 오류 대신 None 반환)
    if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
        print("--- [경고] 필수 Pinecone 환경 변수(API_KEY 또는 INDEX_NAME)가 설정되지 않았습니다. 벡터 DB 기능이 비활성화됩니다. ---")
        return None

    try:
        # 2. Pinecone 클라이언트 초기화
        pc = Pinecone(api_key=PINECONE_API_KEY)
        
        # 3. 인덱스 존재 여부 확인 및 생성
        if PINECONE_INDEX_NAME not in pc.list_indexes().names:
            print(f"Pinecone 인덱스 '{PINECONE_INDEX_NAME}'가 존재하지 않아 새로 생성합니다.")
            pc.create_index(
                name=PINECONE_INDEX_NAME, 
                dimension=EMBEDDING_DIMENSION, 
                metric='cosine',
                spec=ServerlessSpec(cloud='aws', region='us-west-2')
            )

        # 4. 인덱스 연결
        return pc.Index(PINECONE_INDEX_NAME)

    except ApiException as e:
        # API 키가 유효하지 않거나 연결 문제가 있을 경우
        print(f"--- Pinecone API 연결/인증 오류이 발생했습니다. 벡터 DB 비활성화: {e} ---")
        return None
    except Exception as e:
        # 기타 모든 예외를 잡고 None 반환하여 프로세스 종료를 방지
        print(f"--- Pinecone 초기화 중 알 수 없는 오류이 발생했습니다: {e} ---")
        return None


def _get_embedding(text: str) -> List[float]:
    """OpenAI 임베딩 모델을 사용하여 텍스트의 벡터를 생성합니다."""
    try:
        # 클라이언트를 사용하기 직전에 초기화를 시도합니다.
        client = _get_openai_client()
        
        response = client.embeddings.create(
            input=[text],
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSION
        )
        return response.data[0].embedding
        
    except EnvironmentError as e:
        # 환경 변수 누락으로 인한 초기화 실패를 명확히 알립니다.
        print(f"--- 임베딩 생성 실패: {e} ---")
        # 임베딩 실패 시 None 대신 예외를 다시 발생시켜 upsert/query 로직이 실패하도록 유도
        raise
    except Exception as e:
        print(f"--- OpenAI API 호출 중 오류 발생: {e} ---")
        raise


def upsert_message(pinecone_index, message_obj):
    """
    RDB ChatMessage 객체를 임베딩하여 Pinecone 인덱스에 저장(Upsert)합니다.
    """
    # Pinecone 인덱스가 초기화되지 않은 경우 (None) 작업을 건너뜁니다.
    if pinecone_index is None:
        print("--- Pinecone 인덱스가 설정되지 않아 upsert를 건너뜁니다. ---")
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

    except Exception as e:
        print(f"--- Pinecone Upsert 오류 (ID: {message_obj.id}): {e} ---")
        # 벡터 관련 오류는 전체 응답을 실패시키지 않도록 하되, 로그를 남깁니다.
        pass


def query_similar_messages(
    pinecone_index, query: str, user_id: int, n_results: int = 5
) -> Dict[str, Union[List[str], List[Dict]]]:
    """
    Pinecone에서 쿼리와 관련된 문서를 검색합니다.
    """
    # Pinecone 인덱스가 초기화되지 않은 경우 (None) 빈 결과를 반환합니다.
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
            filter={"user_id": str(user_id)}, 
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
        # OpenAI 클라이언트 초기화 오류 시 처리
        print(f"--- 환경 설정 오류로 Pinecone 문서 검색 실패: {e} ---")
        return {"documents": [], "metadatas": []}
    except Exception as e:
        print(f"--- Pinecone 문서 검색 중 오류가 발생했습니다: {e} ---")
        return {"documents": [], "metadatas": []}
