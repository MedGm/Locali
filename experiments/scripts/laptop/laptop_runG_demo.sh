#!/usr/bin/env bash
# The whole assistant on demo_repo with run G, the default since 2026-11-12, as scripts/run.sh serves
# it (Q4_K_M, llama.cpp with n-gram lookup, 4,096-token context, laptop CPU). To compare with run E:
# experiments/results/7_assistant/repair_step_runE/demo_repo (same code, same settings).
set -uo pipefail
cd "$(dirname "$0")/../../.."
set -a; source .env; set +a
G=${GGUF_DIR:-$HOME/models/gguf}/qwen2.5-coder-3b-locali-mixv3r-q4_k_m.gguf
OUT=experiments/results/7_assistant/agents_runG
mkdir -p "$OUT/demo_repo"

"$HOME/tools/llama.cpp/build/bin/llama-server" -m "$G" --jinja --parallel 1 --cache-ram 0 -c 4096 \
    --host 127.0.0.1 --port 8093 --api-key "$LOCALI_MODEL_KEY" --spec-type ngram-simple > "$OUT/server.log" 2>&1 &
server=$!
trap 'kill "$server" 2>/dev/null' EXIT
for _ in $(seq 120); do curl -sf http://127.0.0.1:8093/health >/dev/null && break; sleep 2; done

PYTHONPATH=. uv run python experiments/scripts/assistant/agent_eval.py --base-url http://127.0.0.1:8093/v1 \
    --out "$OUT/demo_repo" > "$OUT/demo_repo/eval.log" 2>&1
echo "demo_repo exit $?"
