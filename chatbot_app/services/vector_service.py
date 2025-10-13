import os
from pinecone import Pinecone, ServerlessSpec # Pinecone 관련 import
from openai import OpenAI # OpenAI 클라이언트 사용
from typing import List, Dict, Optional
from datetime import datetime

# --- 환경 변수 정의 ---
# Render에서 설정한 환경 변수를 사용합니다.
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT") # 서버리스에서는 사용되지 않을 수 있지만, 안전을 위해 유지
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
INDEX_DIMENSION = 1024 # text-embedding-3-large의 1024차원
EMBEDDING_MODEL = "text-embedding-3-large"

# OpenAI 클라이언트 초기화 (OpenAI API 키는 환경 변수에서 자동 로드됨)
try:
    # 이전에 load_dotenv()를 제거했으므로, Render에서 OPENAI_API_KEY를 주입받음
    client_openai = OpenAI()
except Exception as e:
    # API 키가 없으면 여기서 오류가 발생할 수 있습니다.
    print(f"--- [OpenAI Error] OpenAI 클라이언트 초기화 실패: {e} ---")
    client_openai = None # 실패 시 None으로 설정

def get_pinecone_index():
    """Pinecone 클라이언트를 초기화하고 인덱스를 반환하는 함수"""
    if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
        # 이전에 발생했던 EnvironmentError를 대신하여 명확한 오류 반환
        raise EnvironmentError("필수 Pinecone 환경 변수(KEY, NAME)가 설정되지 않았습니다.")

    try:
        # 1. 클라이언트 초기화 (환경 변수를 사용하거나, 직접 키를 전달)
        # 서버리스 환경에서는 environment 대신 cloud와 region이 중요합니다.
        # 기존 환경 변수를 유지하는 것이 Render 설정과 일치할 가능성이 높습니다.
        pc = Pinecone(api_key=PINECONE_API_KEY) 
        
        # 2. 인덱스 존재 확인 및 연결
        # Pinecone은 ChromaDB처럼 get_or_create_collection을 직접 지원하지 않으므로,
        # 인덱스 생성은 배포 전에 수동으로 해야 합니다.
        
        # 인덱스가 존재하는지 확인하는 로직은 생략하고 바로 연결합니다.
        return pc.Index(PINECONE_INDEX_NAME)
    
    except Exception as e:
        print(f"--- [Pinecone Error] 인덱스 연결 중 오류 발생: {e} ---")
        raise

def upsert_message(index_instance, chat_message):
    """
    ChatMessage 객체를 받아 Pinecone 인덱스에 벡터화하여 저장(upsert)합니다.
    (ChromaDB의 upsert_message 함수 대체)
    """
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
        
        # 2. 메타데이터 준비
        metadata = {
            "speaker": "user" if chat_message.is_user else "ai",
            "user_id": chat_message.user.id,
            "timestamp": chat_message.timestamp.isoformat(),
            "text": message_text # 검색 후 텍스트를 바로 사용하기 위해 필수로 저장
        }
        
        # 3. Pinecone에 Upsert
        print(f"--- [Pinecone Debug] Upserting message ID: {chat_message.id}, User ID: {chat_message.user.id}... ---")
        index_instance.upsert(
            vectors=[
                (
                    str(chat_message.id), 
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
    (ChromaDB의 query_similar_messages 함수 대체)
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
        # filter={"user_id": user_id} 메타데이터 필터링 적용
        results = index_instance.query(
            vector=query_embedding,
            top_k=n_results,
            filter={"user_id": user_id},
            include_metadata=True
        )

        retrieved_docs = []
        for match in results.matches:
            # Pinecone은 유사도(score)를 반환하며, 1에 가까울수록 유사합니다.
            # ChromaDB의 거리(distance)와는 의미가 반대입니다.
            # 따라서, 거리 임계값(distance_threshold)을 유사도 임계값으로 재해석합니다.
            
            # 유사도(score)가 임계값보다 높을 경우에만 포함
            # 기존 ChromaDB 코드에서 distance_threshold가 0.8이었으므로,
            # Pinecone 유사도에서는 score >= 0.8로 해석하는 것이 일반적입니다.
            if match.score >= distance_threshold:
                # 메타데이터에서 원본 텍스트를 추출
                document_content = match.metadata.get('text', '문서 내용 없음')
                retrieved_docs.append(document_content)
                
        print(f"--- [Pinecone Debug] {len(retrieved_docs)}개의 관련 문서를 찾았습니다. ---")
        return retrieved_docs

    except Exception as e:
        # 이전에 발생했던 401 오류가 여기서 발생할 수 있습니다.
        print(f"--- [Pinecone] Error querying collection: {e} ---")
        return []
