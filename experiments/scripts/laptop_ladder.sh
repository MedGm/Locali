#!/usr/bin/env bash
# Quantization ladder on the laptop CPU: the fine-tuned model as F16, Q8_0 and Q4_K_M GGUF.
# Base-model Q4_K_M answers come from laptop_baselines.sh (greedy runs reproduce exactly).
#
# Before running (same as laptop_baselines.sh):
#   sudo chmod o+r /sys/class/powercap/intel-rapl:0/energy_uj
#   close the browser and IDE, keep the laptop on mains power
#
#   bash experiments/scripts/laptop_ladder.sh                      # fine-tuned Q4, Q8, F16
#   RUN="base-f16" bash experiments/scripts/laptop_ladder.sh       # any subset of the entries below
#   RUN="base-q4 ft-q4" BENCHMARKS="humanevalfix internal_t1" bash experiments/scripts/laptop_ladder.sh
#
# Re-running resumes: finished problems are skipped. Peak RAM of each llama-server is appended to
# $OUT_ROOT/server_memory.tsv. --load-mode none (no mmap) so peak RSS is the loaded model (with mmap, repacked Q4_K
# weights were counted twice and Q4 looked as big as Q8). --cache-ram 0: the host prompt cache
# (default 8 GiB) grew with every prompt and added ~2 GB to the night-1 peaks.
set -euo pipefail

RAPL=${RAPL:-/sys/class/powercap/intel-rapl:0/energy_uj}
OUT_ROOT=${OUT_ROOT:-experiments/results/ladder_laptop}
LIMIT=${LIMIT:-}
BENCHMARKS=(${BENCHMARKS:-humaneval_plus mbpp_plus})
LLAMA_SERVER=${LLAMA_SERVER:-$HOME/tools/llama.cpp/build/bin/llama-server}
GGUF_DIR=${GGUF_DIR:-$HOME/models/gguf}
UV=${UV:-$HOME/.local/bin/uv}
PORT=8080
STAMP=$(date +%Y%m%d)

# key | model id | quantization | GGUF path | revision
# ft revisions: HF GGUF repo (F16 was built from the merged-model repo). base-q4 is Qwen's official
# GGUF; base-f16 was converted from Qwen/Qwen2.5-Coder-1.5B-Instruct@2e1fd39 with convert_hf_to_gguf.py.
FT=qwen2.5-coder-1.5b-ft-qlora-v2
BASE=qwen2.5-coder-1.5b
ALL_MODELS=(
  "base-q4|$BASE|Q4_K_M|$HOME/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf|f86cb2c1fa58255f8052cc32aeede1b7482d4361"
  "base-f16|$BASE|F16|$GGUF_DIR/qwen2.5-coder-1.5b-instruct-f16.gguf|2e1fd397ee46e1388853d2af2c993145b0f1098a"
  "ft-q4|$FT|Q4_K_M|$GGUF_DIR/qwen2.5-coder-1.5b-qlora-v2-q4_k_m.gguf|f1a367a8c08f5c97fbd25ae8ff9f16cdf0231791"
  "ft-q8|$FT|Q8_0|$GGUF_DIR/qwen2.5-coder-1.5b-qlora-v2-q8_0.gguf|f1a367a8c08f5c97fbd25ae8ff9f16cdf0231791"
  "ft-f16|$FT|F16|$GGUF_DIR/qwen2.5-coder-1.5b-qlora-v2-f16.gguf|a1b0b1189d2050dd20013371fc327362ea6b2964"
)
RUN=(${RUN:-ft-q4 ft-q8 ft-f16})
MODELS=()
for key in "${RUN[@]}"; do
  match=$(printf '%s\n' "${ALL_MODELS[@]}" | grep "^$key|" || true)
  [[ -n "$match" ]] || { echo "unknown model key: $key" >&2; exit 1; }
  MODELS+=("${match#*|}")
done

cat "$RAPL" >/dev/null 2>&1 || { echo "RAPL not readable. Run: sudo chmod o+r $RAPL" >&2; exit 1; }
[[ -x "$LLAMA_SERVER" ]] || { echo "llama-server not found at $LLAMA_SERVER" >&2; exit 1; }
mkdir -p "$OUT_ROOT"
LLAMA_COMMIT=$(git -C "$(dirname "$LLAMA_SERVER")/../.." rev-parse --short HEAD 2>/dev/null || echo unknown)
LOG=$OUT_ROOT/ladder_${STAMP}.log
exec > >(tee -a "$LOG") 2>&1
echo "== ladder $(date -Is), llama.cpp $LLAMA_COMMIT, benchmarks: ${BENCHMARKS[*]}"

server_pid=""
stop_server() { [[ -n "$server_pid" ]] && kill "$server_pid" 2>/dev/null && wait "$server_pid" 2>/dev/null || true; server_pid=""; }

run_all() {
  trap stop_server EXIT
  for entry in "${MODELS[@]}"; do
    IFS='|' read -r model_id quant gguf revision <<<"$entry"
    tag=$(echo "$quant" | tr 'A-Z' 'a-z' | tr -d '_')
    echo "-- $(date -Is) llama-server $model_id $quant"
    "$LLAMA_SERVER" -m "$gguf" --jinja --load-mode none --cache-ram 0 --host 127.0.0.1 --port "$PORT" -t 4 -c 4096 --parallel 1 \
      >"$OUT_ROOT/server_${model_id}_${tag}_${STAMP}.log" 2>&1 &
    server_pid=$!
    for _ in $(seq 1 180); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 1; done
    curl -sf "http://127.0.0.1:$PORT/health" >/dev/null || { echo "server $quant did not start" >&2; exit 1; }

    for bench in "${BENCHMARKS[@]}"; do
      echo "-- $(date -Is) $model_id $quant / $bench"
      "$UV" run python -m evaluation.run --benchmark "$bench" \
        --model-id "$model_id" --model-revision "$revision" --quantization "$quant" \
        --runtime "llama.cpp $LLAMA_COMMIT CPU t=4" --base-url "http://127.0.0.1:$PORT/v1" \
        --notes "quantization ladder, unattended laptop run with RAPL energy" ${LIMIT:+--limit "$LIMIT"} \
        --out "$OUT_ROOT/$bench/${model_id}__${tag}__laptop-cpu__${STAMP}"
    done
    peak=$(awk '/VmHWM/ {print $2}' "/proc/$server_pid/status")
    printf '%s\t%s\t%s\t%s\t%s\n' "$(date -Is)" "$model_id" "$quant" "$peak" "${BENCHMARKS[*]}" >>"$OUT_ROOT/server_memory.tsv"
    echo "-- $model_id $quant peak RSS ${peak} kB"
    stop_server
  done
  echo "== done $(date -Is)"
}

if command -v systemd-inhibit >/dev/null; then
  export -f run_all stop_server
  export LLAMA_SERVER GGUF_DIR UV PORT STAMP LLAMA_COMMIT OUT_ROOT LIMIT
  systemd-inhibit --what=sleep:idle --who=locali --why="quantization ladder" \
    bash -c "$(declare -p MODELS BENCHMARKS); server_pid=''; run_all"
else
  run_all
fi
