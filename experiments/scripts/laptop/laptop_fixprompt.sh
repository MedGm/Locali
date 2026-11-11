#!/usr/bin/env bash
# The assistant's repair step after 2026-11-11 (benchmark-format prompt, sampled retries), run E as
# served by scripts/run.sh (Q4_K_M, llama.cpp with n-gram lookup, 4,096-token context, laptop CPU):
#   1. the whole assistant on demo_repo, to compare with experiments/results/7_assistant/agents_runE/runE
#   2. the repair loop on all 164 HumanEvalFix problems: fixed after 1, 2 and 3 attempts
set -uo pipefail
cd "$(dirname "$0")/../../.."
set -a; source .env; set +a
E=${GGUF_DIR:-$HOME/models/gguf}/qwen2.5-coder-3b-locali-mixv3s-q4_k_m.gguf
OUT=experiments/results/7_assistant/repair_step_runE
mkdir -p "$OUT/demo_repo" "$OUT/feedback"

"$HOME/tools/llama.cpp/build/bin/llama-server" -m "$E" --jinja --parallel 1 --cache-ram 0 -c 4096 \
    --host 127.0.0.1 --port 8093 --api-key "$LOCALI_MODEL_KEY" --spec-type ngram-simple > "$OUT/server.log" 2>&1 &
server=$!
trap 'kill "$server" 2>/dev/null' EXIT
for _ in $(seq 120); do curl -sf http://127.0.0.1:8093/health >/dev/null && break; sleep 2; done

PYTHONPATH=. uv run python experiments/scripts/assistant/agent_eval.py --base-url http://127.0.0.1:8093/v1 \
    --out "$OUT/demo_repo" > "$OUT/demo_repo/eval.log" 2>&1
echo "demo_repo exit $?"
uv run python experiments/scripts/assistant/feedback_repair.py --base-url http://127.0.0.1:8093/v1 \
    --model-id qwen2.5-coder-3b-ft-qlora-mixv3s-q4 --explain --retry-temperature 0.6 \
    --out "$OUT/feedback" > "$OUT/feedback/run.log" 2>&1
echo "feedback exit $?"
echo ALL DONE
