# D: 축소 런북 — ROCm 듀얼부팅용 미할당 공간 확보 (사용자 직접 실행)

> 작성 2026-07-12 (8060). 목적: Ubuntu 24.04 + ROCm 7.2 베어메탈 듀얼부팅을 위해 **Disk 1 (D:)에서
> 150~200GB 미할당 공간**을 확보. 이 문서는 **사용자가 관리자 권한으로 직접 실행**하는 절차다.
> 상위 설계·설치 전체 흐름은 `docs/rocm-linux-dualboot-plan.md` 참조. **설치 후 검증**은 이 문서 맨 끝.

## ✅ 진행 결과 (2026-07-12 완료 — 실측)
- **미할당 230.5GB 확보 성공.** 현재 Disk 1 = D: 701GB(여유 190.5GB) + **미할당 230.5GB**. Disk 0(Samsung/Windows) 미접촉.
- **실축소 차단 범인 = `$Mft::$BITMAP`** (마스터 파일 테이블 비트맵)이 **볼륨 물리 끝**(마지막 클러스터 `0xde82a08` ≈ 891GB 지점)에 박혀 있었음.
  → **Windows 기본 축소는 40GB만** 허용했음.
- **핵심 교훈**: `Optimize-Volume -Defrag`(및 diskmgmt.msc)는 **`$Mft`를 못 옮긴다** → 조각모음·섀도복사본 삭제·시스템복원 정리 **전부 무효**였음.
- **해결책 = 3rd-party 파티션 매니저**(MiniTool Partition Wizard Free / AOMEI Partition Assistant Standard)로 **PreOS(부팅 전) 모드에서 MFT 포함 앞으로 재배치하며 축소** → 성공.
- ⚠️ 아래 절차는 이 교훈을 반영해 정정됨. **이 프로젝트에서 재현하거나 유사 장비에 적용할 때 이 순서를 따를 것.**

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

### ③ 축소 상한 실측 (핵심 — 이동불가 파일 때문에 여유량보다 훨씬 작을 수 있음)
```powershell
$s = Get-PartitionSupportedSize -DriveLetter D
"현재크기 : {0} GB" -f [math]::Round($s.SizeMax/1GB,1)
"최소크기 : {0} GB" -f [math]::Round($s.SizeMin/1GB,1)
"→ 축소가능 최대 : {0} GB" -f [math]::Round(($s.SizeMax - $s.SizeMin)/1GB,1)
```
- `SizeMax - SizeMin` = **Windows 기본 도구로 잘라낼 수 있는 최대량**.
- ⚠️ **이 장비 실측: 여유가 421GB인데도 이 값이 겨우 ~40GB로 나왔다.** 이유는 ④에서 진단.
  **150~200GB에 한참 못 미치면 Windows 기본 축소를 포기하고 ⑤(파티션 매니저)로 직행**해야 한다.

### ④ 진짜 범인 진단 — 마지막 이동불가 파일 찾기 (`$Mft`가 볼륨 끝에 박힘)
Windows가 축소를 거부하는 진짜 원인은 대개 **볼륨 물리 끝에 박힌 이동불가 파일**이다. 이 장비에서는
**`$Mft::$BITMAP`(마스터 파일 테이블 비트맵)이 마지막 클러스터(`0xde82a08` ≈ 891GB 지점)에** 있었다.

**진단법 — 이벤트뷰어 Event ID 259:**
1. `diskmgmt.msc`에서 D: 축소를 한 번 시도(또는 `Get-PartitionSupportedSize` 실행).
2. `Win+R` → `eventvwr.msc` → **Windows 로그 > Application**.
3. **원본(Source) = `Microsoft-Windows-Defrag`, 이벤트 ID = `259`** 항목을 찾는다.
   → 여기에 **"마지막 이동불가 파일"의 이름과 클러스터 위치**가 찍힌다. `$Mft`/`$Mft::$BITMAP`이면 아래 확정.

**⛔ 여기서 하지 말 것 (이 장비에서 전부 무효로 확인됨):**
- `Optimize-Volume -DriveLetter D -Defrag` → **`$Mft`를 못 옮긴다.** 조각모음해도 축소 상한 그대로.
- diskmgmt.msc의 "볼륨 축소"도 동일 엔진 → **`$Mft` 못 옮김.**
- 섀도복사본/시스템 복원 지점 삭제(`vssadmin delete shadows`) → **범인이 아니었음. 지워도 무효.**
- 페이지파일/최대절전 파일 정리도 `$Mft`가 범인이면 무효.
→ **`$Mft`가 끝에 있으면 Windows 기본 도구로는 절대 큰 축소 불가.** ⑤로 간다.

### ⑤ 축소 실행 — 3rd-party 파티션 매니저 (MFT 재배치, 이 장비에서 유일하게 성공)
Windows 기본 도구와 달리, 파티션 매니저는 **`$Mft`를 포함한 이동불가 파일을 볼륨 앞쪽으로 재배치**하면서
축소할 수 있다(부팅 전 PreOS 모드에서 OS가 파일을 잠그기 전에 처리).

**도구(무료로 충분):** MiniTool Partition Wizard **Free** 또는 AOMEI Partition Assistant **Standard**.

**절차:**
1. 위 도구 설치 → **D: 볼륨 선택 → "Move/Resize Partition"**.
2. 볼륨 **오른쪽(끝) 핸들을 왼쪽으로 드래그**하거나 크기를 직접 입력해 **150~200GB 미할당**을 볼륨 끝에 만든다.
   - MFT가 뒤에 있으면 도구가 **"파일 이동/재배치가 필요하다"**고 안내 → 진행 승인.
3. **"Apply"** → 도구가 **재부팅 후 PreOS(부팅 전) 모드**에서 MFT 재배치+축소를 수행한다. **이 단계는 시간이 걸리고 중단 금지**(전원 안정 필수).
4. 부팅 완료 후 D: 뒤에 **미할당** 공간이 생겼는지 확인(⑥).

> 📌 **이 장비 실측 결과: 위 방법으로 230.5GB 미할당 확보 성공** (D: 931.5GB → 701GB, 미할당 230.5GB).
> Windows 기본 축소로는 40GB가 한계였다.

**(참고) Windows 기본 도구로 충분한 경우 — `$Mft`가 끝에 없을 때만:**
```powershell
# ③의 축소가능 최대가 목표(150~200GB) 이상으로 나오는 드문 경우에만 유효.
$targetGB = 731.5   # 예: 180GB 확보(현재크기 - 180GB)
Resize-Partition -DriveLetter D -Size ([uint64]($targetGB * 1GB))
```
이 장비처럼 `$Mft`가 끝에 있으면 위 명령은 `SizeMin` 벽에 막혀 실패한다 → ⑤ 파티션 매니저를 쓸 것.

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
- ✅ **이 장비 실측 최종 상태**: Disk 1(GIGABYTE 931.5GB) = D: 701GB(여유 190.5GB) + **미할당 230.5GB**. Disk 0(Samsung/Windows) 미접촉.

---

## 축소 완료 후 — 다음 단계 (← 현재 여기)

✅ **디스크 준비(230.5GB 미할당 확보)는 완료됨.** 다음은 **Ubuntu 물리 설치**이며, 이 단계는
부팅 전 GUI·BIOS 영역이라 **사용자가 직접** 해야 한다(Claude 자동화 불가).

**즉시 다음 (사용자 물리 작업 — 부팅·BIOS·파티셔닝):**
1. Ubuntu 24.04.3 LTS USB 부팅 → **230.5GB 미할당 공간에** 설치 (C: Windows 유지, GRUB 듀얼부팅).
   BIOS Secure Boot off 권장, 부팅순서 USB 우선. 파티션: ext4 root + swap.
2. 커널 6.14 HWE 핀 고정 → `docs/rocm-linux-dualboot-plan.md` 1단계 그대로.

**Claude가 스테이징 가능 (문서·스크립트·검증 레시피 사전 준비 — 이미 준비됨):**
- ROCm 7.2 설치 명령 블록, TheRock gfx1151 휠 index, 검증 스크립트를 Linux 진입 즉시 복붙 가능하게 정리(하단 참조).
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
