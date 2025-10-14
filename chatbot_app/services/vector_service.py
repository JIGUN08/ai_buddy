import os
import json
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI
from typing import List, Dict, Union

# Pinecone 환경 변수
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# OpenAI 클라이언트 및 임베딩 모델 초기화
# Pinecone 벡터 생성을 위해 사용됩니다.
client_openai = OpenAI()
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSION = 1024


def get_or_create_collection():
    """Pinecone 클라이언트를 초기화하고 인덱스 객체를 반환합니다."""
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    # Pinecone 환경 변수 체크 (Render 등 클라우드 환경에서 사용)
    if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
        # 이 에러는 환경 변수가 없을 때 발생하므로, 서비스 구동 전에 확인되어야 합니다.
        raise EnvironmentError("필수 Pinecone 환경 변수(API_KEY, INDEX_NAME)가 설정되지 않았습니다.")

    try:
        # 1. Pinecone 클라이언트 초기화
        pc = Pinecone(api_key=PINECONE_API_KEY)
        
        # 2. 인덱스 존재 여부 확인 및 생성
        if PINECONE_INDEX_NAME not in pc.list_indexes().names:
            print(f"Pinecone 인덱스 '{PINECONE_INDEX_NAME}'가 존재하지 않아 새로 생성합니다.")
            # ServerlessSpec은 최신 권장 설정입니다.
            pc.create_index(
                name=PINECONE_INDEX_NAME, 
                dimension=EMBEDDING_DIMENSION, 
                metric='cosine',
                spec=ServerlessSpec(cloud='aws', region='us-west-2')
            )

        # 3. 인덱스 연결
        return pc.Index(PINECONE_INDEX_NAME)

    except Exception as e:
        print(f"--- Pinecone 초기화 중 오류이 발생했습니다: {e} ---")
        raise


def _get_embedding(text: str) -> List[float]:
    """OpenAI 임베딩 모델을 사용하여 텍스트의 벡터를 생성합니다."""
    response = client_openai.embeddings.create(
        input=[text],
        model=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIMENSION
    )
    return response.data[0].embedding


def upsert_message(pinecone_index, message_obj):
    """
    RDB ChatMessage 객체를 임베딩하여 Pinecone 인덱스에 저장(Upsert)합니다.
    """
    try:
        user_id = str(message_obj.user.id)
        message_id = str(message_obj.id)
        
        # 1. 임베딩 생성
        embedding = _get_embedding(message_obj.message)
        
        # 2. 메타데이터 구성
        metadata = {
            "text": message_obj.message,
            "speaker": "user" if message_obj.is_user else "ai",
            "user_id": user_id,  # 필터링을 위한 user_id (Pinecone은 문자열 필터를 권장)
            "timestamp": message_obj.timestamp.isoformat()
        }
        
        # 3. Pinecone에 Upsert
        # ID는 메시지 객체의 ID를 사용합니다.
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


def query_similar_messages(
    pinecone_index, query: str, user_id: int, n_results: int = 5
) -> Dict[str, Union[List[str], List[Dict]]]:
    """
    Pinecone에서 쿼리와 관련된 문서를 검색하고 ChatService의 예상 형식으로 반환합니다.
    """
    try:
        print(f"'{PINECONE_INDEX_NAME}' 인덱스에서 관련 문서를 검색합니다...")
        
        # 1. 쿼리 임베딩 생성
        query_embedding = _get_embedding(query)

        # 2. Pinecone 인덱스 쿼리
        # filter={"user_id": user_id}를 사용하여 특정 사용자의 기록만 검색
        # user_id는 upsert 시 문자열로 저장되므로 str()로 변환
        results = pinecone_index.query(
            vector=query_embedding,
            top_k=n_results,
            filter={"user_id": str(user_id)}, 
            include_metadata=True
        )

        retrieved_docs = []
        retrieved_metadatas = []
        
        for match in results.matches:
            # 문서 내용 추출 및 ChatService의 예상 구조에 맞게 메타데이터 재구성
            document_content = match.metadata.get('text', '문서 내용 없음')
            
            # ChatService에서 'speaker' 키를 활용하므로 메타데이터에 포함합니다.
            metadata = {
                'speaker': match.metadata.get('speaker', 'unknown'),
                'user_id': match.metadata.get('user_id'),
                'timestamp': match.metadata.get('timestamp')
            }
            
            retrieved_docs.append(document_content)
            retrieved_metadatas.append(metadata)

        print(f"--- Pinecone 검색 결과: {len(retrieved_docs)}개 문서 ---")
        
        # ChatService에서 ChromaDB 형식을 예상하므로 그에 맞춰 반환
        return {
            "documents": retrieved_docs,
            "metadatas": retrieved_metadatas
        }
        
    except Exception as e:
        print(f"--- Pinecone 문서 검색 중 오류가 발생했습니다: {e} ---")
        # 오류 시 chat_service가 안전하게 처리할 수 있도록 빈 형식 반환
        return {"documents": [], "metadatas": []}
