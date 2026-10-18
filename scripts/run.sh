#!/usr/bin/env bash
# Start one part of Locali with the settings in the repository's .env (one part per terminal).
#
#     scripts/run.sh model      # the assistant's model server (llama.cpp)
#     scripts/run.sh compare    # optional second model, for the playground
#     scripts/run.sh backend    # the API
#     scripts/run.sh web        # the web app, http://localhost:3000
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] || { echo "no .env: copy .env.example to .env and fill it in" >&2; exit 1; }
set -a
# shellcheck disable=SC1091
source .env
set +a

port() { local p=${1##*:}; echo "${p%%/*}"; }
serve() {  # model file, url, key
    exec "${LOCALI_LLAMA_SERVER:-$HOME/tools/llama.cpp/build/bin/llama-server}" -m "$1" --jinja --parallel 1 \
        --cache-ram 0 -c 4096 --host 127.0.0.1 --port "$(port "$2")" --api-key "$3"
}

case "${1:-}" in
    model) serve "$LOCALI_MODEL_FILE" "$LOCALI_MODEL_URL" "$LOCALI_MODEL_KEY" ;;
    compare) serve "$LOCALI_COMPARE_FILE" "$LOCALI_COMPARE_URL" "$LOCALI_COMPARE_KEY" ;;
    backend) exec uv run uvicorn backend.app:default_app --factory --host 127.0.0.1 --port "$(port "${LOCALI_API_URL:-:8000}")" ;;
    web) cd frontend && exec npm run dev ;;
    *) echo "usage: scripts/run.sh model|compare|backend|web" >&2; exit 2 ;;
esac
