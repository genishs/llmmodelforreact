# React Coding Assistant (로컬 LLM)

AMD Ryzen AI Max+ 392 (12코어, Radeon 8060S) 위에서 직접 학습하고 실행하는 React 특화 로컬 코딩 어시스턴트

---

## 시스템 스펙

| 항목 | 사양 |
|------|------|
| CPU | AMD Ryzen AI Max+ 392 (Zen 5, 12코어 / 24스레드, 3.2GHz) |
| Memory | 64GB 통합 메모리 (CPU+GPU 공유, 실사용 47GB) |
| GPU | AMD Radeon 8060S (DirectML, 현재 16GB 할당) |
| NPU | XDNA 2 |
| OS | Windows 11 |

> Apple Silicon과 유사한 통합 메모리 구조 → GPU 할당량을 64GB까지 확장 가능

---

## 모델 정보

| 항목 | 내용 |
|------|------|
| 베이스 모델 | Qwen2.5-Coder-1.5B-Instruct |
| 학습 방식 | LoRA (rank=16, alpha=32) |
| 학습 가능 파라미터 | 약 4.4M / 전체 1.55B (0.28%) |
| 학습 데이터 | React Q&A 84개 (직접 작성 10 + GitHub 수집 74) |
| 최신 모델(1.5B) | `models/qwen-react-lora-v4` |
| **서빙 모델(API/MCP)** | **`models/qwen-react-lora-7b-v4`** (Qwen2.5-Coder-**7B** + LoRA, fp16) |
| GPU 백엔드 | DirectML (AMD GPU on Windows) |

> API 서버(`serve_api.py`)와 MCP 서버(`mcp_server.py`)는 `model_loader.py`를 통해
> **7B v4**를 DirectML에 fp16 스트리밍 적재해 서빙합니다(VRAM ~31GB). 7B 학습·데이터
> 큐레이션 상세는 `docs/training-benchmark-7b.md` 참고.

---

## 빠른 시작

### 1. 환경 활성화

```bash
cd C:\Users\user\Documents\workspace\study\ai_model
venv\Scripts\activate
```

### 2. 환경 확인

```bash
python src/check_env.py
```

정상 출력 예시:
```
[OK] Python 3.11.9
[OK] PyTorch 2.4.1
[OK] DirectML - AMD Radeon 8060S Graphics
[OK] Transformers 5.4.0
[OK] PEFT (LoRA) 0.18.1
```

---

## 사용 방법

### 방법 1: CLI 대화형 모드

```bash
python src/inference.py
```

```
=== React 코딩 어시스턴트 ===
질문: useReducer로 장바구니 기능 만들어줘
추가 컨텍스트 (없으면 Enter):
[생성 중...]
[응답] ...
```

### 방법 2: REST API 서버

```bash
# 서버 시작
python src/serve_api.py
# 또는 scripts\start_api.bat 더블클릭
```

- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

**API 호출 예시 (fetch)**

```typescript
const res = await fetch('http://localhost:8000/generate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    instruction: 'useCallback으로 최적화된 리스트 컴포넌트 만들어줘',
    input: '',          // 추가 컨텍스트 (선택)
    max_new_tokens: 512
  })
});
const { response } = await res.json();
```

**API 호출 예시 (Python)**

```python
import requests

res = requests.post('http://localhost:8000/generate', json={
    'instruction': 'React Query로 데이터 페칭하는 컴포넌트 작성해줘',
})
print(res.json()['response'])
```

### 방법 3: MCP 서버 (Claude Code 통합)

`ai_model` 폴더에서 Claude Code 실행 시 자동으로 MCP 서버가 활성화됩니다.

```bash
# ai_model 폴더에서 Claude Code 실행
cd C:\Users\user\Documents\workspace\study\ai_model
claude
```

활성화 후 Claude Code 대화에서:
```
"generate_react_code 툴로 무한 스크롤 컴포넌트 만들어줘"
"review_react_code 툴로 이 코드 리뷰해줘"
"convert_to_typescript 툴로 이 JS 코드 TS로 변환해줘"
```

MCP 설정 파일: `.mcp.json`

---

## 프로젝트 구조

```
ai_model/
├── .mcp.json                    # MCP 서버 등록 (Claude Code용)
├── requirements.txt
├── config/
│   └── training_config.yaml     # 학습 하이퍼파라미터
├── data/
│   ├── raw/
│   │   └── github_react_qa.jsonl   # GitHub 수집 데이터
│   └── processed/
│       ├── react_train.jsonl       # 학습 데이터 (75개)
│       └── react_val.jsonl         # 검증 데이터 (9개)
├── models/
│   ├── base/
│   │   └── qwen2.5-coder-1.5b/  # 베이스 모델 (다운로드)
│   ├── qwen-react-lora-v1/      # 연습 (4개 샘플)
│   ├── qwen-react-lora-v2/      # 직접 작성 10개
│   ├── qwen-react-lora-v3/      # GitHub 추가 19개
│   └── qwen-react-lora-v4/      # 최신 (84개, 26분 학습) ← 사용 중
├── scripts/
│   ├── setup.md                 # 환경 설정 가이드
│   ├── install.bat              # 패키지 설치
│   ├── start_api.bat            # REST API 서버 실행
│   └── start_mcp.bat            # MCP 서버 단독 실행
├── src/
│   ├── check_env.py             # 환경 확인
│   ├── model_loader.py          # 모델 싱글턴 (API/MCP 공용)
│   ├── prepare_data.py          # 샘플 데이터 생성
│   ├── collect_github_data.py   # GitHub 코드 수집
│   ├── build_dataset.py         # 데이터셋 병합/정제
│   ├── train.py                 # LoRA 학습
│   ├── inference.py             # CLI 추론
│   ├── serve_api.py             # FastAPI REST 서버
│   └── mcp_server.py            # MCP 서버
└── venv/                        # 가상환경
```

---

## 학습 파이프라인

```
1. 데이터 수집
   python src/collect_github_data.py --token YOUR_TOKEN

2. 데이터셋 구축
   python src/build_dataset.py

3. 학습
   python src/train.py           # config/training_config.yaml 참고

4. 추론 테스트
   python src/inference.py
```

---

## 버전 히스토리

| 버전 | 데이터 | train_loss | eval_loss | 특이사항 |
|------|--------|-----------|-----------|---------|
| v1 | 4개 | 0.634 | - | 초기 연습 |
| v2 | 10개 | 0.496 | 0.607 | 직접 작성 고품질 |
| v3 | 19개 | 0.628 | 0.533 | GitHub 9개 추가 |
| v4 | 84개 | 0.734 | 0.769 | **현재 사용**, 26분 학습 |

---

## 다음 단계 (Phase 2~4)

- [ ] GPU 할당 확대 (16GB → 32GB+) 후 재학습
- [ ] 학습 데이터 확대 (목표: 500개+)
- [ ] Qwen2.5-Coder-7B 모델로 업그레이드
- [ ] 현재 작업 중인 React 프로젝트 코드 컨텍스트 주입 (RAG)
- [ ] VSCode Extension 연동

---

## 주요 기술 스택

| 용도 | 라이브러리 |
|------|----------|
| GPU 가속 (AMD) | torch-directml |
| 모델/토크나이저 | transformers 5.4 |
| LoRA 학습 | peft 0.18 |
| 데이터 처리 | datasets 4.8 |
| REST API | FastAPI + uvicorn |
| MCP 서버 | mcp 1.26 |
