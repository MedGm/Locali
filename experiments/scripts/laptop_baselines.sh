#!/usr/bin/env bash
# Unattended laptop-CPU baselines with energy measurement (RQ3, CPU / edge deployment).
#
# Before running:
#   1. sudo chmod o+r /sys/class/powercap/intel-rapl:0/energy_uj   (resets on reboot)
#   2. Close the browser, IDE and anything else busy: timing and energy cover the whole CPU.
#   3. Keep the laptop on mains power.
#
# Run from the repository root:
#   bash experiments/scripts/laptop_baselines.sh
# Re-running resumes: finished problems are skipped.
# Smoke test: RAPL=<readable file> LIMIT=2 OUT_ROOT=/tmp/somewhere bash experiments/scripts/laptop_baselines.sh
set -euo pipefail

RAPL=${RAPL:-/sys/class/powercap/intel-rapl:0/energy_uj}
OUT_ROOT=${OUT_ROOT:-experiments/results/baselines}
LIMIT=${LIMIT:-}
LLAMA_SERVER=${LLAMA_SERVER:-$HOME/tools/llama.cpp/build/bin/llama-server}
MODELS_DIR=${MODELS_DIR:-$HOME/models}
UV=${UV:-$HOME/.local/bin/uv}
PORT=8080
STAMP=$(date +%Y%m%d)
LOG=$OUT_ROOT/laptop_run_${STAMP}.log

# model id | GGUF file | GGUF repo revision
MODELS=(
  "qwen2.5-coder-1.5b|qwen2.5-coder-1.5b-instruct-q4_k_m.gguf|f86cb2c1fa58255f8052cc32aeede1b7482d4361"
  "qwen3.5-2b|Qwen3.5-2B-Q4_K_M.gguf|f6d5376be1edb4d416d56da11e5397a961aca8ae"
)
BENCHMARKS=(humaneval_plus mbpp_plus)

if ! cat "$RAPL" >/dev/null 2>&1; then
  echo "RAPL energy counter not readable. Run: sudo chmod o+r $RAPL" >&2
  exit 1
fi
[[ -x "$LLAMA_SERVER" ]] || { echo "llama-server not found at $LLAMA_SERVER" >&2; exit 1; }

mkdir -p "$(dirname "$LOG")"
LLAMA_COMMIT=$(git -C "$(dirname "$LLAMA_SERVER")/../.." rev-parse --short HEAD 2>/dev/null || echo unknown)
exec > >(tee -a "$LOG") 2>&1
echo "== laptop baselines $(date -Is), llama.cpp $LLAMA_COMMIT"

server_pid=""
stop_server() { [[ -n "$server_pid" ]] && kill "$server_pid" 2>/dev/null && wait "$server_pid" 2>/dev/null || true; server_pid=""; }
trap stop_server EXIT

run_all() {
  for entry in "${MODELS[@]}"; do
    IFS='|' read -r model_id gguf revision <<<"$entry"
    echo "-- $(date -Is) starting llama-server for $model_id"
    "$LLAMA_SERVER" -m "$MODELS_DIR/$gguf" --jinja --host 127.0.0.1 --port "$PORT" -t 4 -c 4096 --parallel 1 \
      >"$OUT_ROOT/server_${model_id}_${STAMP}.log" 2>&1 &
    server_pid=$!
    for _ in $(seq 1 120); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 1; done
    curl -sf "http://127.0.0.1:$PORT/health" >/dev/null || { echo "server for $model_id did not start" >&2; exit 1; }

    for bench in "${BENCHMARKS[@]}"; do
      echo "-- $(date -Is) $model_id / $bench"
      "$UV" run python -m evaluation.run --benchmark "$bench" \
        --model-id "$model_id" --model-revision "$revision" --quantization Q4_K_M \
        --runtime "llama.cpp $LLAMA_COMMIT CPU t=4" --base-url "http://127.0.0.1:$PORT/v1" \
        --notes "unattended laptop run with RAPL energy" ${LIMIT:+--limit "$LIMIT"} \
        --out "$OUT_ROOT/$bench/${model_id}__q4km__laptop-cpu__${STAMP}"
    done
    stop_server
  done
  echo "== done $(date -Is)"
}

# Prevent suspend while the benchmarks run.
if command -v systemd-inhibit >/dev/null; then
  export -f run_all stop_server
  export LLAMA_SERVER MODELS_DIR UV PORT STAMP LLAMA_COMMIT OUT_ROOT LIMIT
  systemd-inhibit --what=sleep:idle --who=locali --why="benchmark run" bash -c "$(declare -p MODELS BENCHMARKS); server_pid=''; trap stop_server EXIT; run_all"
else
  run_all
fi
