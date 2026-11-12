#!/usr/bin/env bash
# Run E as a Q5_K_M file on the laptop: the measurement of laptop_3b_energy_runE (all 164
# HumanEvalFix problems, n-gram lookup, 4 threads, one request at a time, RAPL energy), on the 5-bit
# file that experiments/results/8_improve/quant found better than the 4-bit one.
#     sudo chmod o+r /sys/class/powercap/intel-rapl:0/energy_uj   (resets on reboot)
#     M=<path to qwen2.5-coder-3b-locali-mixv3s-q5_k_m.gguf> bash experiments/scripts/laptop/laptop_runE_q5.sh
set -euo pipefail
cd "$(dirname "$0")/../../.."
RAPL=${RAPL:-/sys/class/powercap/intel-rapl:0/energy_uj}
cat "$RAPL" >/dev/null 2>&1 || { echo "RAPL not readable. Run: sudo chmod o+r $RAPL" >&2; exit 1; }
M=${M:-$HOME/models/gguf/qwen2.5-coder-3b-locali-mixv3s-q5_k_m.gguf}
OUT=experiments/results/5_laptop/laptop_3b_energy_runE_q5
ID=qwen2.5-coder-3b-ft-qlora-mixv3s
mkdir -p "$OUT"
"$HOME/tools/llama.cpp/build/bin/llama-server" -m "$M" --spec-type ngram-simple --jinja --load-mode none --cache-ram 0 \
    --host 127.0.0.1 --port 8082 -t 4 -c 4096 --parallel 1 > "$OUT/server.log" 2>&1 &
pid=$!
for _ in $(seq 1 300); do curl -sf http://127.0.0.1:8082/health >/dev/null && break; sleep 1; done
uv run python -m evaluation.run --benchmark humanevalfix --model-id $ID \
    --model-revision 488639f1ff808d1d3d0ba301aef8c11461451ec5 --quantization Q5_K_M \
    --runtime "llama.cpp 987498f CPU t=4, speculative: ngram-simple" --base-url http://127.0.0.1:8082/v1 \
    --notes "run E at 5 bits, laptop energy check" --out "$OUT/humanevalfix/${ID}__q5km-ngram-simple__laptop-cpu" > "$OUT/run.log" 2>&1
echo "$ID ngram-simple peak_rss_kb $(awk '/VmHWM/ {print $2}' /proc/$pid/status)" > "$OUT/memory.txt"
kill $pid; wait $pid 2>/dev/null || true
echo ALL DONE
