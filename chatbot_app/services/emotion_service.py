import os

def analyze_emotion(bot_message_text):
    """
    Analyzes the bot's message to determine the character's emotion.
    Initializes KoNLPy's Okt tagger within the function to ensure JAVA_HOME is set.
    """
    character_emotion = "default"
    try:
        # Import locally to ensure JAVA_HOME is set by the time this is called
        from konlpy.tag import Okt
        okt = Okt()
        
        morphs = okt.pos(bot_message_text, stem=True)
        print(f"\n--- Emotion Analysis Debug ---")
        print(f"Bot Message: {bot_message_text}")
        print(f"Morphs: {morphs}")
        
        emotion_keywords = {
            "joy": ["기쁨", "행복", "좋다", "신나다", "재미있다", "즐겁다", "ㅋㅋ", "ㅎㅎ", "웃다", "웃어", "웃으니", "웃는다", "미소"],
            "sad": ["슬픔", "우울", "힘들다", "속상하다", "눈물", "ㅠㅠ", "ㅜㅜ", "시무룩"],
            "angry": ["화나다", "짜증", "열받다", "분노", "나쁘다"],
            "mischievous": ["장난", "메롱", "짓궂다"],
            "love": ["사랑", "좋아하다", "고맙다", "감사하다", "좋아"]
        }
        
        detected_word = None
        for word, pos in morphs:
            if pos in ['Noun', 'Adjective', 'Verb']:
                for emotion, keywords in emotion_keywords.items():
                    if word in keywords:
                        character_emotion = emotion
                        detected_word = word
                        break
            if character_emotion != "default":
                break
        
        print(f"Detected Word: {detected_word}")
        print(f"Detected Emotion (before mapping): {character_emotion}")
        
        # Map emotions to character states
        if character_emotion == "joy":
            character_emotion = "happy"
        elif character_emotion == "love":
            character_emotion = "mischievous"
        # sad, angry, mischievous map directly

        print(f"Final Emotion (after mapping): {character_emotion}")
        print(f"--- End Debug ---")

    except Exception as e:
        print(f"--- KoNLPy/Emotion Analysis Error ---: {e}")
        # In case of an error, we just return the default emotion
        character_emotion = "default"
        
    return character_emotion
