"""
장면 묘사 노드 (LangGraph)
선택된 장면의 이미지 프롬프트 생성 (Global Visual + Scene Content)
"""

import json
import re
from typing import List, Dict, Any, Optional

# Vertex AI import
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    VERTEXAI_AVAILABLE = True
except ImportError:
    VERTEXAI_AVAILABLE = False
    print("⚠️  vertexai 패키지가 없습니다.")


# PodcastScene import
try:
    from script_parser_node import PodcastScene
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from script_parser_node import PodcastScene
    except ImportError:
        print("⚠️  script_parser_node를 찾을 수 없습니다.")
        PodcastScene = None


class SceneDescriptionNode:
    """
    장면 묘사 노드 - 이미지 프롬프트 생성
    
    기능:
    1. Global Visual Guidelines 적용
    2. Scene Visual Concept 생성
    3. Final Image Prompt 조합
    4. Composition Rules 적용 (텍스트 오버레이)
    """
    
    # 장면 묘사 프롬프트
    SCENE_DESCRIPTION_PROMPT = """당신은 AI 이미지 생성 전문가입니다.
Imagen, DALL-E, Midjourney 등의 이미지 생성 모델을 위한 프롬프트 작성 경험이 풍부합니다.

**작업:** 팟캐스트 비디오의 특정 장면을 위한 이미지 프롬프트를 생성하세요.

**Global Visual Guidelines (전체 규칙):**
```
Art Style: {art_style}
Art Details: {art_style_details}

Color Palette:
- Primary: {color_primary}
- Secondary: {color_secondary}
- Accent: {color_accent}
- Background: {color_background}

Overall Mood: {overall_mood}
Emotional Tone: {emotional_tone}

Recurring Elements:
- Character: {recurring_character}
- Motifs: {recurring_motifs}
- Icon Style: {icon_style}

Composition Rules (중요!):
- Text Position: {text_position}
- Safe Zone: {text_safe_zone}
- Preference: {composition_preference}
- Avoid: {composition_avoid}
```

**현재 장면 정보:**
```
시간: {timestamp}
내용: {scene_text}
챕터: {chapter_title}
Visual Type: {visual_type}
```

**작업 단계:**

1. **Visual Concept (시각적 개념):**
   장면 내용을 시각화 가능한 구체적인 묘사로 변환하세요.
   
   예시:
   - "TTS 기술 설명" → "Text document transforming into audio waves through TTS pipeline"
   - "사용 사례" → "Business professional using laptop with AI assistant visualization"

2. **Key Elements (주요 요소):**
   이미지에 반드시 포함되어야 할 객체들을 나열하세요.
   
   예시: ["Document icon", "Arrow flow", "Audio waveform", "API badge"]

3. **Composition (구도):**
   텍스트 오버레이 공간을 확보한 구도를 제안하세요.
   
   반드시 포함:
   - {text_safe_zone} empty for text overlay
   - {composition_preference}

4. **Final Prompt:**
   위 모든 요소를 조합하여 최종 프롬프트를 생성하세요.
   
   형식:
   ```
   [Art Style] of [Visual Concept] with [Key Elements].
   [Composition]. [Lighting/Tone].
   Color palette: [Colors].
   [Mood]. [Additional Details].
   High quality, professional.
   ```

**JSON 응답:**
```json
{{
    "visual_concept": "구체적인 시각적 개념 설명",
    "key_elements": ["요소1", "요소2", "요소3"],
    "composition": {{
        "layout": "구도 설명",
        "focal_point": "초점 위치",
        "negative_space": "{text_safe_zone} for text overlay"
    }},
    "lighting": "조명 설명",
    "final_prompt": "완성된 이미지 프롬프트 (영어)"
}}
```

**중요 규칙:**
- Final Prompt는 반드시 영어로
- Composition에 텍스트 공간 반드시 포함
- Global Visual Guidelines 스타일 유지
- 구체적이고 명확하게 (추상적 표현 피하기)
- 150-200 단어 정도
"""

    def __init__(
        self,
        project_id: str = None,
        location: str = "us-central1",
        model_name: str = "gemini-2.5-flash"
    ):
        """장면 묘사 노드 초기화"""
        # 프로젝트 ID 처리
        if project_id is None:
            import os
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
            if not project_id:
                print("⚠️  프로젝트 ID 없음 - 더미 프롬프트 생성")
        
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
    
    def generate_image_prompt(
        self,
        scene: PodcastScene,
        metadata: Any,  # PodcastMetadata
        chapter: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        단일 장면의 이미지 프롬프트 생성
        """
        if not self.model:
            return self._dummy_prompt(scene, metadata)
        
        # Visual Guidelines 추출
        visual = metadata.visual
        
        # 챕터 찾기 (없으면)
        if not chapter:
            chapter = self._find_chapter(scene, metadata.content.chapters)
        
        # 프롬프트 생성
        prompt = self.SCENE_DESCRIPTION_PROMPT.format(
            # Art Style
            art_style=visual.art_style,
            art_style_details=visual.art_style_details.get('primary', ''),
            
            # Colors
            color_primary=visual.color_palette.primary,
            color_secondary=visual.color_palette.secondary,
            color_accent=visual.color_palette.accent,
            color_background=visual.color_palette.background,
            
            # Mood
            overall_mood=visual.overall_mood,
            emotional_tone=visual.emotional_tone,
            
            # Recurring Elements
            recurring_character=visual.recurring_elements.get('character', ''),
            recurring_motifs=', '.join(visual.recurring_elements.get('motifs', [])),
            icon_style=visual.recurring_elements.get('icons_style', ''),
            
            # Composition Rules
            text_position=visual.composition_rules.text_position,
            text_safe_zone=visual.composition_rules.safe_zone,
            composition_preference=visual.composition_rules.preference,
            composition_avoid=visual.composition_rules.avoid,
            
            # Scene Info
            timestamp=scene.timestamp_start,
            scene_text=scene.text,
            chapter_title=chapter.title if chapter else "알 수 없음",
            visual_type=getattr(scene, 'visual_type', 'concept')
        )
        
        try:
            # Gemini 호출
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.7,  # 창의성 필요
                    "top_p": 0.9,
                    "max_output_tokens": 1000
                }
            )
            
            # 응답 파싱
            response_text = response.text.strip()
            response_text = re.sub(r'```json\s*', '', response_text)
            response_text = re.sub(r'```\s*', '', response_text)
            
            result = json.loads(response_text)
            return result
        
        except Exception as e:
            print(f"⚠️  프롬프트 생성 실패: {str(e)}")
            return self._dummy_prompt(scene, metadata)
    
    def generate_prompts_for_scenes(
        self,
        scenes: List[PodcastScene],
        metadata: Any,
        show_progress: bool = True
    ) -> List[PodcastScene]:
        """
        여러 장면의 이미지 프롬프트 생성
        """
        print(f"\n🎨 이미지 프롬프트 생성 시작")
        print("="*80)
        print(f"총 장면: {len(scenes)}개")
        
        for i, scene in enumerate(scenes):
            if show_progress:
                print(f"\n[{i+1}/{len(scenes)}] {scene.scene_id} 프롬프트 생성 중...")
                print(f"  내용: {scene.text[:60]}...")
            
            # 챕터 찾기
            chapter = self._find_chapter(scene, metadata.content.chapters)
            
            # 프롬프트 생성
            result = self.generate_image_prompt(scene, metadata, chapter)
            
            # Scene에 저장
            scene.image_title = result.get('visual_concept', '')[:200]
            scene.image_prompt = result.get('final_prompt', '')
            
            # 추가 메타데이터
            if not hasattr(scene, 'image_metadata'):
                scene.__dict__['image_metadata'] = {}
            
            scene.image_metadata = {
                'visual_concept': result.get('visual_concept', ''),
                'key_elements': result.get('key_elements', []),
                'composition': result.get('composition', {}),
                'lighting': result.get('lighting', '')
            }
            
            if show_progress:
                print(f"  ✅ 프롬프트 생성 완료")
                print(f"  컨셉: {scene.image_title[:80]}...")
        
        print("\n" + "="*80)
        print("✅ 프롬프트 생성 완료")
        print("="*80)
        
        return scenes
    
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
    
    def _dummy_prompt(self, scene: PodcastScene, metadata: Any) -> Dict[str, Any]:
        """더미 프롬프트 생성"""
        visual = metadata.visual
        
        # 간단한 컨셉 생성
        concept = f"Illustration representing: {scene.text[:100]}"
        
        # 최종 프롬프트
        final_prompt = f"""{visual.art_style} of an abstract concept visualization.
{visual.composition_rules.preference}.
{visual.composition_rules.safe_zone} empty for text overlay.
Color palette: {visual.color_palette.primary}, {visual.color_palette.secondary}.
{visual.overall_mood}.
High quality, professional, clean design."""
        
        return {
            'visual_concept': concept,
            'key_elements': ['Abstract shapes', 'Data visualization', 'Clean design'],
            'composition': {
                'layout': 'Top-weighted',
                'focal_point': 'Upper two-thirds',
                'negative_space': visual.composition_rules.safe_zone
            },
            'lighting': 'Bright, even lighting',
            'final_prompt': final_prompt
        }
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph 노드로 실행
        """
        selected_scenes = state.get("selected_scenes", [])
        metadata = state.get("metadata")
        
        if not selected_scenes or not metadata:
            print("⚠️  선택된 장면이나 메타데이터가 없습니다.")
            return {**state}
        
        # 프롬프트 생성
        scenes_with_prompts = self.generate_prompts_for_scenes(
            selected_scenes,
            metadata
        )
        
        return {
            **state,
            "scenes_with_prompts": scenes_with_prompts
        }


# ============================================================================
# 헬퍼 함수들
# ============================================================================

def print_prompts_summary(scenes: List[PodcastScene]):
    """생성된 프롬프트 요약 출력"""
    print("\n" + "="*80)
    print("📋 생성된 이미지 프롬프트 목록")
    print("="*80)
    
    for i, scene in enumerate(scenes, 1):
        print(f"\n{i}. {scene.scene_id} [{scene.timestamp_start}]")
        print(f"   컨셉: {scene.image_title}")
        print(f"   프롬프트:")
        print(f"   {scene.image_prompt}")
        print()


def export_prompts(scenes: List[PodcastScene], output_path: str):
    """프롬프트를 JSON 파일로 저장"""
    data = []
    
    for scene in scenes:
        data.append({
            'scene_id': scene.scene_id,
            'timestamp': scene.timestamp_start,
            'duration': scene.duration,
            'text': scene.text,
            'image_title': scene.image_title,
            'image_prompt': scene.image_prompt,
            'image_metadata': getattr(scene, 'image_metadata', {})
        })
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 프롬프트 저장: {output_path}")


if __name__ == "__main__":
    print("Scene Description Node - 장면 묘사 노드")
    print("Import해서 사용하세요: from scene_description_node import SceneDescriptionNode")
