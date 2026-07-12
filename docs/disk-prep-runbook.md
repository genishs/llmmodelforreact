# D: 축소 런북 — ROCm 듀얼부팅용 미할당 공간 확보 (사용자 직접 실행)

> 작성 2026-07-12 (8060). 목적: Ubuntu 24.04 + ROCm 7.2 베어메탈 듀얼부팅을 위해 **Disk 1 (D:)에서
> 150~200GB 미할당 공간**을 확보. 이 문서는 **사용자가 관리자 권한으로 직접 실행**하는 절차다.
> 상위 설계·설치 전체 흐름은 `docs/rocm-linux-dualboot-plan.md` 참조. **설치 후 검증**은 이 문서 맨 끝.

## ⛔ 왜 사용자가 직접 해야 하나
- Claude 자동화 세션은 **비관리자** → `Get-PartitionSupportedSize` / `Resize-Partition`이 CIM 접근 거부로 실패.
- 디스크 축소는 **파괴 위험이 있는 비가역 작업** → 자동승인 훅 범위 밖(SCM 룰상 명시적 사용자 확인 대상).
- 따라서 아래 명령은 **사용자가 "관리자 권한 PowerShell"** (시작 → PowerShell 우클릭 → 관리자로 실행)에서 수행.

## 현재 디스크 현실 (2026-07-12 실측)

| Disk | 모델 | 문자 | 용량 | 여유 | 역할 |
|---|---|---|---|---|---|
| 0 | SAMSUNG MZVL81T0HFLB | **C:** | 953.9GB | 291GB | Windows. **절대 미접촉** |
| 1 | GIGABYTE GP-AG41TB | **D: 새 볼륨** | 931.5GB | **421GB** | **축소 대상** (활성 데이터 드라이브) |

**D:는 빈 볼륨이 아니다.** Windows 셸 폴더가 D:로 이전되어 실사용 중 (실측 상위 폴더):

| 폴더 | 크기 |
|---|---|
| Saved Games | **234GB** ← 가장 큼, 게임 세이브 |
| Downloads | 97GB |
| Desktop | 69GB |
| Documents | 28GB |
| SteamLibrary | 27GB |
| Videos | 22GB |
| Pictures | 20GB |
| XboxGames | 7GB |

**목표: D: 끝에서 150~200GB 미할당 확보.** 여유가 421GB이므로 축소 후에도 220GB+ 남아 활성 사용에 지장 없음.
(14B fp16 스냅샷 29GB + 20B/32B 4bit 스냅샷 + 복수 LoRA 어댑터 + 데이터셋 + ROCm 툴체인 + Linux swap을
넉넉히 담으려면 150GB가 하한, 200GB면 여유. 미할당은 Ubuntu 설치 시 ext4 root + swap으로 분할.)

---

## 절차 (관리자 PowerShell, 순서대로)

### ① ⚠️ 백업 체크리스트 (축소 전 반드시)
축소는 이론상 데이터를 옮기지만, **정전·중단·이동불가 파일 충돌 시 손상 위험**이 있다. 아래를 먼저:
- [ ] **Saved Games (234GB)** — 게임 세이브. 클라우드 동기화(Steam Cloud 등) 확인 또는 외장 백업.
- [ ] **Desktop (69GB) / Documents (28GB)** — 작업 파일. OneDrive/외장으로 백업.
- [ ] **Downloads (97GB)** — 재다운로드 가능한 것은 이 참에 정리하면 축소 여유↑.
- [ ] 열려 있는 프로그램·게임 **모두 종료** (D: 파일 잠금 해제 → 축소 상한↑).
- [ ] 중요 데이터가 **D: 한 곳에만** 있지 않은지 확인. (BitLocker면 복구키 보관 확인.)

### ② 현재 상태 확인 (읽기 전용, 안전)
```powershell
Get-Volume | Where-Object DriveLetter -in 'C','D' |
  Select-Object DriveLetter, FileSystemLabel,
    @{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}},
    @{n='FreeGB';e={[math]::Round($_.SizeRemaining/1GB,1)}}
Get-Disk | Select-Object Number, FriendlyName,
  @{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}}, PartitionStyle
```

### ③ 축소 상한 실측 (핵심 — 이동불가 파일 때문에 421GB보다 작을 수 있음)
```powershell
$s = Get-PartitionSupportedSize -DriveLetter D
"현재크기 : {0} GB" -f [math]::Round($s.SizeMax/1GB,1)
"최소크기 : {0} GB" -f [math]::Round($s.SizeMin/1GB,1)
"→ 축소가능 최대 : {0} GB" -f [math]::Round(($s.SizeMax - $s.SizeMin)/1GB,1)
```
- `SizeMax - SizeMin` = **지금 당장 잘라낼 수 있는 최대량**. 여유가 421GB라도 페이지파일·MFT·복원지점 등
  **이동불가 파일이 볼륨 끝쪽에 박혀 있으면 이 값이 훨씬 작게** 나온다. 200GB 미만이면 ④ 조각모음 후 재측정.

### ④ 조각모음 (이동불가 파일을 앞당겨 축소 상한↑)
```powershell
Optimize-Volume -DriveLetter D -Defrag -Verbose
# 필요 시(SSD라도 shrink 목적의 조각통합엔 유효):
# Optimize-Volume -DriveLetter D -Defrag -SlabConsolidate -Verbose
```
- 완료 후 **③을 다시 실행**해 축소가능 최대가 목표(150~200GB) 이상인지 확인.
- 그래도 부족하면: 페이지파일 임시 이동(시스템 속성 → 고급 → 가상 메모리 → D: 페이지파일 없음으로),
  시스템 복원 지점 정리(`vssadmin delete shadows`는 신중), 최대절전 파일 정리 후 재측정.

### ⑤ 축소 실행 — 두 방법 중 택1

**방법 A — GUI (권장, 안전·직관적):**
1. `Win + R` → `diskmgmt.msc` → 엔터.
2. **Disk 1 의 D: (새 볼륨)** 우클릭 → **볼륨 축소(Shrink Volume)**.
3. "축소할 공간 입력(MB)"에 **153600** (=150GB) ~ **204800** (=200GB) 입력.
   - 이 칸의 상한이 곧 실축소 가능량. 원하는 값보다 작으면 ④ 조각모음/이동불가 파일 정리 후 재시도.
4. **축소** → D: 뒤에 **"할당되지 않음(Unallocated)"** 검정 막대가 생기면 성공. **여기에 새 볼륨 만들지 말 것**
   (Ubuntu 설치 관리자가 ext4/swap로 사용).

**방법 B — PowerShell (정확한 크기 지정):**
```powershell
# 예: D:를 목표 최종크기로 축소해 ~180GB 미할당 확보.
# 최종크기 = 현재크기 - 확보할공간. 아래는 180GB 확보 예시(731.5GB로 축소).
$targetGB = 731.5
Resize-Partition -DriveLetter D -Size ([uint64]($targetGB * 1GB))
```
- `Resize-Partition`은 GUI와 동일 엔진. 목표 `-Size`가 `SizeMin`보다 작으면 에러 → ③값 안에서 지정.
- **미할당 확보량 = (축소 전 크기 − 지정 -Size)**. 180GB 확보하려면 `-Size (현재크기 − 180GB)`.

### ⑥ 검증 (읽기 전용)
```powershell
Get-Disk -Number 1 | Select-Object Number, FriendlyName,
  @{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}}
# Disk 1 파티션 목록 + 미할당 확인
Get-Partition -DiskNumber 1 |
  Select-Object PartitionNumber, DriveLetter, Type,
    @{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}},
    @{n='OffsetGB';e={[math]::Round($_.Offset/1GB,1)}}
# 미할당 크기 = 디스크 전체 - 파티션 합계
$disk = Get-Disk -Number 1
$used = (Get-Partition -DiskNumber 1 | Measure-Object Size -Sum).Sum
"미할당 : {0} GB" -f [math]::Round(($disk.Size - $used)/1GB,1)
```
- **"미할당 : ~150~200 GB"** 가 나오면 완료. diskmgmt.msc에서도 D: 뒤 검정 "할당되지 않음" 막대로 재확인.

---

## 축소 완료 후 — 다음 단계

미할당 확보가 끝나면 **물리 설치 단계**로 넘어간다. 이 부분은 Claude가 못 하는(부팅 전 GUI·BIOS) 영역이 많다.

**사용자가 직접 (부팅·BIOS·파티셔닝):**
1. Ubuntu 24.04.3 LTS USB 부팅 → **미할당 공간에** 설치 (C: Windows 유지, GRUB 듀얼부팅).
   BIOS Secure Boot off 권장, 부팅순서 USB 우선.
2. 커널 6.14 HWE 핀 고정 → `docs/rocm-linux-dualboot-plan.md` 1단계 그대로.

**Claude가 스테이징 가능 (문서·스크립트·검증 레시피 사전 준비):**
- ROCm 7.2 설치 명령 블록, TheRock gfx1151 휠 index, 검증 스크립트를 Linux 진입 즉시 복붙 가능하게 정리.
- 우리 코드(`src/train_directml.py --backend cuda`)는 이미 ROCm 대비 완료 → git clone 후 바로 사용.

---

## 설치 후 검증 시퀀스 (요약 — 정본은 `rocm-linux-dualboot-plan.md` 2~4단계)

Linux 진입 후 순서:
1. **ROCm 7.2** 설치 → `rocminfo` 로 **gfx1151 인식** 확인. (dualboot-plan 2단계)
2. **PyTorch = TheRock gfx1151 nightly** (`--index-url https://rocm.nightlies.amd.com/v2/gfx1151/`).
   ⚠️ 제네릭 nightly는 gfx1151서 **세그폴트**(ROCm #5853) → 반드시 TheRock 빌드. (3단계)
3. `python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"` → **True + 8060S**.
4. **14B 스모크**:
   ```bash
   export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
   python src/train_directml.py --backend cuda --dtype bf16 \
     --base <14B스냅샷> --seq 512 --lora-r 16 --epochs 1 \
     --train-file data/processed/react_train_r4.jsonl --out models/14b-rocm --smoke 5
   ```
   **합격 기준**: ① `cuda.is_available()=True` ② **seq512에서 step 2 이후 OOM 없이 진행**
   (DirectML 단편화벽 해소 실증) ③ 통합메모리(103GB 주소공간)로 전용캡 초과 적재 ④ bf16 손실 정상.
   - DirectML은 seq320 step2에서 죽었음 → step2 통과가 핵심 관문.
5. 통과 시 → 5단계 bitsandbytes-ROCm 4bit 빌드로 **20B(~11GB)·32B(~18GB) QLoRA** 개방.
