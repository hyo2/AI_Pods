# app/langgraph_pipeline/podcast/audio_processor.py
import os
import uuid
import subprocess
import logging
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

INTER_CHUNK_DELAY = 1.0


def get_output_dir() -> str:
    """환경에 맞는 출력 디렉토리 반환"""
    base = os.getenv("BASE_OUTPUT_DIR", "outputs")
    return os.path.join(base, "podcasts")


class AudioProcessor:
    """오디오 파일 병합 및 처리"""
    
    def __init__(self, model_type: str = "google_cloud"):
        self.model_type = model_type
    
    @staticmethod
    def merge_audio_files(wav_files: List[str]) -> str:
        """여러 WAV 파일을 하나의 MP3로 병합"""
        if not wav_files:
            raise ValueError("병합할 오디오 파일이 없습니다")
        
        logger.info(f"오디오 파일 {len(wav_files)}개 병합 중...")
        
        # ✅ 환경 변수 기반 경로 사용
        output_dir = get_output_dir()
        os.makedirs(output_dir, exist_ok=True)

        list_file_path = os.path.join(output_dir, "concat_list.txt")
        final_filename = os.path.join(output_dir, f"podcast_episode_{uuid.uuid4().hex[:8]}.mp3")
        
        try:
            # FFmpeg concat 파일 생성
            with open(list_file_path, "w", encoding="utf-8") as f:
                for file in wav_files:
                    f.write(f"file '{os.path.abspath(file)}'\n")
            
            # FFmpeg 실행
            command = [
                "ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file_path,
                "-c:a", "libmp3lame", "-b:a", "192k", "-y", final_filename
            ]
            
            subprocess.run(
                command, 
                check=True, 
                capture_output=True, 
                text=True, 
                encoding="utf-8"
            )
            
            # 임시 파일 정리
            os.remove(list_file_path)
            for file in wav_files:
                if os.path.exists(file):
                    os.remove(file)
            
            logger.info(f"병합 완료: {final_filename}")
            
            return final_filename
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg 오류: {e.stderr}")
            raise RuntimeError(f"오디오 병합 실패: {e.stderr}")
        except Exception as e:
            logger.error(f"병합 오류: {e}")
            raise
    
    @staticmethod
    def generate_transcript(
        audio_metadata: List[Dict[str, Any]], 
        output_path: str
    ) -> str:
        """타임스탬프가 포함된 스크립트 생성
        
        Args:
            audio_metadata: 오디오 메타데이터 리스트
            output_path: MP3 파일 경로 (예: /tmp/outputs/podcasts/podcast_episode_abc123.mp3)
        
        Returns:
            생성된 트랜스크립트 파일 경로
        """
        logger.info("타임스탬프 스크립트 생성 중...")
        
        current_time = 0.0
        transcript_lines = []
        
        for item in audio_metadata:
            seconds = int(current_time)
            hh = seconds // 3600
            mm = (seconds % 3600) // 60
            ss = seconds % 60
            timestamp = f"[{hh:02}:{mm:02}:{ss:02}]"
            
            line = f"{timestamp} [{item['speaker']}]: {item['text']}"
            transcript_lines.append(line)
            
            current_time += item['duration'] + INTER_CHUNK_DELAY
        
        # ✅ output_path에서 파일명 추출 후 .txt로 변경
        if not output_path or not os.path.basename(output_path):
            # output_path가 디렉토리거나 빈 값인 경우 fallback
            output_dir = get_output_dir()
            transcript_filename = f"transcript_{uuid.uuid4().hex[:8]}.txt"
            transcript_path = os.path.join(output_dir, transcript_filename)
            logger.warning(f"output_path가 유효하지 않아 fallback 사용: {transcript_path}")
        else:
            # 정상 케이스: MP3 파일명에서 .txt로 변경
            base_name = os.path.basename(output_path)
            transcript_filename = base_name.replace(".mp3", ".txt")
            output_dir = os.path.dirname(output_path)
            transcript_path = os.path.join(output_dir, transcript_filename)
        
        # 디렉토리 확인
        os.makedirs(os.path.dirname(transcript_path), exist_ok=True)
        
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write("\n".join(transcript_lines))
        
        logger.info(f"스크립트 생성 완료: {transcript_path}")
        
        return transcript_path