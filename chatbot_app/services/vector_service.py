# chatbot_app/services/vector_service.py

import os
from pinecone import Pinecone
from openai import OpenAI
from typing import List
from datetime import datetime

# --- 환경 변수 정의 ---
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
INDEX_DIMENSION = 1024 # text-embedding-3-large의 1024차원
EMBEDDING_MODEL = "text-embedding-3-large"

try:
    client_openai = OpenAI()
except Exception as e:
    print(f"--- [OpenAI Error] OpenAI 클라이언트 초기화 실패: {e} ---")
    client_openai = None

def get_pinecone_index():
    """Pinecone 클라이언트를 초기화하고 인덱스 객체를 반환하는 함수"""
    if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
        raise EnvironmentError("필수 Pinecone 환경 변수(KEY, NAME)가 설정되지 않았습니다.")

    try:
        pc = Pinecone(api_key=PINECONE_API_KEY) 
        # 인덱스 존재 여부를 확인하고 연결하는 로직이 필요하지만, 여기서는 바로 연결합니다.
        return pc.Index(PINECONE_INDEX_NAME)
    
    except Exception as e:
        print(f"--- [Pinecone Error] 인덱스 연결 중 오류 발생: {e} ---")
        raise

def upsert_message(index_instance, chat_message):
    """ChatMessage 객체를 받아 Pinecone 인덱스에 벡터화하여 저장(upsert)합니다."""
    if not client_openai:
        print("--- [Upsert Error] OpenAI 클라이언트가 초기화되지 않아 건너뜁니다. ---")
        return

    try:
        message_text = chat_message.message
        
        # 1. 메시지 임베딩 생성
        response = client_openai.embeddings.create(
            input=[message_text],
            model=EMBEDDING_MODEL,
            dimensions=INDEX_DIMENSION
        )
        new_embedding = response.data[0].embedding
        
        # 2. 메타데이터 준비 (RAG를 위해 원본 텍스트를 저장)
        metadata = {
            "speaker": "user" if chat_message.is_user else "ai",
            "user_id": chat_message.user.id, # user.id를 사용
            "timestamp": chat_message.timestamp.isoformat(),
            "text": message_text 
        }
        
        # 3. Pinecone에 Upsert
        index_instance.upsert(
            vectors=[
                (
                    str(chat_message.id),  # ID는 고유해야 합니다.
                    new_embedding, 
                    metadata
                )
            ]
        )
        print(f"--- [Pinecone Debug] Successfully upserted message ID: {chat_message.id} ---")

    except Exception as e:
        print(f"--- [Pinecone] Error upserting message ID {chat_message.id}: {e} ---")

def query_similar_messages(index_instance, query_text, user_id, n_results=5, distance_threshold=0.8) -> List[str]:
    """
    주어진 텍스트와 가장 유사한 대화 내용을 Pinecone에서 검색합니다.
    검색된 'text' 메타데이터 필드를 문자열 리스트로 반환합니다.
    """
    if not client_openai:
        print("--- [Query Error] OpenAI 클라이언트가 초기화되지 않아 검색을 건너뜁니다. ---")
        return []

    try:
        # 1. 쿼리 텍스트 임베딩 생성
        response = client_openai.embeddings.create(
            input=[query_text],
            model=EMBEDDING_MODEL,
            dimensions=INDEX_DIMENSION
        )
        query_embedding = response.data[0].embedding

        # 2. Pinecone 쿼리 실행
        # filter={"user_id": user_id} 필터링 적용
        results = index_instance.query(
            vector=query_embedding,
            top_k=n_results,
            filter={"user_id": user_id},
            include_metadata=True
        )

        retrieved_docs = []
        for match in results.matches:
            # 유사도(score)가 임계값보다 높을 경우에만 포함 (Pinecone: 1에 가까울수록 유사)
            if match.score >= distance_threshold:
                # 메타데이터에서 원본 텍스트를 추출
                document_content = match.metadata.get('text', '문서 내용 없음')
                retrieved_docs.append(document_content)
                
        print(f"--- [Pinecone Debug] {len(retrieved_docs)}개의 관련 문서를 찾았습니다. ---")
        return retrieved_docs

    except Exception as e:
        print(f"--- [Pinecone] Error querying index: {e} ---")
        return []
