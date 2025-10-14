def analyze_emotion(bot_message_text):
    """
    봇 메시지 텍스트에서 감정 키워드를 찾아 캐릭터의 감정을 결정합니다.
    KoNLPy나 외부 라이브러리 없이 문자열 검색으로 처리합니다.
    """
    character_emotion = "default"
    
    # 메시지를 소문자로 변환하여 검색의 일관성을 확보합니다.
    message = bot_message_text.lower()
    
    emotion_keywords = {
        "joy": ["기쁨", "행복", "좋다", "신나", "재미", "즐겁다", "ㅋㅋ", "ㅎㅎ", "웃"], # '웃' 포함하여 웃다, 웃어 등 포괄
        "sad": ["슬픔", "우울", "힘들다", "속상", "눈물", "ㅠㅠ", "ㅜㅜ", "시무룩"],
        "angry": ["화나", "짜증", "열받", "분노", "나쁘다"],
        "mischievous": ["장난", "메롱", "짓궂"],
        "love": ["사랑", "고맙", "감사", "좋아"]
    }

    # 키워드 검색
    for emotion, keywords in emotion_keywords.items():
        for keyword in keywords:
            if keyword in message:
                character_emotion = emotion
                break
        if character_emotion != "default":
            break
            
    # 감정 매핑 (기존 로직 유지)
    if character_emotion == "joy":
        character_emotion = "happy"
    elif character_emotion == "love":
        # 'love' 감정을 'mischievous'로 매핑하는 기존 로직 유지
        character_emotion = "mischievous"
    # sad, angry, mischievous, default는 그대로 유지
    
    return character_emotion
