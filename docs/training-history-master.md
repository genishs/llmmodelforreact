# 마스터 학습·채점 원장 (자동 추출)

> **성격**: 큐레이션 없이 **로그·기록 파일에서 기계적으로 추출한 원장**.
> 해석·교훈은 `docs/model-training-history.md`(정리본), 이 문서는 **근거 원본**이다.
> 추출 시점: 2026-08-03 / 근거: `gpu_jobs 로그 71개`, `comms/scores-*.jsonl`, `models/*/adapter_config.json`

---

## 1. 학습 이력 전체 17건 (시간순)

| # | 날짜 | 파라미터 | 베이스 모델 | 양자화 알고리즘 | LoRA | seq | ep | 종류 | 스텝 | 시간 | s/step | GPU | val_loss |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 07-15 | 14B | qwen2.5-coder-14b | bf16 (무양자) | r16+MLP | 1024 | — | smoke | 4 | 0.1h | 84.9 | 11.1GB | — |
| **2** | 07-15 | **32B** | qwen2.5-coder-32b | **HQQ 4bit gs64** | r16+MLP | 1024 | 2 | **본런** | 78 | 4.3h | 194.4 | 21.4GB | **0.4868** |
| **3** | 07-17 | **123B** | mistral-large-2411 | **HQQ 2bit gs64** | r16+MLP | 512 | 1 | **본런** | 39 | 5.4h | 476.2 | 40.3GB | **0.4704** |
| 4 | 07-17 | 123B | mistral-large-2411 | HQQ 2bit gs64 | r16+MLP | 512 | 1 | 짧은런 | 10 | 1.6h | 499.0 | 40.3GB | 0.9766 |
| 5 | 07-17 | 72B | qwen2.5-72b-instruct | HQQ 2bit gs64 | r16+MLP | 1024 | — | smoke | 3 | 0.3h | 400.9 | 28.0GB | — |
| **6** | 07-17 | **72B** | qwen2.5-72b-instruct | **HQQ 2bit gs64** | r16+MLP | 1024 | 1 | **본런** | 39 | 4.6h | 411.0 | **28.0GB** | **0.7963** |
| 7 | 07-17 | 72B | qwen2.5-72b-instruct | HQQ 4bit gs64 | r16+MLP | 1024 | — | smoke | 3 | 0.4h | 504.6 | 44.4GB | — |
| **8** | 07-18 | **72B** | qwen2.5-72b-instruct | **HQQ 4bit gs64** | r16+MLP | 1024 | 1 | **본런** | 39 | 5.5h | 489.9 | 44.4GB | **0.5753** |
| 9 | 07-18 | 72B | qwen2.5-72b-instruct | HQQ 4bit gs64 | r16+MLP | 1024 | 1 | 짧은런 | 10 | 1.6h | 522.9 | 44.4GB | 0.8542 |
| 10 | 07-30 | 141B(MoE) | mixtral-8x22b-v0.1 | HQQ 2bit gs64 | r16 attn만 | 512 | 1 | smoke | 8 | 0.9h | 406.9 | 43.9GB | — |
| **11** | 07-30 | **141B(MoE)** | mixtral-8x22b-v0.1 | **HQQ 2bit gs64** | r16 **attn만** | 512 | **3** | **본런** | 118 | **11.4h** | 344.0 | 43.9GB | **0.6182** |
| 12 | 07-31 | 123B | mistral-large-2411 | HQQ 2bit gs64 | r16+MLP | 512 | 1 | smoke | 8 | 0.9h | 413.3 | 40.3GB | — |
| **13** | 07-31 | **123B** | mistral-large-2411 (v2) | **HQQ 2bit gs64** | r16+MLP | 512 | 1 | **본런** | 39 | 4.7h | 417.8 | 40.3GB | **0.4642** ★최저 |
| 14 | 07-31 | 72B | qwen2.5-72b-instruct | HQQ 4bit gs64 | r16+MLP | 1024 | 1 | smoke | 8 | 0.9h | 421.9 | 44.4GB | — |
| **15** | 07-31 | **72B** | qwen2.5-72b (Q4-v2) | **HQQ 4bit gs64** | r16+MLP | 1024 | 1 | **본런** | 39 | 4.7h | 416.3 | 44.4GB | **0.5706** |
| 16 | 08-01 | 141B(MoE) | mixtral-8x22b-v0.1 | HQQ 2bit gs64 | r16 attn만 | **1280** | 1 | smoke | 8 | 1.2h | 553.5 | 44.0GB | — |
| **17** | 08-01 | **141B(MoE)** | mixtral-8x22b (킹왕짱) | **HQQ 2bit gs64** | r16 attn만 | **1280** | 2 | **본런** | 78 | 10.5h | 471.3 | 44.0GB | **0.7132** |

**합계 17건 = 본런 8 + smoke 6 + 짧은런 3 · 총 GPU 가동 ≈ 72시간**

### 공통 고정값
`group_size 64` · `lora_r 16` · `lora_alpha 32` · `grad-checkpoint 켬` · ROCm 7.13 / Ubuntu 26.04 / gfx1151

### 양자화 알고리즘 선택 근거
| 알고리즘 | 적용 | 근거 |
|---|---|---|
| bf16 (무양자) | 14B 이하 | 32B bf16 = 65GB로 통합메모리 상한 초과 |
| **HQQ 2bit gs64** | 72B · 123B · 141B | 대형 필수. 2bit이 4bit보다 **빠르고 가벼움**(대역폭 병목) |
| **HQQ 4bit gs64** | 32B · 72B | 정보보존 유리하나 무거움 |
| ~~bitsandbytes nf4~~ | **사용 불가** | gfx1151 wave32 버그 → GPU 웨지. HQQ로 우회 |

### 동일 모델 양자화 A/B (72B, seq1024, 1ep)
| | GPU | s/step | val_loss |
|---|---|---|---|
| HQQ **2bit** (#6) | **28.0GB** | **411s** | 0.7963 |
| HQQ **4bit** (#8) | 44.4GB | 490s | **0.5753** |

→ 4bit이 메모리 1.6배·시간 1.2배를 더 쓰고 val을 0.22 개선. 반면 **123B는 2bit으로 0.4704** →
**"양자화를 낮춰서라도 더 큰 모델"이 이 하드웨어에서 유리**하다는 실측 결론.

### 재현성 (같은 설정 재학습)
| 모델 | 1차 | 2차 | 차이 |
|---|---|---|---|
| 123B HQQ2 | 0.4704 (#3) | 0.4642 (#13) | −0.006 |
| 72B HQQ4 | 0.5753 (#8) | 0.5706 (#15) | −0.005 |

→ **두 건 모두 재현 성공.** 학습 파이프라인이 결정적으로 안정.

---

## 2. 채점 이력 11건 (heldout7, v2 하니스 정본)

| 라벨 | 체급 | n | v1% | **v2%** | 날짜 | max_new |
|---|---|---|---|---|---|---|
| **r7abl-noegovreal** | 7B | 7 | 80.0 | **75.0** ★최고 | 07-16 | 4096 |
| 8060-14b-v1-seq256e2 | 14B | 7 | 62.9 | **73.9** | 07-16 | 4096 |
| seed1234 | 7B | 7 | 68.6 | 72.4 | 07-16 | 4096 |
| 32b-rocm-hqq4bit | 32B | **4**⚠ | 60.0 | 72.0 | 07-16 | 4096 |
| 14b-rocm-bf16 | 14B | 7 | 60.0 | 71.5 | 07-16 | 4096 |
| r6base (옛 챔피언) | 7B | 7 | **88.6** | **71.1**⚠ | 07-16 | 4096 |
| r6admin | 7B | 7 | 74.3 | 67.7 | 07-16 | 4096 |
| 123b-hqq2-seq512 | 123B | **5**⚠ | 56.0 | 67.0 | 07-18 | 4096 |
| cap512 | 7B | 7 | 60.0 | 65.9 | 07-16 | 4096 |
| r4mlp | 7B | 7 | 71.4 | 64.9 | 07-16 | 4096 |
| **72b-q4v2-llamacpp** | 72B | 7 | 74.3 | **58.6**⚠ | 08-03 | **2048** |

### 🔴 이 표를 그대로 비교하면 안 되는 이유 (3가지)
1. **max_new 불일치** — 7B/14B/32B/123B는 **4096**, 72B(llama.cpp)만 **2048**로 채점.
   72B는 7태스크 중 3개가 토큰 상한에 걸려 잘렸고(`ho-admin-medit`, `ho-admin-mlist`, `ho-attachfile`),
   문법이 깨져 0.13~0.20으로 폭락. **잘리지 않은 4개 평균은 89.3%.**
2. **n 불일치** — 32B는 n=4, 123B는 n=5. 가장 변별력 큰 `medit`·`mlist`가 채점 타임아웃으로 빠진 **부분측정**.
3. **72B 실패 1건은 진짜 모델 문제** — `ho-attachfile`은 잘린 게 아니라 `amp;`를 447회 반복하는
   **폭주(degeneration)**로 2048토큰을 소진. 상한을 올려도 해결 안 됨.

> **결론: 현재 동일조건 비교가 가능한 것은 7B·14B(n=7, mn4096)뿐.
> 대형(32B·72B·123B·141B)은 아직 공정하게 측정된 적이 없다.**
> 전 모델 `max_new 4096` · `n=7` 재채점이 남은 과제.

### 미채점 (학습만 완료)
141B 원본(0.6182) · 141B 킹왕짱(0.7132) · 123B-v2(0.4642) · 72B HQQ2(0.7963)

---

## 3. 산출물 아카이브 위치

외장 2TB(NTFS) 단일 저장소로 통합:

```
<외장2>/ai_model/
├── models/base/       원본 3종 625GB (72B / 123B / 141B)
├── models/adapters/   어댑터 31개 8.6GB   ← 대체 불가
├── code/              scripts · src · docs · drivers · data
├── eval/              채점결과 12건 · 생성물 .tsx 323개 · scores-*.jsonl
└── logs/gpu_jobs/     학습 로그 71개 (완주 17건의 근거)
```

⚠️ **대용량 바이너리는 git에 넣지 않는다**(`.gitignore`: `models/**/*.safetensors`, `tokenizer.json`, `*.gguf`).
어댑터·GGUF는 위 아카이브에만 보관.

### 사고 기록 — 어댑터 8개 소실·복구 (2026-08-03)
`git filter-repo`로 히스토리에서 대용량 blob을 제거할 때 **워킹트리 파일까지 삭제**되어
어댑터 8개(5.3GB: 123B 챔피언 · 123B-short · 14B-rocm · 14B-v1 · 32B-hqq · 72B-hqq · 72B-hqq-q4 · 72B-q4-short)가 소실.
무손실 검증용 매니페스트를 **filter-repo 이후**에 떠서 검증이 통과해버린 것이 원인.
윈도우 백업(`bak/`)에서 전량 복구 완료.
→ **재발방지: 파괴적 작업은 작업 직전에 매니페스트를 뜨고 작업 직후 대조한다.**

---

## 4. 재추출 방법

```bash
# 학습 이력
python3 - <<'PY'
import re, glob, os
for p in sorted(glob.glob("logs/gpu_jobs/*.log")):
    t=open(p, errors='ignore').read()
    m=re.search(r'종료: (\d+) steps, 총 ([\d.]+)s, 평균 ([\d.]+)s/step', t)
    if not m: continue
    print(os.path.basename(p), m.groups(),
          re.findall(r'\[epoch \d+/\d+\] val_loss ([\d.]+)', t))
PY

# 채점 이력
python3 -c "
import json,glob
for p in glob.glob('comms/scores-*.jsonl'):
    for l in open(p, errors='ignore'):
        if l.strip().startswith('{'):
            r=json.loads(l)
            if 'pct_v2' in r: print(r['label'], r.get('n_tasks'), r.get('pct_v1'), r.get('pct_v2'))
"
```
