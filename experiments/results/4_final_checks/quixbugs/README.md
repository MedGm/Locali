# QuixBugs harness check (pre-registered check, part 1, secondary benchmark)

Protocol: `docs/preregistration-repair.md`. Data: QuixBugs (github.com/jkoppel/QuixBugs at
4257f44b0ff1, MIT), the 40 Python programs. Built by `experiments/scripts/stats/quixbugs_check.py` on
2026-11-05, before any model answered them: every corrected version passes its tests, every buggy
version fails at least one, so all 40 are kept. Slow tests stay skipped, as in QuixBugs' own runner.

`items.jsonl`: each program with the failing test the prompt shows (a call with its expected result
for the JSON tests, the test function for the graph programs) and pytest's assertion message, or
"time limit exceeded" when the buggy version loops.

Code and text written with AI help (Claude); every figure above comes from the files listed here.
