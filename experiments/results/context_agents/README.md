# How much code should the agents show the model?

Run on 2026-10-17 on the laptop (i5-10210U, CPU only), llama.cpp, the fine-tuned Q8 model
(`ft-q8`), temperature 0, the full workflow on `demo_repo/`, scored against the planted-flaw key.
Code at commit `95b1d38`; scores recomputed from each saved run by
`experiments/scripts/context_table.py`. One run per setting.

The setting changes what the review and test-generation steps put in the prompt
(`backend/agents/context.py`); repair, docs and every other step are the same in all four runs.

- **file**: the whole file. Review makes one call per file instead of one per function.
- **function**: the function alone (Locali's default).
- **slice**: the function plus the constants, helpers and imports it uses (`backend/context_slice.py`).
- **compact**: the function without its docstring, comment-only lines and blank lines.

Findings are located in the original function in every setting, so the same lines are compared.

| Context | Review input tokens | Test-gen input tokens | All input tokens | Output tokens | Model time | Review hits on planted flaws | Model false positives | Bugs fixed / found / suspected | Tests kept / crashed |
|---|---|---|---|---|---|---|---|---|---|
| file | 2,034 | 3,868 | 6,915 | 3,087 | 7.2 min | 3 | 1 | 1 / 1 / 2 | 1 / 19 |
| function | 3,703 | 1,628 | 6,616 | 4,027 | 8.2 min | 4 | 17 | 1 / 2 / 2 | 1 / 23 |
| slice | 4,602 | 2,011 | 7,985 | 3,977 | 9.0 min | 4 | 6 | 1 / 2 / 1 | 2 / 27 |
| compact | 3,622 | 1,594 | 6,501 | 4,060 | 9.6 min | 4 | 17 | 1 / 2 / 2 | 2 / 23 |

"Review hits" are model findings on a planted bug or vulnerability line, in the right category.
The static tools find all 5 vulnerabilities and the secret in every run, so those are not in the
table. "Model time" is generation time on a laptop CPU and moves by a minute between runs for
reasons unrelated to the prompt (thermal throttling), so read it as rough.

## What I take from it

- **Whole files make the review quiet, not better.** One call per file is the cheapest review
  (2.0k input tokens, 305 output tokens for 6 files), and false positives drop to 1. But the model
  then writes very little: it finds 3 planted flaws instead of 4, misses the restock-boundary bug
  completely and only suspects the bulk-discount one. Test generation gets 2.4 times more input
  for the same number of kept tests. Whole files cost more where it matters and find less.
- **Slicing is the interesting one.** Showing the helpers and constants a function uses costs 24 %
  more review input and cuts the model's false positives from 17 to 6 with the same 4 hits. Most of
  the false positives with the function alone are invented lint remarks ("loop variable not used"
  where it is, "ambiguous variable name: total", `round` "without precision") and SQL-injection
  warnings on queries that already use parameters. With the slice, the ones in auth.py, pricing.py
  and most of inventory.py are gone; the db.py ones stay. Why more context quiets them I cannot
  tell from one run. Test generation kept 2 test files instead of 1. One bug moved from
  suspected to missed: in the function run it was suspected through a generated test, and with the
  slice that test was not written.
- **Compact prompts save almost nothing here.** demo_repo has few comments, so dropping them saves
  2 % of the input with the same results. The T4 repair ablation
  ([context_ablation_t4](../context_ablation_t4/README.md)) found the same: 14 % fewer input tokens
  for a small loss. It also removes docstrings, and the restock-boundary bug is only visible
  through its docstring ("at or below the threshold"), so it is not a safe default for review.
- **Locali keeps `function` as the default** and the others as a setting. The slice result is the
  best trade, but it is one run on one small repository; before making it the default I would want
  it on more code than demo_repo.

Together with the T4 ablation, this answers the C5 question for the workflow: a function plus the
one failing test and its error is enough context for repair, whole test suites and whole files
cost more without helping, and the cheapest real saving is in what is left out (other functions,
other tests), not in compressing what is kept.
