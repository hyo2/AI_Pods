# -*- coding: utf-8 -*-
# 필요한 라이브러리들을 가져옵니다.
import os
import re
import uuid
import pdfplumber      # PDF 파일에서 텍스트를 추출하는 데 사용
import subprocess      # FFmpeg과 같은 외부 명령을 실행하는 데 사용
from google.cloud import texttospeech  # Google Cloud TTS API 클라이언트
from google.oauth2 import service_account # 서비스 계정 인증 정보를 로드하는 데 사용
from google.api_core.exceptions import NotFound # API 호출 시 리소스를 찾지 못했을 때의 예외 처리
from google.auth.exceptions import DefaultCredentialsError # 기본 인증 정보 로드 오류 처리

# Vertex AI SDK (Google의 Generative AI 모델, 즉 Gemini를 사용하기 위해 필요)
try:
    import vertexai
    # GenerativeModel 클래스는 Gemini 모델과 상호작용하는 데 사용됩니다.
    from vertexai.generative_models import GenerativeModel
    HAS_VERTEXAI = True # SDK 로드 성공 플래그
except ImportError:
    # vertexai SDK가 설치되지 않았을 경우를 대비합니다.
    HAS_VERTEXAI = False
    print("경고: vertexai SDK가 설치되어 있지 않습니다. pip install google-cloud-aiplatform 필요")

# =========================
# 1. 환경 변수 / 서비스 계정 및 기본 설정
# =========================
# 프로젝트 ID와 리전은 환경 변수에서 가져오거나 기본값을 사용합니다.
PROJECT_ID = os.getenv("VERTEX_AI_PROJECT_ID")
REGION = os.getenv("VERTEX_AI_REGION", "us-central1")

# 1. Vertex AI (Gemini)용 키 경로 (LLM 스크립트 생성에 사용)
# 환경 변수가 없으면 지정된 로컬 경로를 사용합니다.
VERTEXAI_SA_FILE = os.getenv("VERTEX_AI_SERVICE_ACCOUNT_FILE") or \
                   r"C:\Users\USER\Desktop\securityKey\companyKey\vertex-ai-service-account.json" 

# 2. Google Cloud TTS용 키 경로 (음성 파일 생성에 사용)
# TTS와 Vertex AI는 서로 다른 권한이 필요할 수 있으므로 분리된 키를 사용합니다.
TTS_SA_FILE = os.getenv("TTS_SERVICE_ACCOUNT_FILE") or \
              r"C:\Users\USER\Desktop\securityKey\persokey\notebooklm-podcast-api-test-3f639b2ad136.json"
              
# 기본으로 사용할 Gemini 모델 이름 설정
MODEL_NAME = os.getenv("VERTEX_AI_MODEL", "gemini-2.5-flash")

# =========================
# 2. 두 개의 CREDENTIALS(인증 정보) 로드
# =========================
VERTEXAI_CREDENTIALS = None
TTS_CREDENTIALS = None

# Vertex AI용 Credential 로드 시도
if os.path.exists(VERTEXAI_SA_FILE):
    try:
        # 서비스 계정 파일로부터 인증 정보를 생성합니다.
        VERTEXAI_CREDENTIALS = service_account.Credentials.from_service_account_file(VERTEXAI_SA_FILE)
    except Exception as e:
        # 인증 파일 로드 실패 시 치명적인 오류를 발생시킵니다.
        raise RuntimeError(f"Vertex AI 서비스 계정 파일 로드 오류: {e}")
else:
    # 파일이 없으면 경고 메시지를 출력하고 ADC(Application Default Credentials)를 시도하도록 안내합니다.
    print(f"경고: Vertex AI 서비스 계정 파일을 찾을 수 없습니다: {VERTEXAI_SA_FILE}. ADC를 시도합니다.")

# TTS용 Credential 로드 시도
if os.path.exists(TTS_SA_FILE):
    try:
        # TTS 서비스 계정 파일로부터 인증 정보를 생성합니다.
        TTS_CREDENTIALS = service_account.Credentials.from_service_account_file(TTS_SA_FILE)
    except Exception as e:
        # 인증 파일 로드 실패 시 치명적인 오류를 발생시킵니다.
        raise RuntimeError(f"TTS 서비스 계정 파일 로드 오류: {e}")
else:
    # TTS 파일이 없으면 경고 메시지를 출력합니다.
    print(f"경고: TTS 서비스 계정 파일을 찾을 수 없습니다: {TTS_SA_FILE}. TTS 호출 시 오류가 발생할 수 있습니다.")


# 프로젝트 ID와 리전이 설정되지 않았으면 스크립트를 실행할 수 없습니다.
if not all([PROJECT_ID, REGION]):
    raise RuntimeError("환경 변수 VERTEX_AI_PROJECT_ID와 VERTEX_AI_REGION를 확인하세요.")

# =========================
# 3. PDF → 텍스트 추출 + 전처리
# =========================
def extract_text_from_pdf(pdf_path):
    """
    PDF 파일에서 텍스트를 추출하고 이모지 및 '*'를 제거하여 전처리합니다.
    :param pdf_path: 텍스트를 추출할 PDF 파일의 경로
    :return: 전처리된 텍스트 문자열
    """
    text = ""
    try:
        # pdfplumber를 사용하여 PDF 파일 열기
        with pdfplumber.open(pdf_path) as pdf:
            # 모든 페이지를 순회하며 텍스트를 추출
            for page in pdf.pages:
                # 페이지 텍스트를 추출하고, None일 경우 빈 문자열로 처리
                page_text = page.extract_text() or ""
                text += page_text + "\n"
    except FileNotFoundError:
        # 파일이 없으면 오류 발생
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
    
    # 이모지 및 '*' 제거 (정규식을 사용한 전처리)
    # \U00010000-\U0010ffff 범위는 대부분의 이모지를 포함합니다.
    text = re.sub(r"[\*\U00010000-\U0010ffff]", "", text)
    return text.strip()

# =========================
# 4. 텍스트 → 팟캐스트 스크립트 (Gemini Text Generation)
# =========================
def generate_podcast_script(text_to_convert, max_output_tokens=8192, model_name=None):
    """
    텍스트를 Vertex AI GenerativeModel (Gemini)을 사용하여 멀티 스피커 팟캐스트 스크립트로 변환합니다.
    :param text_to_convert: 스크립트 생성의 기반이 될 원본 텍스트
    :param max_output_tokens: 생성될 스크립트의 최대 토큰 수
    :param model_name: 사용할 Gemini 모델의 이름
    :return: 생성된 팟캐스트 스크립트 문자열
    """
    if not HAS_VERTEXAI:
        raise RuntimeError("vertexai SDK가 설치되어 있지 않습니다. pip install vertexai 필요")

    # Vertex AI 인증 정보가 로드되었는지 확인
    if not VERTEXAI_CREDENTIALS:
        raise RuntimeError("Vertex AI 인증 정보를 로드할 수 없습니다.")
        
    # Vertex AI 초기화 (프로젝트, 위치, 인증 정보를 설정)
    vertexai.init(project=PROJECT_ID, location=REGION, credentials=VERTEXAI_CREDENTIALS)
    model_name = model_name or MODEL_NAME
    
    # GenerativeModel 클래스를 사용하여 Gemini 모델 인스턴스를 생성합니다.
    model = GenerativeModel(model_name)

    # 팟캐스트 스크립트 생성을 위한 프롬프트 정의
    # 중요한 지침: 화자 형식([화자 이름] 내용)을 명확하게 지정하여 TTS 분리가 용이하도록 합니다.
    prompt = f"""
    아래 텍스트를 분석하여 두 명의 화자(진행자, 게스트)가 대화하는 형식의 팟캐스트 스크립트를 한국어로 작성해 주세요.
    각 대화는 반드시 "[화자 이름] 내용"의 형식을 지켜야 하며, 화자 이름 뒤에 콜론(:)을 포함하지 마세요.
    (예: [진행자] 안녕하세요. [게스트] 반갑습니다.)
    
    원본 텍스트:
    ---
    {text_to_convert}
    ---
    """
    
    # 생성 설정 (Generation Configuration)
    config = {
        "max_output_tokens": max_output_tokens,
        "temperature": 0.5, # 창의성 조절 (0에 가까울수록 보수적)
    }

    try:
        # 모델에게 프롬프트와 설정을 전달하여 콘텐츠 생성을 요청합니다.
        response = model.generate_content(
            prompt, 
            generation_config=config
        )
    except NotFound as e:
        # 모델 이름을 잘못 지정했거나 접근할 수 없을 경우 처리
        raise RuntimeError(f"모델 {model_name}을(를) 찾을 수 없습니다: {str(e)}") from e

    # 응답 객체에서 텍스트 내용을 추출합니다.
    script_text = getattr(response, "text", "")

    if not script_text:
        # 텍스트가 반환되지 않았을 경우 오류 처리
        raise RuntimeError(f"GenerativeModel이 텍스트를 반환하지 않았습니다. 응답: {response}")

    # 스크립트 후처리 (Gemini 응답에 남아있을 수 있는 이모지 및 '*' 제거)
    script_text = re.sub(r"[\*\U00010000-\U0010ffff]", "", script_text)

    return script_text.strip()

# =========================
# 5. Multi-Speaker TTS (Google Cloud TTS)
# =========================
def tts_multi_speaker(text, speaker_map=None, base_filename=None):
    """
    스크립트를 '[화자] 내용' 기준으로 분리하여 Google Cloud TTS로 음성 파일을 생성합니다.
    :param text: '[화자] 내용' 형식의 팟캐스트 스크립트
    :param speaker_map: 화자 이름과 Cloud TTS 보이스 이름 매핑 딕셔너리
    :param base_filename: 생성될 임시 파일의 기본 이름
    :return: 생성된 임시 MP3 파일 경로 리스트
    """
    speaker_map = speaker_map or {}
    # 임시 파일 충돌 방지를 위해 고유한 UUID를 사용하여 기본 파일명 생성
    base_filename = base_filename or f"podcast_temp_{uuid.uuid4().hex[:8]}"
    mp3_files = []

    # TTS 인증 정보가 로드되었는지 확인
    if not TTS_CREDENTIALS:
        raise RuntimeError("TTS 인증 정보를 로드할 수 없습니다.")
        
    # Cloud TTS 클라이언트 인스턴스 생성 (인증 정보 사용)
    client = texttospeech.TextToSpeechClient(credentials=TTS_CREDENTIALS)

    # 텍스트를 "[화자] 내용" 형태로 분리하는 정규식 사용.
    # r"\[([^\]]+)\]"는 대괄호 안의 내용(화자 이름)을 캡처하고, 그 기준으로 텍스트를 나눕니다.
    segments = re.split(r"\[([^\]]+)\]", text)
    
    # 분리된 segments 리스트는 [앞선 내용, 화자1 이름, 화자1 내용, 화자2 이름, 화자2 내용, ...] 구조가 됩니다.
    i = 1 # 첫 번째 요소(segments[0])는 일반적으로 버려지는 빈 문자열 또는 서론이므로 1부터 시작
    while i < len(segments):
        # segments[i]는 화자 이름, segments[i + 1]는 해당 화자의 내용이 됩니다.
        speaker = segments[i].strip()
        content = segments[i + 1].strip()
        i += 2 # 다음 화자 쌍으로 이동

        if not content:
            continue
            
        # 화자 이름에 따라 사용할 Cloud TTS 보이스를 선택합니다.
        # 기본값: 진행자(ko-KR-Standard-B, 남성), 게스트(ko-KR-Standard-A, 여성)
        voice_name = speaker_map.get(speaker, "ko-KR-Standard-B" if "진행자" in speaker else "ko-KR-Standard-A")
        
        try:
            # TTS 요청을 위한 입력 설정
            synthesis_input = texttospeech.SynthesisInput(text=content)
            # 음성 선택 파라미터 (한국어, 선택된 보이스 이름)
            voice_params = texttospeech.VoiceSelectionParams(language_code="ko-KR", name=voice_name)
            # 오디오 출력 형식 설정 (MP3)
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

            # TTS API 호출
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config
            )

            # 생성된 오디오 파일 저장 (파일명: [base_filename]_[순서]_[화자].mp3)
            output_file = f"{base_filename}_{len(mp3_files) + 1}_{speaker}.mp3"
            with open(output_file, "wb") as f:
                f.write(response.audio_content) # 응답으로 받은 바이너리 오디오 내용을 파일에 씁니다.
            mp3_files.append(output_file)
            print(f"✅ {speaker} ({voice_name}) 구간 생성 완료 → {output_file}")
            
        except Exception as e:
            # TTS 변환 중 오류 발생 시 메시지 출력 후 다음 세그먼트로 이동
            print(f"TTS 변환 중 오류 발생: {speaker} - {e}")
            continue

    return mp3_files

# =========================
# 6. 생성된 오디오 파일 → MP3 병합 (FFmpeg 사용)
# =========================
def combine_mp3_files(input_files, output_filename="final_podcast_episode.mp3"):
    """
    FFmpeg을 사용하여 여러 MP3 파일을 하나의 파일로 순차적으로 병합하고 임시 파일을 삭제합니다.
    (주의: 이 함수를 사용하려면 시스템에 FFmpeg이 설치되어 있어야 합니다.)
    :param input_files: 병합할 임시 MP3 파일 경로 리스트
    :param output_filename: 최종 출력될 MP3 파일 이름
    :return: 최종 MP3 파일 경로 (성공 시), 또는 None (실패 시)
    """
    if not input_files:
        print("경고: 병합할 오디오 파일이 없습니다.")
        return None
        
    try:
        # FFmpeg의 'concat' demuxer를 사용하기 위해 연결 목록 파일(concat_list.txt)을 생성합니다.
        list_file_path = "concat_list.txt"
        with open(list_file_path, "w", encoding="utf-8") as f:
            for file in input_files:
                # 파일 경로에 공백이나 특수 문자가 있을 경우를 대비하여 'file 'file path'' 형식을 사용합니다.
                f.write(f"file '{os.path.abspath(file)}'\n")

        print(f"{len(input_files)}개 오디오 파일을 {output_filename}로 병합 중...")
        
        # FFmpeg 명령 정의
        command = [
            "ffmpeg",
            "-f", "concat",    # 입력 형식을 concat demuxer로 지정
            "-safe", "0",      # 'unsafe'한 파일 경로를 허용 (보안 경고 방지)
            "-i", list_file_path, # 입력 파일로 목록 파일을 지정
            "-c", "copy",      # 오디오를 재인코딩하지 않고 복사(빠름, 무손실)
            output_filename    # 최종 출력 파일 이름
        ]
        
        # subprocess.run을 사용하여 FFmpeg 실행
        # check=True: 명령 실행 실패 시 CalledProcessError 발생
        subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
        
        # 작업 완료 후 임시 파일 정리
        os.remove(list_file_path)
        for file in input_files:
            if os.path.exists(file):
                os.remove(file)
            
        print(f"최종 팟캐스트 파일 생성 완료: {output_filename}")
        return output_filename
        
    except FileNotFoundError:
        # FFmpeg 실행 파일이 시스템 PATH에 없을 경우
        print("\n FFmpeg을 찾을 수 없습니다. 오디오 파일 병합을 건너뜁니다.")
        print("FFmpeg을 설치하고 시스템 PATH에 추가해야 합니다. (개별 파일은 남아 있습니다.)")
        return None
    except subprocess.CalledProcessError as e:
        # FFmpeg 명령 실행 중 오류가 발생한 경우
        print(f"\n FFmpeg 실행 중 오류 발생: {e}")
        print(f"Stderr: {e.stderr}")
        return None

# =========================
# 7. PDF → 팟캐스트 전체 처리 메인 함수
# =========================
def pdf_to_podcast(pdf_file, model_name=None):
    """
    PDF 파일 경로를 받아 텍스트 추출, 스크립트 생성, TTS 변환, 오디오 병합의 전체 과정을 수행합니다.
    :param pdf_file: 입력 PDF 파일 경로
    :param model_name: 사용할 Gemini 모델의 이름
    :return: 최종 팟캐스트 MP3 파일 경로
    """
    print(" PDF 텍스트 추출 중...")
    text = extract_text_from_pdf(pdf_file)
    
    if not text:
        print("경고: PDF에서 추출된 텍스트가 없습니다. 작업을 중단합니다.")
        return None

    print("팟캐스트 스크립트 생성 중...")
    # model_name이 None이면 기본값인 gemini-2.5-flash 사용
    script = generate_podcast_script(text, model_name=model_name)
    
    print("\n--- 팟캐스트 스크립트 미리보기 (첫 500자) ---\n")
    # 생성된 스크립트의 일부를 출력하여 확인
    print(script[:500] + "..." if len(script) > 500 else script)
    print("\n-----------------------\n")

    print("Multi-Speaker TTS 변환 중...")
    # 화자별 보이스 매핑을 정의합니다.
    speaker_map = {"진행자": "ko-KR-Standard-B", "게스트": "ko-KR-Standard-A"} 
    mp3_files = tts_multi_speaker(script, speaker_map=speaker_map)

    # 오디오 파일 병합 (FFmpeg)
    final_file = combine_mp3_files(mp3_files)

    return final_file

# =========================
# 8. CLI(Command Line Interface) 실행 로직
# =========================
if __name__ == "__main__":
    # argparse 모듈을 사용하여 명령줄 인수를 처리
    import argparse
    parser = argparse.ArgumentParser(description="Convert a PDF into a multi-speaker podcast using Vertex AI and Google Cloud TTS.")
    
    # 기본 PDF 파일 경로 설정
    DEFAULT_PDF_PATH = r"C:\Users\USER\Desktop\feeling\팟캐스트_에이전트_PRD.pdf" 
    
    # PDF 파일 경로를 인수로 받거나 기본값을 사용합니다.
    parser.add_argument("pdf", nargs="?", help=f"PDF 파일 경로 (기본값: {DEFAULT_PDF_PATH})", default=DEFAULT_PDF_PATH) 
    
    # 사용할 모델을 지정하는 옵션
    parser.add_argument("--model", "-m", help=f"사용할 모델 (기본값: {MODEL_NAME})")
    # 환경 설정 및 인증 상태를 확인하는 디버깅 옵션
    parser.add_argument("--check", action="store_true", help="환경/인증 점검만 수행")
    args = parser.parse_args()
    
    selected_model = args.model or MODEL_NAME

    if args.check:
        # 'check' 인수가 있을 경우 진단 정보를 출력합니다.
        print("Running environment diagnostics...")
        print(f"PROJECT_ID: {'SET' if PROJECT_ID else 'MISSING'}")
        print(f"REGION: {REGION}")
        print(f"Vertex AI SA File: {VERTEXAI_SA_FILE} | Status: {'Found' if os.path.exists(VERTEXAI_SA_FILE) else 'MISSING'}")
        print(f"TTS SA File: {TTS_SA_FILE} | Status: {'Found' if os.path.exists(TTS_SA_FILE) else 'MISSING'}")
        print(f"Vertex AI Creds Loaded: {'Yes' if VERTEXAI_CREDENTIALS else 'No'}")
        print(f"TTS Creds Loaded: {'Yes' if TTS_CREDENTIALS else 'No'}")
        print(f"vertexai SDK available: {'yes' if HAS_VERTEXAI else 'no'}")
        print(f"Configured model: {selected_model}")
        
    else:
        # 실제 팟캐스트 생성 프로세스를 실행합니다.
        try:
            # pdf_to_podcast 함수 호출
            final_podcast_path = pdf_to_podcast(args.pdf, model_name=selected_model) 
            if final_podcast_path:
                print(f"\n✨ 모든 작업 완료! 최종 팟캐스트 파일: {final_podcast_path}")
        except Exception as e:
            # 실행 중 발생한 모든 예외를 포착하여 출력합니다.
            print(f"\n 치명적인 오류 발생: {e}")
            exit(1) # 오류 발생 시 프로그램 종료 (종료 코드 1)