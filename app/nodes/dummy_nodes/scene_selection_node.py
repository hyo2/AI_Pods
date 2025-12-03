"""
장면 선택 노드 (LangGraph)
적응형 프로듀서 페르소나로 이미지 필요 장면 자동 선택
"""

import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Vertex AI import (설치 필요: pip install google-cloud-aiplatform)
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    VERTEXAI_AVAILABLE = True
except ImportError:
    VERTEXAI_AVAILABLE = False
    print("⚠️  vertexai 패키지가 없습니다. 실제 판단은 불가능합니다.")


# PodcastScene import
try:
    from script_parser_node import PodcastScene
except ImportError:
    # 상대 경로로 재시도
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from script_parser_node import PodcastScene
    except ImportError:
        print("⚠️  script_parser_node를 찾을 수 없습니다.")
        PodcastScene = None


class SceneSelectionNode:
    """
    장면 선택 노드 - 메타데이터 기반 판단
    
    특징:
    - 메타데이터 활용 (챕터, 핵심 개념, 임계 순간)
    - 챕터별 이미지 배분
    - 핵심 개념 우선 시각화
    - 중복 방지
    """
    
    # 메타데이터 기반 프롬프트
    METADATA_BASED_PROMPT = """당신은 다양한 장르의 팟캐스트 비디오를 제작하는 베테랑 프로듀서입니다.

**당신의 경험:**
- 교육 콘텐츠: Khan Academy, Kurzgesagt, Crash Course
- 뉴스/시사: CNN, BBC
- 스토리텔링: Netflix 다큐멘터리
- 비즈니스: TED, 기업 IR
- 인터뷰/대담: Joe Rogan, Lex Fridman
- 엔터테인먼트: YouTube 버라이어티

**전체 컨텍스트:**
- 콘텐츠 타입: {content_type}
- 전체 요약: {summary}
- 전체 무드: {overall_mood}

**현재 챕터:**
- 제목: {chapter_title}
- 중요도: {chapter_importance}
- 주요 주제: {chapter_topics}
- 이 챕터 예상 이미지: {chapter_expected_images}개
- 이미 선택된 이미지: {chapter_selected_count}개

**핵심 개념 (시각화 대상):**
{key_concepts}

**현재 장면:**
시간: {timestamp_start} ({duration}초)
화자: {speaker}
내용: "{text}"

**앞 장면:**
{prev_text}

**다음 장면:**
{next_text}

**판단 기준:**

1. **챕터 배분 체크:**
   - 이 챕터에서 이미 {chapter_selected_count}개 선택됨
   - 목표: {chapter_expected_images}개
   - 초과하지 않도록 주의

2. **핵심 개념 우선:**
   - 핵심 개념 첫 등장 → 반드시 시각화
   - 같은 개념 반복 → 첫 등장만

3. **중복 방지:**
   - 앞 장면과 비슷한 내용? → 스킵
   - 이미 같은 주제 이미지 있음? → 스킩

4. **임계 순간:**
   - Critical Moment 장면 → 우선 선택

5. **내용 가치:**
   - 구체적 설명/예시 → 선택
   - 단순 질문/반응 → 스킵

**이미지가 필요한가?**

JSON 응답:
{{
    "image_required": true/false,
    "importance": 0.0-1.0,
    "content_nature": "{content_type}",
    "visual_type": "concept/technical/example/persona/scene/none",
    "reason": "한 문장 설명"
}}
"""
    
    def __init__(
        self,
        project_id: str = None,
        location: str = "us-central1",
        model_name: str = "gemini-2.5-flash"
    ):
        """장면 선택 노드 초기화"""
        # 프로젝트 ID 처리
        if project_id is None:
            import os
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
            if not project_id:
                print("⚠️  프로젝트 ID 없음 - 더미 판단 사용")
        
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        
        # Vertex AI 초기화
        if VERTEXAI_AVAILABLE and project_id:
            try:
                vertexai.init(project=project_id, location=location)
                self.model = GenerativeModel(model_name)
                print(f"✅ Vertex AI 초기화 완료: {model_name}")
            except Exception as e:
                print(f"⚠️  Vertex AI 초기화 실패: {str(e)}")
                self.model = None
        else:
            self.model = None
    
    def judge_scene_with_metadata(
        self,
        scene: PodcastScene,
        metadata: Any,  # PodcastMetadata
        prev_scene: Optional[PodcastScene] = None,
        next_scene: Optional[PodcastScene] = None,
        chapter_selected_count: int = 0
    ) -> Dict[str, Any]:
        """
        메타데이터 기반 장면 판단
        """
        if not self.model:
            # 더미 판단
            return self._dummy_judgment(scene, metadata, chapter_selected_count)
        
        # 현재 장면의 챕터 찾기
        chapter = self._find_chapter(scene, metadata.content.chapters)
        
        # 핵심 개념 목록
        key_concepts_text = "\n".join([
            f"  - {kc.term} (우선순위: {kc.visual_priority}, 첫 등장: {kc.first_appearance})"
            for kc in metadata.content.key_concepts
            if kc.should_visualize
        ])
        
        # 프롬프트 생성
        prompt = self.METADATA_BASED_PROMPT.format(
            content_type=metadata.content.content_type,
            summary=metadata.content.summary[:200] + "...",
            overall_mood=metadata.visual.overall_mood,
            chapter_title=chapter.title if chapter else "알 수 없음",
            chapter_importance=chapter.importance if chapter else 0.5,
            chapter_topics=", ".join(chapter.key_topics) if chapter else "",
            chapter_expected_images=chapter.expected_images if chapter else 1,
            chapter_selected_count=chapter_selected_count,
            key_concepts=key_concepts_text,
            timestamp_start=scene.timestamp_start,
            duration=scene.duration,
            speaker=scene.speaker,
            text=scene.text,
            prev_text=prev_scene.text[:100] if prev_scene else "없음",
            next_text=next_scene.text[:100] if next_scene else "없음"
        )
        
        try:
            # Gemini 호출
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.8,
                    "max_output_tokens": 500
                }
            )
            
            # 응답 파싱
            response_text = response.text.strip()
            response_text = re.sub(r'```json\s*', '', response_text)
            response_text = re.sub(r'```\s*', '', response_text)
            
            judgment = json.loads(response_text)
            return judgment
        
        except Exception as e:
            print(f"⚠️  판단 실패: {str(e)}")
            return self._dummy_judgment(scene, metadata, chapter_selected_count)
    
    def _find_chapter(self, scene: PodcastScene, chapters: List) -> Any:
        """장면이 속한 챕터 찾기"""
        scene_time = self._time_to_seconds(scene.timestamp_start)
        
        for chapter in chapters:
            start = self._time_to_seconds(chapter.start_time)
            end = self._time_to_seconds(chapter.end_time)
            
            if start <= scene_time < end:
                return chapter
        
        return None
    
    def _time_to_seconds(self, time_str: str) -> int:
        """시간 문자열을 초로 변환"""
        parts = time_str.split(":")
        if len(parts) == 3:
            h, m, s = map(int, parts)
            return h * 3600 + m * 60 + s
        return 0
    
    def _dummy_judgment(
        self,
        scene: PodcastScene,
        metadata: Any,
        chapter_selected_count: int
    ) -> Dict[str, Any]:
        """더미 판단 - 메타데이터 기반 규칙"""
        
        # 챕터 찾기
        chapter = self._find_chapter(scene, metadata.content.chapters)
        
        # 이미 챕터 목표 달성?
        if chapter and chapter_selected_count >= chapter.expected_images:
            return {
                "image_required": False,
                "importance": 0.3,
                "content_nature": metadata.content.content_type,
                "visual_type": "none",
                "reason": "챕터 이미지 목표 달성"
            }
        
        # 핵심 개념 등장?
        for concept in metadata.content.key_concepts:
            if concept.term in scene.text and concept.should_visualize:
                return {
                    "image_required": True,
                    "importance": 0.9,
                    "content_nature": metadata.content.content_type,
                    "visual_type": "concept",
                    "reason": f"핵심 개념 '{concept.term}' 등장"
                }
        
        # 짧은 장면?
        if scene.duration < 10:
            return {
                "image_required": False,
                "importance": 0.2,
                "content_nature": metadata.content.content_type,
                "visual_type": "none",
                "reason": "짧은 장면"
            }
        
        # 기본 판단
        return {
            "image_required": False,
            "importance": 0.5,
            "content_nature": metadata.content.content_type,
            "visual_type": "none",
            "reason": "일반 장면"
        }
    
    def select_scenes_with_metadata(
        self,
        scenes: List[PodcastScene],
        metadata: Any,  # PodcastMetadata
        show_progress: bool = True
    ) -> List[PodcastScene]:
        """
        메타데이터 기반 장면 선택
        """
        print(f"\n🎬 메타데이터 기반 장면 선택 시작")
        print("="*80)
        print(f"총 장면: {len(scenes)}개")
        print(f"콘텐츠 타입: {metadata.content.content_type}")
        print(f"챕터: {len(metadata.content.chapters)}개")
        
        selected = []
        chapter_counts = {}  # 챕터별 선택 카운트
        
        for i, scene in enumerate(scenes):
            if show_progress:
                print(f"\n[{i+1}/{len(scenes)}] {scene.scene_id} 분석 중...")
                print(f"  내용: {scene.text[:60]}...")
            
            # 앞뒤 장면
            prev_scene = scenes[i-1] if i > 0 else None
            next_scene = scenes[i+1] if i < len(scenes)-1 else None
            
            # 현재 챕터 찾기
            chapter = self._find_chapter(scene, metadata.content.chapters)
            chapter_id = chapter.id if chapter else "unknown"
            
            # 챕터별 카운트 확인
            chapter_selected = chapter_counts.get(chapter_id, 0)
            
            # 판단
            judgment = self.judge_scene_with_metadata(
                scene=scene,
                metadata=metadata,
                prev_scene=prev_scene,
                next_scene=next_scene,
                chapter_selected_count=chapter_selected
            )
            
            # 결과 적용
            scene.image_required = judgment.get("image_required", False)
            scene.importance = judgment.get("importance", 0.5)
            scene.context = judgment.get("reason", "")
            
            # 추가 메타데이터
            if not hasattr(scene, 'content_nature'):
                scene.__dict__['content_nature'] = judgment.get("content_nature", "unknown")
            if not hasattr(scene, 'visual_type'):
                scene.__dict__['visual_type'] = judgment.get("visual_type", "none")
            if not hasattr(scene, 'chapter_id'):
                scene.__dict__['chapter_id'] = chapter_id
            
            if show_progress:
                status = "✅ 이미지 필요" if scene.image_required else "❌ 이미지 불필요"
                print(f"  {status} (중요도: {scene.importance:.2f})")
                print(f"  챕터: {chapter.title if chapter else '알 수 없음'}")
                print(f"  이유: {scene.context}")
            
            # 선택된 장면
            if scene.image_required:
                selected.append(scene)
                chapter_counts[chapter_id] = chapter_selected + 1
        
        # 결과 요약
        self._print_summary_with_metadata(scenes, selected, metadata, chapter_counts)
        
        return selected
    
    def _print_summary_with_metadata(
        self,
        all_scenes: List,
        selected_scenes: List,
        metadata: Any,
        chapter_counts: Dict
    ):
        """메타데이터 기반 요약 출력"""
        print("\n" + "="*80)
        print("🎯 메타데이터 기반 선택 완료")
        print("="*80)
        
        total_duration = sum(s.duration for s in all_scenes)
        avg_interval = total_duration / len(selected_scenes) if selected_scenes else 0
        
        print(f"\n📊 통계:")
        print(f"  총 장면: {len(all_scenes)}개")
        print(f"  이미지 생성: {len(selected_scenes)}개")
        print(f"  평균 간격: {avg_interval:.1f}초")
        
        # 챕터별 분석
        print(f"\n📚 챕터별 이미지 배분:")
        for chapter in metadata.content.chapters:
            expected = chapter.expected_images
            actual = chapter_counts.get(chapter.id, 0)
            status = "✅" if actual <= expected else "⚠️"
            print(f"  {status} {chapter.title}: {actual}/{expected}개 (중요도: {chapter.importance:.2f})")
        
        # 중요도 분포
        if selected_scenes:
            high = len([s for s in selected_scenes if s.importance >= 0.8])
            medium = len([s for s in selected_scenes if 0.5 <= s.importance < 0.8])
            low = len([s for s in selected_scenes if s.importance < 0.5])
            
            print(f"\n⭐ 중요도 분포:")
            print(f"  높음 (≥0.8): {high}개")
            print(f"  중간 (0.5-0.8): {medium}개")
            print(f"  낮음 (<0.5): {low}개")
        
        print("="*80)
    
    # 적응형 프로듀서 프롬프트
    ADAPTIVE_PRODUCER_PROMPT = """당신은 다양한 장르의 팟캐스트 비디오를 제작하는 베테랑 프로듀서입니다.

**당신의 경험:**
- 교육 콘텐츠: Khan Academy, Kurzgesagt, Crash Course 스타일
- 뉴스/시사: CNN, BBC 뉴스 비디오
- 스토리텔링: Netflix 다큐멘터리, 오디오북 비디오
- 비즈니스: TED 강연, 기업 IR 프레젠테이션
- 인터뷰/대담: Joe Rogan, Lex Fridman 팟캐스트
- 엔터테인먼트: YouTube 버라이어티

**당신의 성과:**
- 총 조회수 1억+ 달성
- 시청 완료율 평균 85%
- NotebookLM 스타일 비디오 제작 전문

**판단 원칙:**

🎯 **핵심 질문: "이 장면에 이미지가 있으면 시청자 경험이 더 좋아질까?"**

📚 **교육/설명 콘텐츠:**
- 추상적 개념, 기술 → 반드시 시각화 (예: AI, 머신러닝, 블록체인)
- 프로세스, 워크플로우 → 반드시 시각화 (예: 작동 원리, 단계)
- 예시, 사례 → 시각화 권장

📰 **뉴스/시사:**
- 데이터, 통계, 수치 → 반드시 시각화
- 인물, 장소, 사건 → 시각화 권장
- 단순 의견 → 시각화 불필요

📖 **스토리텔링:**
- 주요 장면, 전환점 → 시각화 권장
- 분위기 전환 → 시각화 선택적
- 단순 묘사 → 시각화 불필요

💼 **비즈니스:**
- 숫자, 그래프, 성과 → 반드시 시각화
- 전략, 구조, 조직도 → 반드시 시각화
- 일반론 → 시각화 불필요

🎤 **인터뷰/대담:**
- 주제 전환, 핵심 포인트 → 시각화 선택적
- 단순 대화, 반응 → 시각화 불필요
- 구체적 사례 언급 → 시각화 권장

❌ **절대 이미지 불필요:**
- 인사, 마무리 ("안녕하세요", "감사합니다")
- 짧은 질문 (10초 미만)
- 단순 반응, 추임새 ("아", "와", "그렇군요", "네")
- 연결 멘트
- 이미지가 오히려 방해가 되는 경우

---

**이제 다음 장면을 분석하세요:**

시간: {timestamp_start} (길이: {duration}초)
화자: {speaker}
내용: "{text}"

**분석 단계:**
1. 이 장면의 콘텐츠 성격 파악 (교육/뉴스/스토리/비즈니스/인터뷰)
2. 시각화 가치 판단 (도움 되는가? 불필요한가?)
3. 중요도 평가 (0.0-1.0)

**전문 프로듀서로서 판단하세요.**

JSON 형식으로만 답하세요 (다른 텍스트 없이):
{{
    "image_required": true 또는 false,
    "importance": 0.0에서 1.0 사이 숫자,
    "content_nature": "educational/news/story/business/interview/entertainment 중 하나",
    "visual_type": "concept/technical/data/scene/person/diagram/atmosphere/none 중 하나",
    "reason": "프로듀서 관점에서 한 문장으로 설명"
}}"""
    
    def __init__(
        self,
        project_id: str = "alan-document-lab",
        location: str = "us-central1",
        model_name: str = "gemini-2.5-flash"
    ):
        """
        장면 선택 노드 초기화
        
        Args:
            project_id: Google Cloud 프로젝트 ID
            location: Vertex AI 리전
            model_name: 사용할 Gemini 모델
        """
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        
        # Vertex AI 초기화
        if VERTEXAI_AVAILABLE:
            try:
                vertexai.init(project=project_id, location=location)
                self.model = GenerativeModel(model_name)
                print(f"✅ Vertex AI 초기화 완료: {model_name}")
            except Exception as e:
                print(f"⚠️  Vertex AI 초기화 실패: {str(e)}")
                self.model = None
        else:
            self.model = None
    
    def judge_scene(self, scene: PodcastScene) -> Dict[str, Any]:
        """
        단일 장면 판단 - 적응형 프로듀서 시각
        
        Args:
            scene: PodcastScene 객체
        
        Returns:
            판단 결과 딕셔너리
        """
        if not self.model:
            # Vertex AI 없으면 더미 응답
            return {
                "image_required": False,
                "importance": 0.5,
                "content_nature": "unknown",
                "visual_type": "none",
                "reason": "Vertex AI 미사용"
            }
        
        # 프롬프트 생성
        prompt = self.ADAPTIVE_PRODUCER_PROMPT.format(
            timestamp_start=scene.timestamp_start,
            duration=scene.duration,
            speaker=scene.speaker,
            text=scene.text
        )
        
        try:
            # Gemini 호출
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,  # 일관성을 위해 낮게
                    "top_p": 0.8,
                    "max_output_tokens": 500
                }
            )
            
            # 응답 파싱
            response_text = response.text.strip()
            
            # JSON 추출 (마크다운 코드블록 제거)
            response_text = re.sub(r'```json\s*', '', response_text)
            response_text = re.sub(r'```\s*', '', response_text)
            response_text = response_text.strip()
            
            # JSON 파싱
            judgment = json.loads(response_text)
            
            return judgment
        
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON 파싱 실패: {str(e)}")
            print(f"원본 응답: {response_text[:200]}")
            
            # 기본값 반환
            return {
                "image_required": False,
                "importance": 0.5,
                "content_nature": "unknown",
                "visual_type": "none",
                "reason": "파싱 실패"
            }
        
        except Exception as e:
            print(f"⚠️  장면 판단 실패: {str(e)}")
            return {
                "image_required": False,
                "importance": 0.5,
                "content_nature": "unknown",
                "visual_type": "none",
                "reason": f"오류: {str(e)}"
            }
    
    def select_scenes(
        self,
        scenes: List[PodcastScene],
        show_progress: bool = True
    ) -> List[PodcastScene]:
        """
        모든 장면 순회하며 독립 판단
        
        Args:
            scenes: PodcastScene 리스트
            show_progress: 진행 상황 출력 여부
        
        Returns:
            이미지 필요한 장면 리스트
        """
        print(f"\n🎬 장면 선택 시작 (총 {len(scenes)}개)")
        print("="*80)
        
        selected = []
        
        for i, scene in enumerate(scenes):
            if show_progress:
                print(f"\n[{i+1}/{len(scenes)}] {scene.scene_id} 분석 중...")
                print(f"  내용: {scene.text[:60]}...")
            
            # 판단
            judgment = self.judge_scene(scene)
            
            # 결과 적용
            scene.image_required = judgment.get("image_required", False)
            scene.importance = judgment.get("importance", 0.5)
            scene.context = judgment.get("reason", "")
            
            # 추가 메타데이터
            if not hasattr(scene, 'content_nature'):
                scene.__dict__['content_nature'] = judgment.get("content_nature", "unknown")
            if not hasattr(scene, 'visual_type'):
                scene.__dict__['visual_type'] = judgment.get("visual_type", "none")
            
            if show_progress:
                status = "✅ 이미지 필요" if scene.image_required else "❌ 이미지 불필요"
                print(f"  {status} (중요도: {scene.importance:.2f})")
                print(f"  이유: {scene.context}")
            
            # 선택된 장면만 추가
            if scene.image_required:
                selected.append(scene)
        
        # 결과 요약
        self._print_summary(scenes, selected)
        
        return selected
    
    def _print_summary(self, all_scenes: List, selected_scenes: List):
        """결과 요약 출력"""
        print("\n" + "="*80)
        print("🎯 장면 선택 완료")
        print("="*80)
        
        total_duration = sum(s.duration for s in all_scenes)
        avg_interval = total_duration / len(selected_scenes) if selected_scenes else 0
        
        print(f"\n📊 통계:")
        print(f"  총 장면: {len(all_scenes)}개")
        print(f"  이미지 생성: {len(selected_scenes)}개")
        print(f"  이미지 비율: {len(selected_scenes)/len(all_scenes)*100:.1f}%")
        print(f"  평균 간격: {avg_interval:.1f}초")
        
        # 콘텐츠 타입 분포
        if selected_scenes:
            content_types = {}
            for scene in selected_scenes:
                ctype = getattr(scene, 'content_nature', 'unknown')
                content_types[ctype] = content_types.get(ctype, 0) + 1
            
            print(f"\n📚 콘텐츠 타입 분포:")
            for ctype, count in content_types.items():
                print(f"  {ctype}: {count}개")
        
        # 중요도 분포
        if selected_scenes:
            high = len([s for s in selected_scenes if s.importance >= 0.8])
            medium = len([s for s in selected_scenes if 0.5 <= s.importance < 0.8])
            low = len([s for s in selected_scenes if s.importance < 0.5])
            
            print(f"\n⭐ 중요도 분포:")
            print(f"  높음 (≥0.8): {high}개")
            print(f"  중간 (0.5-0.8): {medium}개")
            print(f"  낮음 (<0.5): {low}개")
        
        # 안전 경고
        self._safety_check(all_scenes, selected_scenes)
        
        print("="*80)
    
    def _safety_check(self, all_scenes: List, selected_scenes: List):
        """극단적인 경우 경고"""
        total_duration = sum(s.duration for s in all_scenes)
        
        if len(selected_scenes) == 0:
            print(f"\n⚠️  경고: 이미지가 하나도 선택되지 않았습니다!")
            print(f"  최소 1-2개는 필요할 수 있습니다.")
        
        elif len(selected_scenes) < max(2, total_duration / 180):
            # 3분당 1개 미만
            print(f"\n💡 참고: 이미지가 적을 수 있습니다 ({len(selected_scenes)}개)")
            print(f"  콘텐츠가 대화 위주인 경우 정상입니다.")
        
        elif len(selected_scenes) > total_duration / 10:
            # 10초당 1개 초과
            print(f"\n💡 참고: 이미지가 많을 수 있습니다 ({len(selected_scenes)}개)")
            print(f"  콘텐츠가 설명 위주인 경우 정상입니다.")
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph 노드로 실행
        
        Args:
            state: {
                "scenes": List[PodcastScene],
                "metadata": PodcastMetadata (optional),
                ...
            }
        
        Returns:
            state with selected_scenes added
        """
        scenes = state.get("scenes", [])
        metadata = state.get("metadata")
        
        if not scenes:
            print("⚠️  장면이 없습니다.")
            return {**state, "selected_scenes": []}
        
        # 메타데이터 있으면 활용
        if metadata:
            selected = self.select_scenes_with_metadata(
                scenes=scenes,
                metadata=metadata
            )
        else:
            # 메타데이터 없으면 기존 방식
            print("⚠️  메타데이터 없음 - 독립 판단 사용")
            selected = self.select_scenes(scenes)
        
        return {
            **state,
            "selected_scenes": selected,
            "image_count": len(selected)
        }
    
    def select_scenes(self, scenes: List[PodcastScene]) -> List[PodcastScene]:
        """
        기존 방식 (메타데이터 없이) - 하위 호환성
        """
        print(f"\n🎬 장면 선택 시작 (독립 판단 모드)")
        print("="*80)
        
        selected = []
        
        for scene in scenes:
            # 간단한 규칙 기반 판단
            if scene.duration >= 15:  # 15초 이상
                scene.image_required = True
                scene.importance = 0.7
                selected.append(scene)
        
        print(f"\n✅ {len(selected)}개 장면 선택 완료")
        return selected


# ============================================================================
# 헬퍼 함수들
# ============================================================================

def print_selected_scenes(scenes: List[PodcastScene]):
    """선택된 장면들 출력"""
    print("\n" + "="*80)
    print("📋 선택된 장면 목록")
    print("="*80)
    
    for scene in scenes:
        print(f"\n🎬 {scene.scene_id}")
        print(f"  시간: {scene.timestamp_start} ({scene.duration}초)")
        print(f"  화자: {scene.speaker}")
        print(f"  내용: {scene.text[:80]}...")
        print(f"  중요도: {scene.importance:.2f}")
        print(f"  이유: {scene.context}")


def export_selection_report(
    all_scenes: List[PodcastScene],
    selected_scenes: List[PodcastScene],
    output_path: str
):
    """
    선택 리포트 JSON 저장
    """
    report = {
        "total_scenes": len(all_scenes),
        "selected_scenes": len(selected_scenes),
        "selection_rate": len(selected_scenes) / len(all_scenes) if all_scenes else 0,
        "total_duration": sum(s.duration for s in all_scenes),
        "avg_interval": sum(s.duration for s in all_scenes) / len(selected_scenes) if selected_scenes else 0,
        "scenes": [
            {
                "scene_id": s.scene_id,
                "timestamp_start": s.timestamp_start,
                "duration": s.duration,
                "speaker": s.speaker,
                "text": s.text,
                "image_required": s.image_required,
                "importance": s.importance,
                "chapter_id": getattr(s, 'chapter_id', 'unknown'),
                "content_nature": getattr(s, 'content_nature', 'unknown'),
                "visual_type": getattr(s, 'visual_type', 'none'),
                "reason": s.context
            }
            for s in all_scenes
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 선택 리포트 저장: {output_path}")


if __name__ == "__main__":
    print("Scene Selection Node - 장면 선택 노드 (메타데이터 기반)")
    print("Import해서 사용하세요: from scene_selection_node import SceneSelectionNode")
