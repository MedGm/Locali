#!/usr/bin/env bash
# Run G on the laptop at 4 and 5 bits: the measurement of laptop_3b_energy_runE (all 164 HumanEvalFix
# problems, n-gram lookup, 4 threads, one request at a time, RAPL energy), once per file, one after
# the other. Nothing else should run on the laptop meanwhile.
#     sudo chmod o+r /sys/class/powercap/intel-rapl:0/energy_uj   (resets on reboot)
#     bash experiments/scripts/laptop/laptop_runG.sh              (QUANTS="q4_k_m" for one file)
set -euo pipefail
cd "$(dirname "$0")/../../.."
RAPL=${RAPL:-/sys/class/powercap/intel-rapl:0/energy_uj}
cat "$RAPL" >/dev/null 2>&1 || { echo "RAPL not readable. Run: sudo chmod o+r $RAPL" >&2; exit 1; }
GGUF=${GGUF:-$HOME/models/gguf}
OUT=experiments/results/5_laptop/laptop_3b_energy_runG
ID=qwen2.5-coder-3b-ft-qlora-mixv3r
mkdir -p "$OUT"
for q in ${QUANTS:-q4_k_m q5_k_m}; do
    short=${q//_/}  # q4km
    "$HOME/tools/llama.cpp/build/bin/llama-server" -m "$GGUF/qwen2.5-coder-3b-locali-mixv3r-$q.gguf" \
        --spec-type ngram-simple --jinja --load-mode none --cache-ram 0 \
        --host 127.0.0.1 --port 8082 -t 4 -c 4096 --parallel 1 > "$OUT/server_$q.log" 2>&1 &
    pid=$!
    for _ in $(seq 1 300); do curl -sf http://127.0.0.1:8082/health >/dev/null && break; sleep 1; done
    uv run python -m evaluation.run --benchmark humanevalfix --model-id $ID \
        --model-revision 488639f1ff808d1d3d0ba301aef8c11461451ec5 --quantization "${q^^}" \
        --runtime "llama.cpp 987498f CPU t=4, speculative: ngram-simple" --base-url http://127.0.0.1:8082/v1 \
        --notes "run G, laptop energy check" --out "$OUT/humanevalfix/${ID}__${short}-ngram-simple__laptop-cpu" \
        > "$OUT/run_$q.log" 2>&1
    echo "$ID $q ngram-simple peak_rss_kb $(awk '/VmHWM/ {print $2}' /proc/$pid/status)" >> "$OUT/memory.txt"
    kill $pid; wait $pid 2>/dev/null || true
done
echo ALL DONE
