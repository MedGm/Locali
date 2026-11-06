# ConDefects harness check (pre-registered check, part 1)

Protocol: `docs/preregistration-repair.md` (registered in commit 15aa6b9). Data: ConDefects
(github.com/appmlk/ConDefects at 43f0834a82c5, data CC BY-SA 4.0; AtCoder test cases from its
`Test.zip`), Python programs from contests that started on or after 2024-02-01. Built by
`experiments/scripts/stats/condefects_check.py` on 2026-11-05, before any model answered these programs.

| | Programs | Tasks |
|---|---|---|
| Candidates | 489 | 161 |
| **Kept** (accepted version passes every test, faulty version fails one) | **382** | **129** |
| Dropped: the accepted version fails a test | 106 | |
| Dropped: the faulty version passes every test | 1 | |

Tests run smallest input first and stop at the first failure, so in `harness.json` "fails N of M
tests" means "fails a test": the tests after the first failure were not run. Of the 106 accepted
versions that fail, 18 import a library the sandbox does not have (`atcoder` 12, `sortedcontainers`
7, `numpy` 1, `pypyjit` 1; some import two). The other 87 use only the standard library; likely
causes, not told apart by the check, are solutions written for PyPy that are too slow for CPython
within 10 s, problems that accept several correct outputs, and interactive problems (abc355_e).

## Files

- `items.jsonl`: the 382 kept programs: faulty and accepted version, the test folder, and the
  failing test the prompt shows (smallest failing input, expected and actual output, cut at 1,000
  characters). Program text from ConDefects (CC BY-SA 4.0), test data from AtCoder.
- `harness.json`: counts and the reason for every dropped program.
- `format_check.jsonl`: the three programs from before 2023 used to check the prompt format.

Code and text written with AI help (Claude); every figure above comes from the files listed here.
