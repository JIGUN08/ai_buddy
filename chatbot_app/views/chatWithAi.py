import json
import os
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from dotenv import load_dotenv

load_dotenv()

from ..services import chat_service, emotion_service, finetuning_service

@login_required
def chat_response(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_message_text = data.get('message', '')
        
        bot_message_text = "죄송합니다. API 응답을 가져오는 데 실패했습니다."
        explanation = ""
        character_emotion = "default"
        bot_message_obj = None

        try:
            # 1. 채팅 상호작용 (컨텍스트 생성, API 호출, 응답 처리, 기억 저장)
            bot_message_text, explanation, bot_message_obj = chat_service.process_chat_interaction(request, user_message_text)

            # 2. 파인튜닝 데이터 로깅
            finetuning_service.anonymize_and_log_finetuning_data(request, user_message_text, bot_message_text)

            # 3. 감정 분석
            character_emotion = emotion_service.analyze_emotion(bot_message_text)

        except Exception as e:
            print(f"예상치 못한 오류: {e}")
            bot_message_text = f"예상치 못한 오류가 발생했습니다: {e}"
            character_emotion = "sad"

        timestamp = bot_message_obj.timestamp.isoformat() if bot_message_obj else timezone.now().isoformat()
        return JsonResponse({'message': bot_message_text, 'character_emotion': character_emotion, 'explanation': explanation, 'timestamp': timestamp})
    return JsonResponse({'error': 'Invalid request'}, status=400)
