#!/usr/bin/env bash
# gpu_job.sh — crash-safe detached GPU job runner for halo-ubuntu (gfx1151).
#
# WHY THIS EXISTS
#   The Radeon 8060S iGPU drives BOTH the display and compute. A GPU wedge
#   ("HIP error: unspecified launch failure" -> "amdgpu: device wedged, but
#   recovered through reset") takes down the GNOME session and every terminal
#   inside it. Any job launched from that terminal dies with it.
#
#   This wrapper launches the job as a **systemd --user transient service**.
#   The user manager (systemd --user) is NOT a child of the GNOME session, and
#   `Linger=yes` is already enabled for this user, so the unit survives:
#     - the GNOME session dying from a GPU wedge
#     - logout / re-login
#     - `systemctl isolate multi-user.target`
#     - the terminal (and the Claude Code session) going away
#
# USAGE
#   scripts/gpu_job.sh [options] -- <command> [args...]
#   scripts/gpu_job.sh --name nf4gate -- python scripts/test_nf4_backward_gate.py
#
# OPTIONS
#   --name NAME        job name (default: gpujob). Unit = gpujob-NAME-TIMESTAMP.service
#   --serialize        AMD_SERIALIZE_KERNEL=3  (sync after every kernel; a wedge
#                      then names the exact faulting kernel in the log)
#   --blocking         HIP_LAUNCH_BLOCKING=1   (synchronous launches)
#   --debug            both of the above (use when hunting a wedge)
#   --timeout SEC      hard wall clock limit; unit is killed after SEC (default 3600)
#   --cwd DIR          working directory (default: the ai_model repo root)
#   --foreground       run inline instead of detached (NOT wedge-safe; debug only)
#   --list             list running/recent gpujob units and exit
#   --logs NAME|UNIT   tail -f the log for a job and exit
#   --stop UNIT        stop a running job and exit
#
# The caller is NEVER blocked: the script prints the unit name + log path and exits 0.

set -uo pipefail

REPO_DEFAULT="/run/media/user/새 볼륨/Documents/workspace/study/ai_model"
VENV="/home/user/.venvs/ai_model_rocm"
PY="$VENV/bin/python"

# Logs go to $HOME (ext4). The repo lives on an ntfs3 removable mount, which is a
# bad place for a log a systemd unit appends to across a GPU reset.
LOG_DIR="${GPU_JOB_LOG_DIR:-$HOME/gpu_jobs/logs}"
RUN_DIR="${GPU_JOB_RUN_DIR:-$HOME/gpu_jobs/run}"

NAME="gpujob"
CWD="$REPO_DEFAULT"
TIMEOUT=3600
SERIALIZE=0
BLOCKING=0
FOREGROUND=0

die() { echo "gpu_job: error: $*" >&2; exit 2; }

# ---------------------------------------------------------------- arg parsing
ACTION="run"
ACTION_ARG=""
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)       NAME="${2:?--name needs a value}"; shift 2 ;;
    --serialize)  SERIALIZE=1; shift ;;
    --blocking)   BLOCKING=1; shift ;;
    --debug)      SERIALIZE=1; BLOCKING=1; shift ;;
    --timeout)    TIMEOUT="${2:?--timeout needs a value}"; shift 2 ;;
    --cwd)        CWD="${2:?--cwd needs a value}"; shift 2 ;;
    --foreground) FOREGROUND=1; shift ;;
    --list)       ACTION="list"; shift ;;
    --logs)       ACTION="logs"; ACTION_ARG="${2:-}"; shift 2 ;;
    --stop)       ACTION="stop"; ACTION_ARG="${2:?--stop needs a unit}"; shift 2 ;;
    -h|--help)    sed -n '2,40p' "$0"; exit 0 ;;
    --)           shift; ARGS=("$@"); break ;;
    *)            die "unknown option '$1' (did you forget '--' before the command?)" ;;
  esac
done

mkdir -p "$LOG_DIR" "$RUN_DIR" || die "cannot create $LOG_DIR"

# ---------------------------------------------------------------- subcommands
case "$ACTION" in
  list)
    echo "== running gpujob units =="
    systemctl --user list-units --type=service --no-pager --plain 'gpujob-*' 2>/dev/null
    echo
    echo "== recent logs in $LOG_DIR =="
    ls -1t "$LOG_DIR" 2>/dev/null | head -20
    exit 0 ;;
  logs)
    [[ -n "$ACTION_ARG" ]] || die "--logs needs a job name or unit"
    f=$(ls -1t "$LOG_DIR"/*"$ACTION_ARG"* 2>/dev/null | head -1)
    [[ -n "$f" ]] || die "no log matching '$ACTION_ARG' in $LOG_DIR"
    echo "gpu_job: tailing $f  (Ctrl-C to stop; the job keeps running)"
    exec tail -f "$f" ;;
  stop)
    systemctl --user stop "$ACTION_ARG"
    echo "gpu_job: stopped $ACTION_ARG"
    exit 0 ;;
esac

[[ ${#ARGS[@]} -gt 0 ]] || die "no command given. Use: gpu_job.sh [opts] -- <command...>"

# Preflight: the whole design rests on the user manager being reachable and
# lingering. If either is false the job would die with the session -- fail loudly
# rather than silently handing back a job that cannot survive a wedge.
systemctl --user is-system-running >/dev/null 2>&1 || \
  die "systemd --user is not reachable (XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-unset})"
if [[ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != "yes" ]]; then
  echo "gpu_job: WARNING: Linger=no for $USER -- the job will NOT survive logout." >&2
  echo "gpu_job:          fix with: sudo loginctl enable-linger $USER" >&2
fi

TS=$(date +%Y%m%d-%H%M%S)
# The PID suffix is load-bearing, not decoration: date granularity is 1s, so two
# launches in the same second would otherwise collide on the unit name and the
# second systemd-run would fail. This keeps re-runs safe.
UNIT="gpujob-${NAME}-${TS}-$$"
LOG="$LOG_DIR/${UNIT}.log"
INNER="$RUN_DIR/${UNIT}.sh"

# ---------------------------------------------------------------- inner script
# Everything (GPU state before/after, the command, exit code) is written by the
# inner script so a single file holds the whole story of the job. The inner
# script is generated per-job and is self-contained -- systemd only ever sees
# `bash /path/to/inner.sh`, which sidesteps quoting hell with the Korean/spaced
# repo path and with arbitrary user commands.
{
  printf '#!/usr/bin/env bash\n'
  printf 'set -uo pipefail\n'
  printf 'export PATH=%q:"$PATH"\n' "$VENV/bin"
  printf 'export VIRTUAL_ENV=%q\n' "$VENV"
  # NEVER set HSA_OVERRIDE_GFX_VERSION -- setting it (even empty) breaks
  # torch.cuda.is_available() on this box. Leaving it unset is what works.
  printf 'unset HSA_OVERRIDE_GFX_VERSION\n'
  printf 'export PYTHONUNBUFFERED=1\n'
  [[ $SERIALIZE -eq 1 ]] && printf 'export AMD_SERIALIZE_KERNEL=3\n'
  [[ $BLOCKING  -eq 1 ]] && printf 'export HIP_LAUNCH_BLOCKING=1\n'
  printf 'cd %q || exit 3\n' "$CWD"
  printf '\n'
  printf 'gpu_state() {\n'
  printf '  echo "--- GPU state: $1 ---"\n'
  printf '  %q --showuse --showmeminfo vram --showtemp 2>&1 | sed "s/^/    /" || echo "    (rocm-smi unavailable)"\n' "$VENV/bin/rocm-smi"
  printf '  echo "--- kernel amdgpu/drm tail ---"\n'
  # `dmesg` is blocked here (kernel.dmesg_restrict=1) but `journalctl -k` works
  # because this user is in the `adm` group -- no sudo needed.
  # NOTE: filter FIRST, then tail. Doing `-n 15 | grep amdgpu` returns nothing,
  # because the last lines of this journal are always apparmor audit spam.
  # "Modules linked in:" dumps a ~2KB module list per kernel WARNING and would
  # otherwise eat the whole tail window; cut bounds any other stack-trace spew.
  printf '  journalctl -k --no-pager --since "-30min" 2>/dev/null \\\n'
  printf '    | grep -iE "amdgpu|drm|wedge|ring.*timeout|GPU reset|unspecified launch" \\\n'
  printf '    | grep -viE "Modules linked in|apparmor|^\\s*$" \\\n'
  printf '    | cut -c1-200 \\\n'
  printf '    | tail -12 | sed "s/^/    /" || echo "    (no recent amdgpu kernel messages)"\n'
  printf '}\n\n'
  # A wedge is the single outcome this whole harness exists to catch, so make it
  # an explicit, greppable verdict rather than something to eyeball in the log.
  printf 'wedge_check() {\n'
  printf '  local hits\n'
  printf '  hits=$(journalctl -k --no-pager --since "-30min" 2>/dev/null \\\n'
  printf '    | grep -icE "device wedged|ring.*timeout|GPU reset begin|amdgpu.*reset" || true)\n'
  printf '  if [ "${hits:-0}" -gt 0 ]; then\n'
  printf '    echo "*** WEDGE DETECTED: $hits amdgpu reset/wedge kernel message(s) during this job. ***"\n'
  printf '    echo "*** The GPU faulted. If the desktop died, this job still ran to here.       ***"\n'
  printf '  else\n'
  printf '    echo "no amdgpu wedge/reset messages in the kernel log -- GPU looks healthy"\n'
  printf '  fi\n'
  printf '}\n\n'
  printf 'echo "=========================================================="\n'
  printf 'echo "job      : %s"\n' "$UNIT"
  printf 'echo "started  : $(date -Is)"\n'
  printf 'echo "cwd      : %s"\n' "$CWD"
  printf 'echo "command  : %s"\n' "${ARGS[*]}"
  printf 'echo "serialize: %s   blocking: %s"\n' "$SERIALIZE" "$BLOCKING"
  printf 'echo "=========================================================="\n'
  printf 'gpu_state BEFORE\n'
  printf 'echo "=========================== RUN =========================="\n'
  printf 'start=$(date +%%s)\n'
  # exec the command with its args properly quoted, one %q per arg
  printf '%q ' "${ARGS[@]}"
  printf '\n'
  printf 'rc=$?\n'
  printf 'end=$(date +%%s)\n'
  printf 'echo "=========================== DONE =========================="\n'
  printf 'echo "exit code: $rc   elapsed: $((end-start))s"\n'
  printf 'gpu_state AFTER\n'
  printf 'wedge_check\n'
  printf 'echo "finished : $(date -Is)"\n'
  printf 'exit $rc\n'
} > "$INNER"
chmod +x "$INNER"

# ---------------------------------------------------------------- launch
if [[ $FOREGROUND -eq 1 ]]; then
  echo "gpu_job: FOREGROUND mode -- this job dies if the session dies. Log: $LOG"
  bash "$INNER" 2>&1 | tee "$LOG"
  exit "${PIPESTATUS[0]}"
fi

# --collect: the unit is garbage-collected after it exits, so re-running the same
#   --name is always safe (idempotent; the timestamp makes the unit unique anyway).
# StandardOutput/Error=append: gives us the timestamped file; journald also keeps
#   a copy under the unit name, which survives even if the log file is lost.
# RuntimeMaxSec: hard ceiling so a hung job can never occupy the GPU forever.
if systemd-run --user \
      --unit="$UNIT" \
      --collect \
      --description="GPU job ${NAME} (${TS})" \
      --property="RuntimeMaxSec=${TIMEOUT}" \
      --property="StandardOutput=append:${LOG}" \
      --property="StandardError=append:${LOG}" \
      --property="KillSignal=SIGINT" \
      --property="TimeoutStopSec=30" \
      /bin/bash "$INNER" >/dev/null 2>&1; then
  :
else
  die "systemd-run failed to launch $UNIT (try: systemctl --user status $UNIT)"
fi

cat <<EOF
gpu_job: launched detached -- this terminal is free, and the job now survives
         a GPU wedge, a dead GNOME session, and logout.

  unit   : ${UNIT}.service
  log    : $LOG
  follow : scripts/gpu_job.sh --logs $NAME
  status : systemctl --user status ${UNIT}
  journal: journalctl --user -u ${UNIT} -f
  stop   : scripts/gpu_job.sh --stop ${UNIT}
EOF
exit 0
