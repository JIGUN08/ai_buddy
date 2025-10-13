# fine_tune_model.py

import openai
import os
# from dotenv import load_dotenv  <-- [삭제] .env 파일 로드 불필요
import time

# [삭제] .env 파일에서 환경 변수를 로드하는 코드를 삭제합니다.
# load_dotenv()

# OpenAI API 키를 환경 변수에서 가져옵니다.
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    # Render 환경에서도 환경 변수가 없을 경우를 대비하여 에러 메시지 유지
    print("오류: OPENAI_API_KEY 환경 변수가 설정되지 않았습니다. Render 설정을 확인해주세요.")
else:
    try:
        client = openai.OpenAI(api_key=api_key)

        # 스크립트 파일이 있는 디렉터리를 기준으로 파일을 찾습니다.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # finetuning_snapshot.jsonl 파일이 스크립트와 같은 디렉터리에 있다고 가정
        file_path = os.path.join(script_dir, "finetuning_snapshot.jsonl") 
        
        # 1. 파일 업로드
        print("학습 파일을 업로드하는 중...")
        training_file = client.files.create(
            file=open(file_path, "rb"), # 동적 경로 사용
            purpose="fine-tune"
        )
        print(f"파일 업로드 완료. 파일 ID: {training_file.id}")

        # 2. 파인튜닝 작업 생성
        print("파인튜닝 작업을 생성하는 중...")
        job = client.fine_tuning.jobs.create(
            training_file=training_file.id,
            model="gpt-3.5-turbo"
        )
        print(f"파인튜닝 작업 생성 완료. 작업 ID: {job.id}")
        print("OpenAI 웹사이트에서 작업 상태를 확인하거나, 아래 명령어로 상태를 확인할 수 있습니다.")
        print(f"openai api fine_tuning.jobs.retrieve -i {job.id}")

    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
        if "No such file or directory" in str(e):
            print(f"경로 오류: '{file_path}' 파일을 찾을 수 없습니다. 파일 경로를 확인해주세요.")
