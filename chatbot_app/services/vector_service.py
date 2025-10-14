
import chromadb
import openai
import os

# ChromaDB 클라이언트 초기화
# 데이터를 디스크에 영구적으로 저장하기 위해 PersistentClient를 사용합니다.
# 경로를 지정하지 않으면 기본적으로 메모리에 저장됩니다.
client = chromadb.PersistentClient(path="./chroma_db")

# OpenAI 임베딩 함수 설정
# ChromaDB가 내부적으로 이 함수를 사용하여 텍스트를 벡터로 변환합니다.
openai_ef = chromadb.utils.embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.environ.get("OPENAI_API_KEY"),
                model_name="text-embedding-3-small"
            )

def get_or_create_collection(name="chat_history"):
    """
    지정된 이름의 컬렉션을 가져오거나, 없으면 새로 생성합니다.
    OpenAI 임베딩 함수를 사용하도록 명시적으로 설정합니다.
    """
    collection = client.get_or_create_collection(
        name=name,
        embedding_function=openai_ef
    )
    return collection

def upsert_message(collection, chat_message):
    """
    ChatMessage 객체 하나를 받아 ChromaDB에 벡터화하여 저장(upsert)합니다.
    `upsert`는 ID가 존재하면 업데이트, 존재하지 않으면 새로 추가하는 동작입니다.
    """
    try:
        print(f"--- [ChromaDB Debug] Upserting message ID: {chat_message.id}, Speaker: {'user' if chat_message.is_user else 'ai'}, User ID: {chat_message.user.id}, Message: {chat_message.message[:50]}... ---")
        collection.upsert(
            ids=[str(chat_message.id)],
            documents=[chat_message.message],
            metadatas=[{
                "speaker": "user" if chat_message.is_user else "ai",
                "user_id": chat_message.user.id,
                "timestamp": chat_message.timestamp.isoformat()
            }]
        )
        print(f"--- [ChromaDB Debug] Successfully upserted message ID: {chat_message.id} ---")
    except Exception as e:
        print(f"--- [ChromaDB] Error upserting message ID {chat_message.id}: {e} ---")

def query_similar_messages(collection, query_text, user_id, n_results=3, distance_threshold=0.8):
    """
    주어진 텍스트와 가장 유사한 대화 내용을 ChromaDB에서 검색합니다.
    특정 사용자의 대화 내용만 검색하도록 메타데이터 필터링을 사용합니다.
    거리 임계값을 적용하여 충분히 유사한 결과만 반환합니다 (거리가 낮을수록 유사).
    """
    try:
        # ChromaDB 쿼리 시 거리(distances)를 포함하도록 요청
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results, # 일단 n_results만큼 가져온 후 필터링
            where={"user_id": user_id},
            include=['documents', 'metadatas', 'distances'] # 거리 정보 포함 요청
        )

        filtered_results = {
            'ids': [],
            'documents': [],
            'metadatas': [],
            'distances': []
        }

        # 사용자가 지정한 거리 임계값 0.4를 직접 사용
        # 여기서는 distances가 거리이며, 낮을수록 유사하다고 가정합니다.
        
        if results and results.get('distances') and results.get('documents'):
            for i in range(len(results['distances'][0])):
                distance = results['distances'][0][i]
                # 거리가 distance_threshold 이하인 경우만 포함
                if distance <= distance_threshold:
                    filtered_results['ids'].append(results['ids'][0][i])
                    filtered_results['documents'].append(results['documents'][0][i])
                    filtered_results['metadatas'].append(results['metadatas'][0][i])
                    filtered_results['distances'].append(distance)
        
        return filtered_results
    except Exception as e:
        print(f"--- [ChromaDB] Error querying collection: {e} ---")
        return None
