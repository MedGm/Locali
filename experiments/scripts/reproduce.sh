#!/usr/bin/env bash
# Rebuild every derived result from a clean checkout and compare it with what is committed.
#
#     bash experiments/scripts/reproduce.sh [workdir]
#
# A fresh git worktree of HEAD gets its own environment (uv sync --frozen), then:
#   - the results summary the web app shows (export_results.py)
#   - the agent context table (context_table.py, rescored from the saved runs)
#   - the serving tables and plots (serving_table.py)
#   - the other-languages table (multilang_table.py)
#   - the model red-team report, rescored from the saved answers (redteam_model.py, no model calls)
#   - the 16 red-team control cases, executed again (redteam.py, needs Docker)
# and every regenerated file is diffed against the committed one. Lines naming the commit are
# ignored. Model generations are not repeated here: they are the raw data the rest is built from.
set -euo pipefail

REPO=$(git rev-parse --show-toplevel)
WORK=${1:-$(mktemp -d /tmp/locali-reproduce-XXXX)}
CLEAN="$WORK/locali"
UV=${UV:-uv}

git -C "$REPO" worktree add --detach "$CLEAN" HEAD >/dev/null
trap 'git -C "$REPO" worktree remove --force "$CLEAN"' EXIT
cd "$CLEAN"
unset VIRTUAL_ENV  # the worktree has its own environment
echo "clean checkout of $(git rev-parse --short HEAD) in $CLEAN"
UV_LINK_MODE=hardlink "$UV" sync --frozen --quiet

export PYTHONPATH=.
"$UV" run python experiments/scripts/export_results.py >/dev/null
"$UV" run python experiments/scripts/context_table.py >/dev/null
"$UV" run python experiments/scripts/serving_table.py >/dev/null
"$UV" run python experiments/scripts/multilang_table.py experiments/results/multilang_t4_rescore \
    experiments/results/multilang_t4_rescore2 >/dev/null
LOCALI_MODEL_URL=http://127.0.0.1:9/v1 "$UV" run python experiments/scripts/redteam_model.py >/dev/null
"$UV" run python experiments/scripts/redteam.py >/dev/null

status=0
for f in experiments/results/summary.json \
         experiments/results/context_agents/table.md \
         experiments/results/serving_t4/tables.md \
         experiments/results/multilang_t4_rescore/table.md \
         experiments/results/serving_t4/throughput.png \
         experiments/results/serving_t4/latency.png \
         experiments/results/redteam/model.md \
         experiments/results/redteam/model.jsonl \
         experiments/results/redteam/controls.md; do
    if [[ $f == *.png ]]; then
        same=$(cmp -s <(git show "HEAD:$f") "$f" && echo yes || echo no)
    else
        same=$(cmp -s <(git show "HEAD:$f" | grep -v "at commit\|, commit \|generated_at") \
                      <(grep -v "at commit\|, commit \|generated_at" "$f") && echo yes || echo no)
    fi
    if [[ $same == yes ]]; then
        echo "same      $f"
    else
        echo "DIFFERENT $f"
        status=1
    fi
done
exit $status
