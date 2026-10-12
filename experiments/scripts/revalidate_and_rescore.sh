#!/usr/bin/env bash
# After any scoring/extraction change: re-validate every task with reference answers, then
# re-score all stored runs. Run from the repository root.
set -euo pipefail
UV=${UV:-$HOME/.local/bin/uv}
VAL=experiments/results/harness_validation
TASKS=(humaneval_plus mbpp_plus humanevalfix bugdetect cruxeval_o testgen refactor completion securecodegen vulndetect)

for task in "${TASKS[@]}"; do
  rm -rf "${VAL:?}/${task:?}"
  "$UV" run python -m evaluation.run --benchmark "$task" --reference --workers 4 --out "$VAL/$task" >/dev/null 2>&1
  python3 -c "import json,sys; m=json.load(open('$VAL/$task/summary.json'))['metrics']; print('VALIDATION $task', m['n'], m['status_counts'])"
done

runs=$(find experiments/results/baselines experiments/results/kaggle_baselines_20261012/results -name summary.json -printf '%h\n' | sort)
# shellcheck disable=SC2086
"$UV" run python -m evaluation.rescore $runs 2>/dev/null | sed 's#experiments/results/##'
echo "DONE"
