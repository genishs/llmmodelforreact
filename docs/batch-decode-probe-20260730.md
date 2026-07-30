# 배치 디코드 프로브 재개 — 결정 로그 (2026-07-30, 재부팅 후)

## 임무
`scripts/batch_decode_probe.py`(이슈 #9, 커밋 667be1e)를 실제 GPU에서 실행해 batch=1 vs batch=N
throughput 배수를 실측한다. 직전 세션에서 스왑 부족(15GiB) 상태로 프로브를 시작했다가
OS 재부팅으로 중단됐다. 이 로그는 재부팅 후 재개 과정의 진단·결정을 기록한다.

## 선행조건 확인
- **스왑**: 재부팅 직후 이미 복구되어 있었다 — `swapon --show` = `/dev/nvme0n1p3`(15.3G) +
  `/swapfile`(49G) = **64GiB, 0 사용**. RAM 56Gi 가용. 폴링 불필요, 즉시 진행.
- **EGOV_SRC**: `eval_hard_tsc.py`/`score_v2.py`의 하드코딩 후보 경로(`.../egovGeoportal/src`)는
  이 장비에 존재하지 않는다 — 2026-07 리네임([[twinspace-repos-renamed-2026-07]])으로
  `egovGeoportal` → `sysadmin-front`. 실제 정본:
  ```
  export EGOV_SRC="/mnt/data/Documents/workspace/twinspace_platform/sysadmin-front/src"
  ```
  heldout7 앵커 7개 전부 존재 확인(EgovSelect.jsx, EgovImageGallery.jsx,
  EgovAboutOrganization.jsx, EgovAttachFile.jsx, EgovAdminDataAccessEdit.jsx,
  EgovAdminMemberList.jsx, EgovAdminMemberEdit.jsx). `gen_batch_utils.py` 헤더 주석에 이미
  같은 경로가 언급되어 있어 직전 세션 결론과 일치.
- **123B 베이스(mistral-large-2411) 상태**: 오선생이 재다운로드 중(pid 9773,
  `ai_model_mixtral` venv, 51개 샤드 중 7개 완료, 토크나이저 파일 아직 없음) — **미완료 확인,
  건드리지 않음**. `qwen-react-lora-123b-hqq`의 `adapter_config.json`을 확인해
  `base_model_name_or_path = ./models/base/mistral-large-2411`임을 검증 — 어댑터 단독으로는
  채점 불가, 반드시 베이스 완주 후로 순연.

## 재부팅 전 시도 3건 사후 진단 (로그: `~/gpu_jobs/logs/gpujob-bdprobe*-20260730-22*.log`)
1. `bdprobe123b`(22:55) — 5초만에 실패. `mistral-large-2411` 베이스에 토크나이저 파일이
   아직 없고(다운로드 미완료), `ai_model_rocm` venv에 `sentencepiece` 미설치 →
   `AutoTokenizer.from_pretrained` 가 slow→fast 변환 불가로 크래시. 어차피 베이스 미완료라
   지금 재시도 대상 아님.
2. `bdprobe141b`(22:57) — 17초만에 실패. `gpu_job.sh`가 커맨드에 `python`만 주면
   **하드코딩된 기본 venv(`ai_model_rocm`, transformers 신버전)를 PATH에 태운다** — 학습에 쓴
   `ai_model_mixtral`(4.46.3)과 클래스 구조가 달라 `MixtralDecoderLayer`에
   `block_sparse_moe` 속성이 없다는 AttributeError. **교훈: mixtral 계열은 반드시
   `/home/user/.venvs/ai_model_mixtral/bin/python`을 커맨드에 명시.**
3. `bdprobe141bv2`(22:58) — venv 올바르게 명시, HQQ 양자화 진행 중(100/1624 Linear,
   RAM 가용 49~51GB 안정) 이었으나 **재부팅으로 SIGTERM(exit 143)** — 웨지 아님(커널 로그
   깨끗), 로직도 정상 진행 중이었다. 그대로 재실행하면 된다.

## 재개 (23:24 발사)
```
scripts/gpu_job.sh --name bdprobe141bv3 --timeout 9000 \
  --cwd "/mnt/data/Documents/workspace/study/ai_model" -- \
  /home/user/.venvs/ai_model_mixtral/bin/python scripts/batch_decode_probe.py \
  --base "/run/media/user/새 볼륨/mixtral-8x22b-v0.1" \
  --hqq-nbits 2 --hqq-group-size 64 --max-new 32 --batches 1 2 4
```
- venv `ai_model_mixtral` 명시(위 교훈 반영), `--timeout 9000`(2.5h) — smoke 로그 기준
  HQQ 로드 자체가 ~82분(4934s) 걸리므로 기본 3600s로는 로드 중 타임아웃킬 위험.
- 유닛: `gpujob-bdprobe141bv3-20260730-232447-11453.service`, 로그:
  `~/gpu_jobs/logs/gpujob-bdprobe141bv3-20260730-232447-11453.log`.
- 23:25:04 비양자화 텐서 115개 로드 완료(RAM 가용 52.9GB) — v2와 동일 궤적으로 정상 진행 확인.
- 결과(배치=N 배수, peak GPU mem)는 완료 후 별도 기록 예정.

## 141B 학습 상태 참고 (프로브와 별개, 이미 완료)
`gpujob-mixtralfull-20260730-100218-1990482` 이 22:48:44에 **정상 완료**(exit 0, 118 step,
val_loss 0.6182, 무웨지) — `models/mixtral-8x22b-hqq2-full`은 최종 저장본. 프로브 대상
`--base`가 원본 bf16(mixtral-8x22b-v0.1)인 이유는 배치 디코드 배수 측정이 로드 방식(HQQ
스트리밍)만 재현하면 되고 학습된 LoRA 유무와 무관하기 때문 — 채점 실행 시에는 이 어댑터를
얹어서 별도로 돌린다.

## push 보류
로컬 커밋만 유지(두목 명시 지시 전까지 미push).
