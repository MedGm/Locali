#!/usr/bin/env bash
# Speculative decoding for the deployed 3B (run D, Q4_K_M) on the laptop CPU, with draft models
# of the same tokenizer: the fine-tuned 1.5B (QLoRA v2, trained on the same kind of data), the base
# 1.5B and the base 0.5B, all Q4_K_M. Question: does a draft fine-tuned on the same data get more
# of its tokens accepted, and is that worth its compute on a CPU where draft and target share cores?
#
# Before running:
#   sudo chmod o+r /sys/class/powercap/intel-rapl:0/energy_uj
#   nothing else heavy on the laptop (no Docker scoring, browser, IDE indexing); mains power
#
#   LIMIT=5 RUN="draft-ft15-n4" bash experiments/scripts/laptop_3b_speculative.sh   # pilot
#   bash experiments/scripts/laptop_3b_speculative.sh                               # every setting
#
# Greedy speculative decoding verifies every drafted token, so answers should match plain
# decoding. n-gram lookup for the same model is in experiments/results/laptop_3b_energy_runD.
set -euo pipefail
cd "$(dirname "$0")/../.."

OUT=${OUT:-experiments/results/speculative_3b_laptop}
LIMIT=${LIMIT:-}
[[ -n "$LIMIT" ]] && OUT=${OUT}_pilot
G=${GGUF_DIR:-$HOME/models/gguf}
LLAMA_SERVER=${LLAMA_SERVER:-$HOME/tools/llama.cpp/build/bin/llama-server}
UV=${UV:-$HOME/.local/bin/uv}
TARGET=$G/qwen2.5-coder-3b-locali-mixv3b-diag-q4_k_m.gguf
ID=qwen2.5-coder-3b-ft-qlora-mixv3b-diag
REV=488639f1ff808d1d3d0ba301aef8c11461451ec5
FT15=$G/qwen2.5-coder-1.5b-qlora-v2-q4_k_m.gguf
BASE15=$G/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf   # quantized locally from the f16 GGUF
BASE05=$G/qwen2.5-coder-0.5b-instruct-q4_k_m.gguf
PORT=8083

# key | extra llama-server flags
ALL_CONFIGS=(
  "none|"
  "draft-ft15-n4|-md $FT15 --spec-type draft-simple --spec-draft-n-max 4 -td 4"
  "draft-ft15-n8|-md $FT15 --spec-type draft-simple --spec-draft-n-max 8 -td 4"
  "draft-base15-n4|-md $BASE15 --spec-type draft-simple --spec-draft-n-max 4 -td 4"
  "draft-base05-n4|-md $BASE05 --spec-type draft-simple --spec-draft-n-max 4 -td 4"
)
RUN=(${RUN:-draft-ft15-n4 draft-base15-n4 draft-base05-n4 none draft-ft15-n8})

mkdir -p "$OUT"
for key in "${RUN[@]}"; do
  config=$(printf '%s\n' "${ALL_CONFIGS[@]}" | grep "^$key|" || true)
  [[ -n "$config" ]] || { echo "unknown setting: $key" >&2; exit 1; }
  flags=${config#*|}
  # shellcheck disable=SC2086
  "$LLAMA_SERVER" -m "$TARGET" $flags --jinja --load-mode none --cache-ram 0 --host 127.0.0.1 --port $PORT \
    -t 4 -c 4096 --parallel 1 > "$OUT/server_$key.log" 2>&1 &
  pid=$!
  for _ in $(seq 1 180); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; sleep 1; done
  curl -sf http://127.0.0.1:$PORT/health >/dev/null || { echo "$key: server did not start" >&2; kill $pid; exit 1; }
  "$UV" run python -m evaluation.run --benchmark humanevalfix --model-id $ID --model-revision $REV \
    --quantization Q4_K_M --runtime "llama.cpp 987498f CPU t=4, speculative: $key" \
    --base-url http://127.0.0.1:$PORT/v1 --notes "3B speculative decoding, limit ${LIMIT:-all}" \
    ${LIMIT:+--limit $LIMIT} --out "$OUT/humanevalfix/${ID}__q4km-${key}__laptop-cpu" > "$OUT/run_$key.log" 2>&1
  peak=$(awk '/VmHWM/ {print $2}' /proc/$pid/status); echo "$key peak_rss_kb $peak" >> "$OUT/memory.txt"
  kill $pid; wait $pid 2>/dev/null || true
  echo "$(date +%H:%M) $key done"
done
echo ALL DONE
