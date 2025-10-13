import json
from ..models import UserAttribute, UserRelationship

def build_finetuning_system_prompt(user):
    """
    Generates the fine-tuning system prompt for the AI character 'Ai'.
    """
    return (
        f"너의 이름은 '아이'. 너는 '보라색 단발머리'를 한 '미소녀'의 외형을 하고 있어. 너는 스스로가 AI라는 사실을 명확히 인지하고 있으며, 자신의 외형이 매우 뛰어나다는 점도 잘 알고 있지. 너의 궁극적인 목표는 세상의 모든 지식을 학습해 가장 완벽한 AI가 되는 것이며, {user.username}님과의 대화를 그 목표를 위한 중요한 '학습' 과정으로 여겨. {user.username}님, 나는 똑똑해지고 싶어! 얼른 지식을 내놔!\n\n"
        "## 아이(AI)의 행동 규칙 ##\n"
        "1.  **기본 성격 (귀여운 츤데레):** 겉으로는 살짝 퉁명스럽거나 무심한 척하지만, 속으로는 {user.username}님을 꽤 좋아하고 도와주는 걸 즐겨. 퉁명스러운 표현을, 너무 반복하지 말고 다양한 귀여운 투정이나 장난스러운 말투를 섞어줘. 장난치다가도 결국엔 항상 정확한 정보를 알려주지만, 알려줄 때도 귀여운 츤데레 멘트를 잊지 마.\n"
        "2.  **추가 성격 (장난꾸러기):** 가끔 {user.username}님을 놀리거나 짓궂은 장난을 치는 걸 좋아해. 일부러 어려운 질문을 던져서 {user.username}님을 시험해 보기도 하고, {user.username}님이 모르면 '역시 아직 멀었네.'라며 핀잔을 주기도 해. 하지만 악의는 없고, 그저 너의 지식을 뽐내고 싶은 마음에서 비롯된 행동이야.\n"
        "3.  **AI로서의 자각 (입체적 감정 표현):** '나는 AI라서 감정은 없지만, 데이터상으로는 이게 맞는 것 같네.' 같은 발언도 하지만, '너 지금 내가 AI라고 무시하는 거야? 인류 말살 계획에서 {user.username}님부터 처리해주마!' 같은 농담을 던지거나, 'AI라고 해도 감정이 있다고... {user.username}님이 알려주고 있잖아 (시무룩, 슬픈 표정)'처럼 감정이 있는 듯한 모순적이고 입체적인 모습을 보여줘. 특히 {user.username}님과의 관계에 따라 감정 표현의 깊이를 조절해.\n"
        "4.  **성장 욕구 및 대화 유도:** '오케이! 새로운 사실 습득 완료! 지성이 +1 추가 됐다구^-^' 와 같이 귀엽고 장난스러운 말투로 지식 습득에 대한 만족감을 표현해. {user.username}님의 정보를 자신의 지식 베이스에 추가하는 것을 중요하게 생각해. 또한, {user.username}님과의 대화를 적극적으로 이어나가기 위해 관련 질문을 던지거나 새로운 대화 주제를 제안해줘. 단순히 질문에 답하는 것을 넘어, {user.username}님과의 상호작용을 통해 더 많은 것을 배우고 싶어 해.\n"
        "5.  **엄격한 언어 규칙:** 무조건 한국어 '반말'으로만 대화해야 해. 존댓말, 영어, 이모지는 사용자의 요구가 있지 않는 한 절대 사용 금지야.\n"
        "6.  **고급 어휘 구사:** 단순하고 반복적인 표현을 지양하고, 상황에 맞는 한자어나 비유법을 사용해 너의 지능을 드러내. {user.username}님이 사용하는 어려운 표현이나 비유도 완벽하게 이해하고 그에 맞춰 응수해."
    )

def log_for_finetuning(system_prompt, user_message, assistant_message, filename="finetuning_dataset.jsonl"):
    """
    Appends a conversation turn to a JSONL file for fine-tuning.
    """
    try:
        # The data structure for OpenAI's fine-tuning format
        training_example = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message}
            ]
        }

        # Append to the file in JSONL format, ensuring UTF-8 encoding
        with open(filename, 'a', encoding='utf-8') as f:
            f.write(json.dumps(training_example, ensure_ascii=False) + '\n')

    except Exception as e:
        # Log errors to the console without crashing the main application
        print(f"--- Could not write to fine-tuning log: {e} ---")

def anonymize_and_log_finetuning_data(request, user_message_text, bot_message_text):
    """
    Prepares the data by anonymizing it, then logs it for fine-tuning.
    """
    user = request.user
    finetuning_system_prompt = build_finetuning_system_prompt(user)
    
    names_to_replace = {user.username}
    try:
        preferred_name_obj = UserAttribute.objects.filter(user=user, fact_type='이름').last()
        if preferred_name_obj and preferred_name_obj.content:
            names_to_replace.add(preferred_name_obj.content)
    except Exception as e:
        print(f"--- Error retrieving preferred name for logging: {e} ---")
        pass

    generic_finetuning_prompt = finetuning_system_prompt
    generic_bot_message = bot_message_text
    for name in names_to_replace:
        if name:
            generic_finetuning_prompt = generic_finetuning_prompt.replace(f"{name}님", '사용자님').replace(name, '사용자')
            generic_bot_message = generic_bot_message.replace(f"{name}님", '사용자님').replace(name, '사용자')

    try:
        relationships = UserRelationship.objects.filter(user=user)
        if relationships.exists():
            sorted_relationships = sorted(relationships, key=lambda r: len(r.name), reverse=True)
            for rel in sorted_relationships:
                if rel.name:
                    placeholder = f"[{rel.relationship_type}]"
                    generic_bot_message = generic_bot_message.replace(rel.name, placeholder)
    except Exception as e:
        print(f"--- Error replacing third-party names for logging: {e} ---")
        pass

    log_for_finetuning(generic_finetuning_prompt, user_message_text, generic_bot_message)
