# app/services/podcast/audio_processor.py
import os
import uuid
import subprocess
import logging
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

INTER_CHUNK_DELAY = 1.0


class AudioProcessor:
    """오디오 파일 병합 및 처리"""
    
    @staticmethod
    def merge_audio_files(wav_files: List[str]) -> str:
        """여러 WAV 파일을 하나의 MP3로 병합"""
        if not wav_files:
            raise ValueError("병합할 오디오 파일이 없습니다")
        
        logger.info(f"오디오 파일 {len(wav_files)}개 병합 중...")
        
        list_file_path = "concat_list.txt"
        final_filename = f"podcast_episode_{uuid.uuid4().hex[:8]}.mp3"
        
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
        """타임스탬프가 포함된 스크립트 생성"""
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
        
        transcript_path = output_path.replace(".mp3", ".txt")
        
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write("\n".join(transcript_lines))
        
        logger.info(f"스크립트 생성 완료: {transcript_path}")
        
        return transcript_path