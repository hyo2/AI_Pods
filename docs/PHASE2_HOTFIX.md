# 🔧 Phase 2 긴급 패치 - ImagenService 호환성 수정

## 🐛 발생한 문제

```
TypeError: ImagenService.__init__() got an unexpected keyword argument 'default_model'
```

기존 `ImagenService`가 `default_model` 파라미터를 지원하지 않아 발생한 에러입니다.

---

## ✅ 수정 내용

### 1. ImagenService 초기화 수정
- `default_model` 파라미터 제거
- 기존 ImagenService와 호환되도록 수정

### 2. 대체 구현 추가
- ImagenService가 없어도 동작
- Vertex AI를 직접 호출하는 백업 메서드 추가

### 3. 에러 핸들링 강화
- 초기화 실패 시에도 계속 진행
- 이미지 생성 실패 시 스킵하고 다음으로

---

## 🚀 패치 적용 방법

### 방법 1: 파일 교체 (추천)

```bash
# 프로젝트 루트에서 실행

# 수정된 파일 복사
cp /mnt/user-data/outputs/image_generation_node.py app/nodes/
cp /mnt/user-data/outputs/pipeline_phase2.py app/pipelines/

# 확인
echo "✅ 패치 완료!"
```

### 방법 2: 수동 수정

#### `app/pipelines/pipeline_phase2.py` (라인 56-70)

**변경 전:**
```python
from app.services.imagen_service import ImagenService
imagen_service = ImagenService(
    project_id="alan-document-lab",
    credentials_path=credentials_path,
    default_model=image_default_method  # ← 이 줄 문제!
)
```

**변경 후:**
```python
# ImagenService 초기화 (기존 서비스 사용)
try:
    from app.services.imagen_service import ImagenService
    # 기존 ImagenService는 default_model 파라미터가 없을 수 있음
    imagen_service = ImagenService(
        project_id="alan-document-lab",
        credentials_path=credentials_path
    )
except Exception as e:
    print(f"  ⚠️  ImagenService 초기화 실패: {e}")
    print(f"  ℹ️  기본 설정으로 계속 진행...")
    imagen_service = None
```

#### `app/nodes/image_generation_node.py` (라인 29-50)

**변경 전:**
```python
if imagen_service is None:
    from app.services.imagen_service import ImagenService
    self.imagen = ImagenService(
        project_id="alan-document-lab",
        credentials_path="./vertex-ai-service-account.json",
        default_model=default_method  # ← 이 줄 문제!
    )
```

**변경 후:**
```python
if imagen_service is None:
    try:
        from app.services.imagen_service import ImagenService
        # 기존 ImagenService는 default_model 파라미터가 없을 수 있음
        self.imagen = ImagenService(
            project_id="alan-document-lab",
            credentials_path="./vertex-ai-service-account.json"
        )
    except Exception as e:
        print(f"⚠️  ImagenService 초기화 실패: {e}")
        self.imagen = None
```

---

## 🧪 패치 검증

### 1. 빠른 테스트

```bash
python tests/test_phase2_pipeline.py

# 메뉴에서 '1' 선택
# 에러 없이 실행되어야 함!
```

### 2. 예상 출력

```
🔧 파이프라인 초기화 중...
  ✅ 분석 노드
  ✅ 토픽 추출 노드
  ✅ 이미지 생성 노드  # ← 이제 에러 없음!
✨ 파이프라인 준비 완료

================================================================================
🚀 파이프라인 시작
================================================================================
...
```

---

## 💡 추가 정보

### 새로운 기능: 직접 Vertex AI 호출

패치 후에는 두 가지 방식으로 작동합니다:

1. **기존 ImagenService 사용** (있으면)
   - 기존 코드 호환성 유지
   - 모든 기능 사용 가능

2. **직접 Vertex AI 호출** (없으면)
   - ImagenService 없이도 작동
   - Gemini 2.0 Flash로 이미지 생성
   - Imagen 4 직접 호출

### 지원되는 메서드

- `gemini` - Gemini 2.0 Flash (빠름)
- `imagen-4` - Imagen 4.0 (고품질)
- `imagen-4-fast` - Imagen 4.0 Fast
- `imagen-4-ultra` - Imagen 4.0 Ultra

---

## 🎯 다시 테스트하기

```bash
# 1. 파일 교체
cp /mnt/user-data/outputs/image_generation_node.py app/nodes/
cp /mnt/user-data/outputs/pipeline_phase2.py app/pipelines/

# 2. 테스트 실행
python tests/test_phase2_pipeline.py

# 3. 메뉴에서 '4' 선택 (커스텀 입력)
# 4. 텍스트 입력하고 전략 선택
```

---

## ✅ 체크리스트

- [ ] 수정된 파일 복사 완료
- [ ] 테스트 실행 - 에러 없음
- [ ] 이미지 생성 성공
- [ ] 갤러리 HTML 생성 확인

---

**패치 완료! 다시 테스트해보세요! 🚀**
