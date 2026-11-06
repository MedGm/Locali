#!/usr/bin/env bash
# The 3B base on demo_repo again, after the code-extraction fix (a ```markdown block that is valid
# Python counts as code). Same settings as step 2 of laptop_runE.sh; the first run is kept in
# experiments/results/7_assistant/agents_runE/base_first_scoring.
set -uo pipefail
cd "$(dirname "$0")/../../.."
set -a; source .env; set +a
out=experiments/results/7_assistant/agents_runE/base
mkdir -p "$out"
"$HOME/tools/llama.cpp/build/bin/llama-server" -m "${GGUF_DIR:-$HOME/models/gguf}/qwen2.5-coder-3b-instruct-q4_k_m.gguf" \
    --jinja --parallel 1 --cache-ram 0 -c 4096 --host 127.0.0.1 --port 8093 --api-key "$LOCALI_MODEL_KEY" \
    --spec-type ngram-simple > "$out/server.log" 2>&1 &
server=$!
for _ in $(seq 120); do curl -sf http://127.0.0.1:8093/health >/dev/null && break; sleep 2; done
PYTHONPATH=. uv run python experiments/scripts/assistant/agent_eval.py --base-url http://127.0.0.1:8093/v1 --out "$out" > "$out/eval.log" 2>&1
echo "base eval exit $?"
kill "$server"; wait "$server" 2>/dev/null
echo ALL DONE
