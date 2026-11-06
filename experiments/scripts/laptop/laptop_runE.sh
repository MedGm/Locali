#!/usr/bin/env bash
# Run E as the default model: the laptop energy check (same method as run D's,
# experiments/results/5_laptop/laptop_3b_energy_runD) and the full assistant on demo_repo for the 3B base,
# run D and run E, one after the other on the same code (experiments/results/7_assistant/agents_runE).
set -uo pipefail
cd "$(dirname "$0")/../../.."
G=${GGUF_DIR:-$HOME/models/gguf}
REV=488639f1ff808d1d3d0ba301aef8c11461451ec5
E=$G/qwen2.5-coder-3b-locali-mixv3s-q4_k_m.gguf

# 1. energy per fixed bug, all 164 HumanEvalFix problems, n-gram lookup
OUT=experiments/results/5_laptop/laptop_3b_energy_runE M=$E ID=qwen2.5-coder-3b-ft-qlora-mixv3s REV=$REV \
    BENCHES=humanevalfix SETTINGS=ngram-simple bash experiments/results/5_laptop/laptop_3b_check/check3b_param.sh

# 2. the full workflow on demo_repo, with the settings of scripts/run.sh (n-gram lookup, 4096 context)
set -a; source .env; set +a
for pair in "base:$G/qwen2.5-coder-3b-instruct-q4_k_m.gguf" "runD:$G/qwen2.5-coder-3b-locali-mixv3b-diag-q4_k_m.gguf" "runE:$E"; do
    name=${pair%%:*}; file=${pair#*:}
    out=experiments/results/7_assistant/agents_runE/$name
    mkdir -p "$out"
    "$HOME/tools/llama.cpp/build/bin/llama-server" -m "$file" --jinja --parallel 1 --cache-ram 0 -c 4096 \
        --host 127.0.0.1 --port 8093 --api-key "$LOCALI_MODEL_KEY" --spec-type ngram-simple > "$out/server.log" 2>&1 &
    server=$!
    for _ in $(seq 120); do curl -sf http://127.0.0.1:8093/health >/dev/null && break; sleep 2; done
    PYTHONPATH=. uv run python experiments/scripts/assistant/agent_eval.py --base-url http://127.0.0.1:8093/v1 --out "$out" > "$out/eval.log" 2>&1
    echo "$name eval exit $?"
    kill "$server"; wait "$server" 2>/dev/null
done
echo ALL DONE
