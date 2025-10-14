import os
import json
from pinecone import Pinecone, ServerlessSpec # 필요한 모듈 임포트
from pinecone.exceptions import PineconeApiException # 최신 Pinecone SDK용 예외
from openai import OpenAI, AuthenticationError # 필요한 모듈 임포트
from typing import List, Dict, Union

# Pinecone SDK v3+에서 예외 클래스 이름이 변경되어, 
# 하위 호환성을 위해 'ApiException'으로 별칭(alias)을 지정합니다.
ApiException = PineconeApiException 

# --- 전역 상수 설정 ---
# PINECONE_INDEX_NAME은 이제 get_or_create_collection() 내부에서 읽습니다.
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
    """
    global client_openai
    if client_openai is None:
        try:
            client_openai = OpenAI()
        except AuthenticationError as e:
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
        raise
    except Exception as e:
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
    
    # 2. 환경 변수를 함수 내부에서 다시 읽어와서 확실하게 체크합니다.
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX_NAME")
    
    # 3. 환경 변수 체크 및 디버깅 로그 출력
    is_key_set = bool(PINECONE_API_KEY)
    is_name_set = bool(index_name)

    print(f"--- [Pinecone Debug] API_KEY 설정됨: {is_key_set} ---")
    print(f"--- [Pinecone Debug] INDEX_NAME 설정됨: {is_name_set}, 값: {index_name} ---")

    if not is_key_set or not is_name_set:
        print("--- [경고] 필수 Pinecone 환경 변수(API_KEY 또는 INDEX_NAME) 중 하나가 누락되었습니다. 벡터 DB 기능이 비활성화됩니다. ---")
        pinecone_index_instance = False # 실패 기록 캐시
        return None

    try:
        # 4. Pinecone 클라이언트 초기화
        pc = Pinecone(api_key=PINECONE_API_KEY)

        # 5. 인덱스 존재 여부 확인 및 생성
        
        # **[수정] 'argument of type 'method' is not iterable' 오류를 해결하기 위해 
        # index names를 가져오는 방식을 명시적으로 분리합니다. (V3 SDK 권장 방식)**
        index_list = pc.list_indexes()
        index_names = index_list.names 
        
        # 5. 인덱스 존재 여부 확인 및 생성
        if index_name not in pc.list_indexes().names:
            print(f"Pinecone 인덱스 '{index_name}'가 존재하지 않아 새로 생성합니다.")
            pc.create_index(
                name=index_name, 
                dimension=EMBEDDING_DIMENSION, 
                metric='cosine',
                spec=ServerlessSpec(cloud='aws', region='us-west-2')
            )

        # 6. 인덱스 연결 및 캐시 저장
        index = pc.Index(index_name)
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
        # **[수정] Pinecone에 저장할 때는 RDB의 Primary Key(정수) 대신, 
        # 사용자가 설정한 로그인 ID(username/email)를 사용합니다.
        # 이렇게 하면 Pinecone 콘솔에서 '1' 대신 'user@example.com'과 같이 명확하게 보입니다.**
        user_identifier = str(message_obj.user.username)
        message_id = str(message_obj.id)
        
        # 1. 임베딩 생성
        embedding = _get_embedding(message_obj.message)

        # 2. 메타데이터 구성
        metadata = {
            "text": message_obj.message,
            "speaker": "user" if message_obj.is_user else "ai",
            "user_id": user_identifier, # 이제 로그인 ID(username)가 저장됩니다.
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
    # **[수정] 이제 정수 ID 대신 문자열 ID(username)를 필터링에 사용합니다.**
    pinecone_index, query: str, user_identifier: str, n_results: int = 5
) -> Dict[str, Union[List[str], List[Dict]]]:
    """
    Pinecone에서 쿼리와 관련된 문서를 검색하고 ChatService의 예상 형식으로 반환합니다.
    """
    if pinecone_index is None:
        print("--- Pinecone 인덱스가 설정되지 않아 문서 검색을 건너뛰고 빈 결과를 반환합니다. ---")
        return {"documents": [], "metadatas": []}
        
    try:
        print(f"벡터 DB에서 관련 문서를 검색합니다...")
        
        # 1. 쿼리 임베딩 생성
        query_embedding = _get_embedding(query)

        # 2. Pinecone 인덱스 쿼리
        results = pinecone_index.query(
            vector=query_embedding,
            top_k=n_results,
             # **[수정] 저장된 문자열 ID(username)로 필터링합니다.**
            filter={"user_id": user_identifier}, 
            include_metadata=True
        )

        retrieved_docs = []
        retrieved_metadatas = []
        
        for match in results.matches:
            document_content = match.metadata.get('text', '문서 내용 없음')
            
            metadata = {
                'speaker': match.metadata.get('speaker', 'unknown'),
                # metadata.user_id는 이제 문자열 username입니다.
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
