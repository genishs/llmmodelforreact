# GRUB 듀얼부팅 메뉴 복구 — Windows를 GRUB에 추가 (8060 노트북)

> 증상: Ubuntu 설치 후 시작 시 GRUB 선택 메뉴가 안 뜨고 곧장 Windows로 부팅됨.
> Ubuntu는 BIOS 부팅메뉴(F8/ESC)로만 선택 가능. → 펌웨어가 Windows를 먼저 부팅 + GRUB이 Windows를 목록에 안 띄움.
> 해결: ① GRUB(ubuntu)을 펌웨어 부팅순서 맨 앞으로 ② GRUB os-prober로 Windows 추가.
> **아래 명령은 전부 Ubuntu 터미널에서 실행.** (ASUS TUF A14, gfx1151, UEFI, Windows·Ubuntu 별도 디스크)

## ① 부팅 순서: GRUB(ubuntu) 먼저

```bash
sudo efibootmgr
```

출력에서 `ubuntu` 옆 번호와 `Windows Boot Manager` 옆 번호를 확인한다.
예) `Boot0001* ubuntu`, `Boot0000* Windows Boot Manager` 라면 ubuntu(0001)를 맨 앞으로:

```bash
sudo efibootmgr -o 0001,0000
```

> ⚠️ 위 번호는 예시. **네 출력의 실제 번호로 바꿔서** 실행할 것. ubuntu 번호를 맨 앞에 두고 나머지를 뒤에 나열.
> efibootmgr가 헷갈리면 이 ①을 건너뛰고 대신 **BIOS(F2) → Boot 탭에서 "ubuntu"를 "Windows Boot Manager" 위로** 올려도 동일.

## ② GRUB에 Windows 추가 + 메뉴 표시

```bash
sudo sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=10/' /etc/default/grub
echo 'GRUB_TIMEOUT_STYLE=menu'      | sudo tee -a /etc/default/grub
echo 'GRUB_DISABLE_OS_PROBER=false' | sudo tee -a /etc/default/grub
sudo update-grub
```

✅ `update-grub` 실행 중 **`Found Windows Boot Manager on ...`** 줄이 나오면 성공 (GRUB이 Windows를 잡음).

## ③ 재부팅

```bash
sudo reboot
```

→ 시작 시 **GRUB 메뉴에 Ubuntu + Windows Boot Manager**, 10초 타임아웃, 기본 Ubuntu.

---

## 체크포인트 / 함정

- **②에서 `Found Windows Boot Manager`가 안 나오면** — os-prober가 Windows를 못 찾은 것:
  ```bash
  sudo os-prober
  ```
  단독 실행해 Windows 감지 여부 확인. (Windows ESP는 BitLocker 영향 없이 읽힘. Fast Startup은 설치 전 껐으므로 OK.)
- **재부팅해도 여전히 바로 Windows로 가면** — 펌웨어가 순서를 되돌린 것. BIOS(F2) → Boot 우선순위에서 ubuntu를 직접 맨 위로 고정.
- **막히면** — 문제 명령의 출력을 캡처 → Windows 재부팅 → `claude --resume` 로 이어서 문의(또는 폰 Claude 앱).

## 다음 단계

GRUB 메뉴 정상화 후 → 진짜 목표인 **ROCm 설치**로. `docs/rocm-linux-dualboot-plan.md` 2~4단계
(ROCm 7.2 → TheRock gfx1151 휠[제네릭 nightly 세그폴트 주의] → 14B `--backend cuda --dtype bf16 --seq 512 --smoke 5`).
첫 관문 = seq512 step2 OOM 없이 통과.
