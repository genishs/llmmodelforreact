#!/usr/bin/env bash
# chain_mixtral8x22b_feas.sh — Mixtral-8x22B(141B) "가능성 테스트" 체인.
#
# 목적(범위 엄수): 141B가 (a) 이 gfx1151/64GB 장비에 HQQ 2bit로 로드되고
#   (b) LoRA 학습 스텝이 실제로 도는지 짧은 런(--smoke 8스텝)으로 증명만 한다. 풀 학습 아님.
#
# 흐름: 외장하드 다운로드 완료 대기 → 무결성 검증 → 스왑 가드(≥60GiB, 미달이면 큐잉·중단) → smoke 발사.
#
# ⚠️ 어텐션-온리 LoRA(q/k/v/o_proj) — --lora-mlp 절대 넣지 말 것.
#    Mixtral MLP는 전문가 w1/w2/w3+라우터 gate라 gate_proj/up_proj/down_proj 타깃이 없어 PEFT가 죽는다.
#    config/training_config.yaml 기본 target_modules가 이미 q/v/k/o_proj(어텐션) → 그대로 사용.
# ⚠️ 스왑: 141B GTT 피크 ~52-56GiB로 60GiB 한계 근접 → 스왑 마진 필수. sudo swapon은 두목 몫(큐잉).
#         GTT 캡(56GiB)은 건드리지 말 것(핀이라 상향 시 프리즈).

set -uo pipefail
REPO="/mnt/data/Documents/workspace/study/ai_model"        # 내장 repo(코드 정본)
BASE="/run/media/user/새 볼륨/mixtral-8x22b-v0.1"           # 외장 다운로드 타깃(bf16 원본)
# ⚠️ Mixtral 전용 격리 venv: transformers 4.46.3(구조식 MoE, 개별 Linear 전문가).
# 본 ai_model_rocm(transformers 5.13.1=전문가 융합 nn.Parameter)은 HQQ per-Linear 로더와
# 비호환 → block_sparse_moe 속성부재로 크래시. 실측: 4.46.3에서 체크포인트 키 1739개 100%
# 매칭(scripts/check_mixtral_struct.py), torch2.10+rocm7.13 호환 확인.
PY="/home/user/.venvs/ai_model_mixtral/bin/python"
DL_LOG="/home/user/gpu_jobs/logs/dl_mixtral.log"
LOG="/home/user/gpu_jobs/logs/chain_mixtral_feas.log"
SWAP_MIN_GIB=60

cd "$REPO" || exit 1
exec >>"$LOG" 2>&1
echo "=================================================="
echo "[$(date '+%F %T')] Mixtral-8x22B 가능성 체인 시작"

# ---------- 1. 다운로드 완료 대기 (최대 6시간) ----------
echo "[$(date '+%F %T')] 다운로드 완료 대기…(최대 6h)"
for i in $(seq 1 2160); do   # 2160*10s = 6h
  running=$(ps -eo comm,args | grep -i dl_mixtral8x22b | grep -v grep | grep -c python)
  incomplete=$(find "$BASE" -name "*.incomplete" 2>/dev/null | wc -l)
  alldone=$(grep -c "ALL DONE" "$DL_LOG" 2>/dev/null || echo 0)
  if [ "$running" -eq 0 ] && [ "$incomplete" -eq 0 ] && [ "$alldone" -ge 1 ]; then break; fi
  sleep 10
done
running=$(ps -eo comm,args | grep -i dl_mixtral8x22b | grep -v grep | grep -c python)
incomplete=$(find "$BASE" -name "*.incomplete" 2>/dev/null | wc -l)
alldone=$(grep -c "ALL DONE" "$DL_LOG" 2>/dev/null || echo 0)
if [ "$running" -ne 0 ] || [ "$incomplete" -ne 0 ] || [ "$alldone" -lt 1 ]; then
  echo "[$(date '+%F %T')] ✗ 중단: 6h 내 다운로드 미완(running=$running incomplete=$incomplete alldone=$alldone)"
  echo "[QUEUE] 다운로드 미완 → 학습 미발사. 다운로드 로그: $DL_LOG"
  exit 1
fi
echo "[$(date '+%F %T')] 다운로드 완료"

# ---------- 2. 무결성 검증 ----------
echo "[$(date '+%F %T')] 검증…"
shards=$(ls "$BASE"/model-*.safetensors 2>/dev/null | wc -l)
idx="$BASE/model.safetensors.index.json"
expected=$("$PY" -c "import json;d=json.load(open('$idx'));print(len(set(d['weight_map'].values())))" 2>/dev/null || echo 0)
echo "  샤드 $shards개 (index 기대 $expected개) | incomplete 0 | config $([ -f "$BASE/config.json" ] && echo OK || echo MISSING)"
if [ "$expected" -gt 0 ]; then
  [ "$shards" = "$expected" ] || { echo "✗ 샤드 수 불일치($shards vs $expected) — 중단"; exit 1; }
else
  echo "  (index 기대치 파싱 실패 — incomplete 0 신뢰)"; [ "$shards" -gt 40 ] || { echo "✗ 샤드 너무 적음($shards) — 중단"; exit 1; }
fi
[ -f "$BASE/config.json" ] || { echo "✗ config 없음 — 중단"; exit 1; }
"$PY" - <<PYEOF || { echo "✗ safetensors 무결성 실패 — 중단"; exit 1; }
import glob,json,struct,sys
ok=0
for f in sorted(glob.glob("$BASE/model-*.safetensors")):
    with open(f,"rb") as fh:
        n=struct.unpack("<Q",fh.read(8))[0]; json.loads(fh.read(n))
    ok+=1
print(f"  safetensors 헤더 OK: {ok}개"); sys.exit(0)
PYEOF
echo "[$(date '+%F %T')] ✓ 검증 통과"

# ---------- 3. 스왑 가드 (읽기전용; sudo는 두목 몫) ----------
# 다운로드 완료 후 두목이 sudo swapon 할 때까지 최대 2시간 폴링. 생기면 발사, 안 생기면 큐잉.
swap_now() { swapon --show=SIZE --bytes --noheadings 2>/dev/null | awk '{s+=$1} END{printf "%.0f", s/1073741824}'; }
echo "[$(date '+%F %T')] 스왑 가드: ≥${SWAP_MIN_GIB}GiB 대기(최대 2h; sudo swapon /swapfile 은 두목 몫)"
for i in $(seq 1 720); do   # 720*10s = 2h
  swap_gib=$(swap_now); swap_gib=${swap_gib:-0}
  [ "$swap_gib" -ge "$SWAP_MIN_GIB" ] && break
  [ $((i % 30)) -eq 1 ] && echo "[$(date '+%F %T')]   현재 스왑 ${swap_gib}GiB — 대기중…"
  sleep 10
done
swap_gib=$(swap_now); swap_gib=${swap_gib:-0}
echo "[$(date '+%F %T')] 스왑 총량: ${swap_gib}GiB (요구 ≥${SWAP_MIN_GIB}GiB)"
if [ "$swap_gib" -lt "$SWAP_MIN_GIB" ]; then
  echo "[$(date '+%F %T')] ✗ 스왑 부족 → 발사 보류(오발사 방지)."
  echo "[QUEUE] 두목 조치 필요: sudo swapon /swapfile (스왑 15→64GiB). 완료 후 이 체인 재실행:"
  echo "        setsid nohup bash scripts/chain_mixtral8x22b_feas.sh &"
  exit 2
fi
echo "[$(date '+%F %T')] ✓ 스왑 가드 통과"

# ---------- 4. host RAM 회복 대기 ----------
sleep 15
echo "[$(date '+%F %T')] host RAM 가용: $(free -g | awk '/Mem:/{print $7}')GB"

# ---------- 5. Mixtral HQQ 2bit 어텐션-온리 LoRA 가능성 런(smoke 8스텝) 발사 ----------
echo "[$(date '+%F %T')] Mixtral HQQ2 어텐션-LoRA 가능성 런(smoke 8) 발사"
bash scripts/gpu_job.sh --name mixtralfeas --timeout 14400 --cwd "$REPO" -- \
  "$PY" src/train_directml.py \
    --backend cuda --dtype bf16 \
    --base "$BASE" \
    --quant hqq --hqq-nbits 2 --hqq-group-size 64 \
    --lora-r 16 \
    --grad-ckpt --seq 512 \
    --epochs 1 --smoke 8 \
    --out ./models/mixtral-8x22b-hqq2-feas

# ---------- 6. 계측 백그라운드(GUI-off에도 생존) ----------
# 학습은 detached --user 유닛에서 돈다. 계측도 setsid nohup 파일로그로 분리 → 세션·GUI 죽어도
# GTT 피크가 파일에 남아 다음 세션이 문서화 가능. train_directml 사라지면 스스로 종료.
MW_LOG="/home/user/gpu_jobs/logs/mem_watch_mixtral.log"
setsid nohup bash "$REPO/scripts/mem_watch_until.sh" >"$MW_LOG" 2>&1 &
echo "[$(date '+%F %T')] 계측 백그라운드 시작 → $MW_LOG"
echo "[$(date '+%F %T')] 체인 완료 — 가능성 런은 mixtralfeas 유닛에서 진행 중. 계측은 $MW_LOG."
