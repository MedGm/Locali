#!/usr/bin/env bash
set -euo pipefail
cd /home/medgm/vsc/deep_learning
OUT=experiments/results/laptop_3b_check
M=$HOME/models/gguf/qwen2.5-coder-3b-instruct-q4_k_m.gguf
mkdir -p $OUT
for setting in none ngram-simple; do
  flags=""; [[ $setting == ngram-simple ]] && flags="--spec-type ngram-simple"
  $HOME/tools/llama.cpp/build/bin/llama-server -m $M $flags --jinja --load-mode none --cache-ram 0 --host 127.0.0.1 --port 8082 -t 4 -c 4096 --parallel 1 > $OUT/server_$setting.log 2>&1 &
  pid=$!
  for _ in $(seq 1 120); do curl -sf http://127.0.0.1:8082/health >/dev/null && break; sleep 1; done
  for bench in humanevalfix humaneval_plus; do
    $HOME/.local/bin/uv run python -m evaluation.run --benchmark $bench --model-id qwen2.5-coder-3b --model-revision f74adce6aa16316c625447af059dbebe4983757c \
      --quantization Q4_K_M --runtime "llama.cpp 987498f CPU t=4, speculative: $setting" --base-url http://127.0.0.1:8082/v1 \
      --notes "3B laptop feasibility check, 20 problems" --limit 20 --out $OUT/$bench/qwen2.5-coder-3b__q4km-${setting}__laptop-cpu > $OUT/run_${bench}_$setting.log 2>&1
    echo "$setting $bench done"
  done
  peak=$(awk '/VmHWM/ {print $2}' /proc/$pid/status); echo "$setting peak_rss_kb $peak" >> $OUT/memory.txt
  kill $pid; wait $pid 2>/dev/null || true
done
echo ALL DONE
