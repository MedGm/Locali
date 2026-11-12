# The repair step after 2026-11-11, on the laptop

Run E as the app serves it (Q4_K_M, llama.cpp 987498f with n-gram lookup, 4,096-token context,
laptop CPU), 2026-11-11/12, `experiments/scripts/laptop/laptop_fixprompt.sh`. Descriptive, as
registered in `docs/preregistration-runs-fg.md`.

The debug agent now asks for the fix in the benchmark format (the function and the failing tests,
answer = the fixed function), retries with the new error at temperature 0.6, and asks for the
explanation only after a fix passes (`backend/agents/debug.py`).

## The repair loop on HumanEvalFix (`feedback/`)

All 164 bugs, up to three attempts, errors explained (`evaluation/feedback_repair.py --explain
--retry-temperature 0.6`). This is the loop the agent copies, not the agent itself: the prompt of
the benchmark, with the test error added on retries.

| Fixed within | of 164 | |
|---|---|---|
| 1 attempt | 95 | 57.9 % |
| 2 attempts | 102 | 62.2 % |
| 3 attempts | 106 | 64.6 % |

295 model calls. The first attempt gives the same 95 as the single-attempt laptop run of this file.
The two retries add 11 fixes. For comparison, the old repair format (diagnosis first, then code)
fixed 59 of the same 164 bugs in one attempt on Kaggle at 16 bits.

## The whole assistant on `demo_repo` (`demo_repo/`)

Same result as before the change (`../agents_runE/runE`): 1 of 6 planted bugs fixed, 3 found,
1 suspected, 1 missed; the same 4 tests kept; coverage 27.7 % to 72.0 %. Only one planted bug has a
failing test in this project, so the debug agent is called for one bug (2 model calls now: the fix,
then the explanation). The project is too small to show the gain of the table above.

Code and text written with AI help (Claude).
