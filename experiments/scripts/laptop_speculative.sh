#!/usr/bin/env bash
# Speculative decoding on the laptop CPU: the fine-tuned 1.5B Q8 model with a 0.5B draft model or
# with draft-free n-gram lookup, against plain decoding. Same harness, energy and resume as
# laptop_ladder.sh; llama.cpp's draft counts are stored with every answer (draft_n, draft_n_accepted).
#
# Before running:
#   sudo chmod o+r /sys/class/powercap/intel-rapl:0/energy_uj
#   stop other model servers, close the browser and IDE, keep the laptop on mains power
#
#   LIMIT=20 bash experiments/scripts/laptop_speculative.sh                    # pilot, every setting
#   RUN="ngram-simple none draft-q4-n4 draft-q4-n8 draft-q8-n8" bash experiments/scripts/laptop_speculative.sh
#   QUANT=q4km RUN="ngram-simple none" bash experiments/scripts/laptop_speculative.sh   # Q4_K_M target
#
# The full run starts with a speculative setting so plain decoding is not the one that pays for the
# cold start (the pilot ran it first, right after the model was read from disk).
#
# Greedy speculative decoding verifies every drafted token with the target model, so answers should
# match plain decoding; the summary compares them. Re-running resumes.
set -euo pipefail

RAPL=${RAPL:-/sys/class/powercap/intel-rapl:0/energy_uj}
OUT_ROOT=${OUT_ROOT:-experiments/results/speculative_laptop}
LIMIT=${LIMIT:-}
BENCHMARKS=(${BENCHMARKS:-humaneval_plus humanevalfix})
LLAMA_SERVER=${LLAMA_SERVER:-$HOME/tools/llama.cpp/build/bin/llama-server}
GGUF_DIR=${GGUF_DIR:-$HOME/models/gguf}
UV=${UV:-$HOME/.local/bin/uv}
PORT=8081
STAMP=$(date +%Y%m%d)
[[ -n "$LIMIT" ]] && OUT_ROOT=${OUT_ROOT}_pilot

QUANT=${QUANT:-q80}  # target model: q80 (deployed default) or q4km
case "$QUANT" in
  q80) TARGET=$GGUF_DIR/qwen2.5-coder-1.5b-qlora-v2-q8_0.gguf; QUANT_LABEL=Q8_0 ;;
  q4km) TARGET=$GGUF_DIR/qwen2.5-coder-1.5b-qlora-v2-q4_k_m.gguf; QUANT_LABEL=Q4_K_M ;;
  *) echo "QUANT must be q80 or q4km" >&2; exit 1 ;;
esac
TARGET_ID=qwen2.5-coder-1.5b-ft-qlora-v2
TARGET_REV=f1a367a8c08f5c97fbd25ae8ff9f16cdf0231791
DRAFT_Q8=$GGUF_DIR/qwen2.5-coder-0.5b-instruct-q8_0.gguf  # Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF@ebb2015
DRAFT_Q4=$GGUF_DIR/qwen2.5-coder-0.5b-instruct-q4_k_m.gguf

# key | extra llama-server flags
ALL_CONFIGS=(
  "none|"
  "draft-q8-n2|-md $DRAFT_Q8 --spec-type draft-simple --spec-draft-n-max 2 -td 4"
  "draft-q8-n4|-md $DRAFT_Q8 --spec-type draft-simple --spec-draft-n-max 4 -td 4"
  "draft-q8-n8|-md $DRAFT_Q8 --spec-type draft-simple --spec-draft-n-max 8 -td 4"
  "draft-q4-n4|-md $DRAFT_Q4 --spec-type draft-simple --spec-draft-n-max 4 -td 4"
  "draft-q4-n8|-md $DRAFT_Q4 --spec-type draft-simple --spec-draft-n-max 8 -td 4"
  "ngram-simple|--spec-type ngram-simple"
  "ngram-mod|--spec-type ngram-mod"
)
RUN=(${RUN:-none draft-q8-n2 draft-q8-n4 draft-q8-n8 draft-q4-n4 ngram-simple ngram-mod})
CONFIGS=()
for key in "${RUN[@]}"; do
  match=$(printf '%s\n' "${ALL_CONFIGS[@]}" | grep "^$key|" || true)
  [[ -n "$match" ]] || { echo "unknown setting: $key" >&2; exit 1; }
  CONFIGS+=("$match")
done

cat "$RAPL" >/dev/null 2>&1 || { echo "RAPL not readable. Run: sudo chmod o+r $RAPL" >&2; exit 1; }
[[ -x "$LLAMA_SERVER" ]] || { echo "llama-server not found at $LLAMA_SERVER" >&2; exit 1; }
for f in "$TARGET" "$DRAFT_Q8" "$DRAFT_Q4"; do [[ -f "$f" ]] || { echo "missing $f" >&2; exit 1; }; done
mkdir -p "$OUT_ROOT"
LLAMA_COMMIT=$(git -C "$(dirname "$LLAMA_SERVER")/../.." rev-parse --short HEAD 2>/dev/null || echo unknown)
LOG=$OUT_ROOT/speculative_${STAMP}.log
exec > >(tee -a "$LOG") 2>&1
echo "== speculative $(date -Is), llama.cpp $LLAMA_COMMIT, benchmarks: ${BENCHMARKS[*]}, limit: ${LIMIT:-all}"

server_pid=""
stop_server() { [[ -n "$server_pid" ]] && kill "$server_pid" 2>/dev/null && wait "$server_pid" 2>/dev/null || true; server_pid=""; }

run_all() {
  trap stop_server EXIT
  for entry in "${CONFIGS[@]}"; do
    IFS='|' read -r key flags <<<"$entry"
    echo "-- $(date -Is) llama-server $QUANT $key"
    # shellcheck disable=SC2086
    "$LLAMA_SERVER" -m "$TARGET" $flags --jinja --load-mode none --cache-ram 0 --host 127.0.0.1 --port "$PORT" \
      -t 4 -c 4096 --parallel 1 >"$OUT_ROOT/server_${QUANT}-${key}_${STAMP}.log" 2>&1 &
    server_pid=$!
    for _ in $(seq 1 180); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && break; sleep 1; done
    curl -sf "http://127.0.0.1:$PORT/health" >/dev/null || { echo "server $key did not start" >&2; exit 1; }

    for bench in "${BENCHMARKS[@]}"; do
      echo "-- $(date -Is) $key / $bench"
      "$UV" run python -m evaluation.run --benchmark "$bench" \
        --model-id "$TARGET_ID" --model-revision "$TARGET_REV" --quantization "$QUANT_LABEL" \
        --runtime "llama.cpp $LLAMA_COMMIT CPU t=4, speculative: $key" --base-url "http://127.0.0.1:$PORT/v1" \
        --notes "speculative decoding study ($key: $flags), unattended laptop run with RAPL energy" \
        ${LIMIT:+--limit "$LIMIT"} --out "$OUT_ROOT/$bench/${TARGET_ID}__${QUANT}-${key}__laptop-cpu__${STAMP}"
    done
    peak=$(awk '/VmHWM/ {print $2}' "/proc/$server_pid/status")
    printf '%s\t%s\t%s\t%s\n' "$(date -Is)" "$QUANT-$key" "$peak" "${BENCHMARKS[*]}" >>"$OUT_ROOT/server_memory.tsv"
    echo "-- $key peak RSS ${peak} kB"
    stop_server
  done
  echo "== done $(date -Is)"
}

if command -v systemd-inhibit >/dev/null; then
  export -f run_all stop_server
  export LLAMA_SERVER UV PORT STAMP LLAMA_COMMIT OUT_ROOT LIMIT TARGET TARGET_ID TARGET_REV QUANT QUANT_LABEL
  systemd-inhibit --what=sleep:idle --who=locali --why="speculative decoding study" \
    bash -c "$(declare -p CONFIGS BENCHMARKS); server_pid=''; run_all"
else
  run_all
fi
