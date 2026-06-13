# MCP 서버(7B v3) 구동·확인 가이드

ai_model 폴더에서 Claude Code를 실행하면 로컬 React 어시스턴트(7B v3)가 MCP 툴로 붙습니다.

## 구동

1. `.mcp.json`이 이미 등록돼 있음(프로젝트 스코프). 별도 실행 불필요.
2. ai_model 폴더에서 Claude Code 실행:
   ```
   cd C:\Users\user\Documents\workspace\study\ai_model
   claude
   ```
3. **이미 Claude Code가 떠 있었다면 재시작**해야 새 모델 로더(7B v3)가 반영됩니다.
4. 첫 툴 호출 시 7B를 DirectML에 fp16 스트리밍 적재(~18초, VRAM ~31GB 점유, 세션 동안 유지).

## 제공 툴 (5종)

| 툴 | 용도 |
|----|------|
| `generate_react_code` | 지시문으로 React/TS 코드 생성 |
| `review_react_code` | 코드 리뷰·개선 제안 |
| `convert_to_typescript` | JS React → TS 변환 |
| `improve_code_file` | 파일 분석·개선 제안 |
| `improve_directory` | 디렉터리 일괄 분석(최대 5파일) |

사용 예(대화):
```
generate_react_code 툴로 useToggle 커스텀 훅 만들어줘
review_react_code 툴로 이 코드 리뷰해줘
```

## 동작 확인 (모델 로딩 없이/포함)

```bash
venv\Scripts\activate

# 엔드투엔드 스모크(서버 기동 → 툴 목록 → 7B 로딩+생성)
python scripts/mcp_smoke.py

# REST로도 동일 모델 서빙
python src/serve_api.py     # http://localhost:8000/docs
```

## 주의

- **stdout 청결 필수**: MCP는 stdout으로 프로토콜 통신. 서빙 경로의 모든 로그는 stderr로
  보냄(`dml_loader.py`/`model_loader.py`). stdout에 print 추가 금지.
- 시작 전 시스템 RAM 4GB+ 확보 권장(7B fp16 스트리밍 적재 피크). 로더에 RAM 가드 내장.
- 서빙 모델 경로는 `model_loader.py`의 `ADAPTER_PATH`(기본 `qwen-react-lora-7b-v3`).
  다른 버전으로 바꾸려면 이 값만 수정.
