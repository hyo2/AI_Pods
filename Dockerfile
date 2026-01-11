# Python 3.13 베이스 이미지
FROM python:3.13-slim

# 시스템 패키지 설치 (ffmpeg + libreoffice)
RUN apt-get update && \
    apt-get install -y \
        ffmpeg \
        libreoffice \
        libreoffice-writer \
        libreoffice-calc \
        libreoffice-impress \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# requirements 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 코드 복사
COPY . .

# 포트 노출
EXPOSE 8000

# 앱 실행 (Railway Settings와 동일하게 --proxy-headers 추가)
CMD ["sh", "-c", "echo '===== FFMPEG BUILD CONF =====' && ffmpeg -buildconf && echo '===== FFMPEG LICENSE =====' && ffmpeg -L && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers"]
