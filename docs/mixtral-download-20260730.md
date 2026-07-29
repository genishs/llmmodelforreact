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
