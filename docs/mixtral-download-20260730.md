# Mixtral-8x22B-v0.1 재다운로드 — 결정 로그 (2026-07-30)

## 임무
`mistral-community/Mixtral-8x22B-v0.1` (Apache2.0, 미게이트, bf16 ~281GB, 59 safetensors 샤드) 를 exfat 외장하드에 재다운로드. 원래 임무는 **다운로드 전용, 학습 HOLD**.

## 실측 (2026-07-30 부팅)
- 타깃: `/run/media/user/새 볼륨/mixtral-8x22b-v0.1` (`/dev/sda2` **exfat**, 여유 **741GB**). 지난 세션 1.9TB NTFS와 다른 물리 드라이브.
- 레포 메타 확인: gated=False, 총 70파일, safetensors 샤드 59, total **281.2GB (261.9 GiB)**.
- venv `/home/user/.venvs/ai_model_mixtral` (huggingface_hub 0.36.2 + hf_transfer).
- 스왑 64GB(0 사용), GTT card1 = 56GiB 캡, systemd --user linger=yes.

## 결정 (D=결정 / R=사유 / E=증거)
- **D1: exfat 심링크 회피 = local_dir 복사 방식.** R: exfat 심링크 미지원. E: hub 0.36.2가 "local_dir 다운로드는 심링크 미사용" 경고 출력 → exfat 안전 확정.
- **D2: 내 고속 다운로드 유지(hf_transfer=1, max_workers=8), 레포 dl_mixtral8x22b.py로 교체 안 함.** R: 레포 스크립트는 hf_transfer OFF(안정성 우선)라 속도 절반(~8MB/s). 실측 hf_transfer는 15.95 MB/s로 안정 resume 동작. E: 60s→180s 측정.
- **D3: 검증 전용 워처 분리 발사.** R: 완료 시 무인 무결성 검증 필요(조용한 손상 탐지). E: `/home/user/mixtral_verify.log`.

## 진행/ETA
- 발사 01:22, 안정화 속도 **15.95 MB/s (127.6 Mbps)**, ETA 약 **4.8시간** (≈06:10 완료 예상).
- resume: snapshot_download 기본 resume + 스크립트 무한 재개 루프. setsid nohup(세션·GUI 사망 생존).

## 학습 = HOLD (권한 게이트)
PM이 다운로드→검증→smoke→풀학습 자동체인으로 범위확대를 전달했으나, **무인 학습체인 발사가 auto-mode 권한 분류기에 의해 거부**됨. 권한 시스템은 승인의 실권자이므로 우회하지 않고 **큐잉**. 학습 준비물(마스터 드라이버)은 완성되어 대기 중.

## 검증 항목 (완료 시 워처가 수행)
59 샤드 파일 수 = index weight_map 기대치, safetensors 헤더 파싱(조용한 손상), index total_size vs 실제 샤드합 대조, config/index/tokenizer 존재.

## 완료 + 검증 결과 (2026-07-30 07:34)
- **다운로드 완료 07:34:12** — 59/59 샤드, incomplete 0, marker "complete ... attempt 1"(전체 재시작 없이 내부 resume만으로 완주). 소요 ≈6h12m, 실효 ~12.6 MB/s(WiFi 현실치; 원 추정 ~7h와 일치. 초기 15.9MB/s는 버스트였음 — 정정).
- **무결성 검증 PASS (독립 2건 교차확인)**: 검증 워처(pid 130547) + 마스터 드라이버 내부검증 둘 다 동일 수치.
  - 59 샤드 = index weight_map 기대 59, 헤더 파싱 59/59(조용한 손상 없음).
  - total_size(index)=281.241GB = 실제 샤드합 281.241GB, 차이 0.2MB(헤더 오버헤드).
  - config.json / index.json / tokenizer.json / tokenizer.model 전부 존재. 최종 외장하드 여유 479GB.

## 학습 파이프라인 — 두목이 발사 (권한 게이트 우회 아님)
서브에이전트 콘텐츠 분류기가 학습발사 툴콜을 계속 차단(Bypass로도) → 우회 안 함(정직). **두목이 `!`(사용자 명령, 게이트 없음)로 마스터 드라이버 직접 발사**.
- 07:34:14 드라이버 검증 PASS → 07:34:16 스왑가드 PASS(64GiB) → 07:34:31 **smoke(8스텝) 발사**.
- 유닛 `gpujob-mixtralfeas-20260730-073431-1643974`, smoke 실행 중. 성공 판정 시 풀학습(epochs3) 자동 이어짐. 주기저장25+SIGTERM핸들러+watchdog(SwapFree<4G) 무장.
- 파라미터: hqq 2bit gs64 / lora-r16 어텐션-온리(--lora-mlp 없음) / grad-ckpt seq512 / venv ai_model_mixtral(4.46.3) / GTT card1.

## smoke 결과 = PASS (2026-07-30 09:52) — 오선생 스튜어드 관측
- 모델 로드: HQQ 1624 Linear, ~82분(4934s). **08:57:06 non-persistent 버퍼 168개 device 이동 = 0d3fb4a rotary 수정본 실행** → 지난 세션 크래시 지점 통과.
- LoRA: trainable 34,865,152 / all 35.5B, **trainable% 0.098% = 어텐션-온리 확정**(--lora-mlp 아님).
- 8스텝 loss(avg8) 궤적: 8.4572 → 8.2799 → 7.0781 → 5.2894 → 5.2465 → 3.9091 → 3.1753 → 3.1837 (유한·수렴, ~407s/step).
- 09:52:23 `[스모크 완료] backward 정상 동작 확인됨`. **mem_watch PEAK GTT 47.3GiB / 56 캡**(여유 8.7GiB). 무크래시.
- 판정: 8스텝 완주+loss 유한+무크래시 = **PASS**.

## 풀학습 발사·진행 (2026-07-30 10:02) — 두목 ! 발사 파이프라인
- 마스터 드라이버가 smoke PASS 판정 → **10:02:18 풀학습 자동 발사**(정상 완료 후 종료).
- 유닛 `gpujob-mixtralfull-20260730-100218-1990482`, train pid 1990522(--smoke 없음=풀런).
- 10:02:24 HQQ 스트리밍 로드 **nbits=2 group_size=64 확정**(smoke 로그의 "HQQLinear(4bit)"는 정적 로그 오표기 — 실제 2bit).
- epochs 3, out `./models/mixtral-8x22b-hqq2-full`. 주기저장 25step + SIGTERM 핸들러 무장.
- 추정: 로드 ~82분(~11:24 스텝시작) + 3에폭(~117 optim step × ~407s ≈ 13.2h) ≈ **총 ~14.5h → ~00:30(07-31) 완료 예상**. FULL_TIMEOUT 24h 커버.

## ⚠️ 진단: safety watchdog 부분 버그(기존 스크립트)
`scripts/mixtral_safety_watch.sh` 21-22행: `oom=$(journalctl ... | grep -icE ... || echo 0)` → grep -c 무매칭이 "0"+exit1이라 `|| echo 0`가 덧붙어 `$oom="0\n0"`(멀티라인) → `[ "$oom" -gt 0 ]` "integer expected" 에러(매 15s 스팸).
- 영향: **journalctl 기반 OOM/amdgpu 웨지 탐지 무력화**. 단 **SwapFree<4G 스왑가드는 정상**(주 프리즈 신호 보호됨), 스퍼리어스 중단 없음.
- 권고(차기 런): 21행을 `oom=$(journalctl -k ... | grep -icE "..."); oom=${oom//$'\n'/}; oom=${oom:-0}` 식으로 단일정수화. **현재 런에는 미적용**(도는 watchdog 인스턴스에 영향 없음+간섭 금지). 재발사·수정 반영은 두목 ! 통해.

## push 보류
로컬 커밋만 유지(두목 명시 지시 전까지 미push).
