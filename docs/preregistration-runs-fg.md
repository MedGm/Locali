# Rules fixed before runs F and G, the adapter variants and the quantization check

Written 2026-11-11, before any of these models or files answered a benchmark. The commit that adds
this file is the registration. Tests are exact McNemar tests on the same problems, as everywhere
else; the secondary tests of one run are Holm-corrected together.

## Run F: fix first, diagnosis after

Same data, recipe and seed as run E, except that the 3,795 repair-format rows ask for the fixed
function and then the diagnosis (`training/data/build_mix_v3f.py`).

- **Primary:** HumanEvalFix in the repair format, run F with the code-first prompt
  (`humanevalfix_t1fmt_codefirst`) against run E with the diagnosis-first prompt
  (`humanevalfix_t1fmt`, 59 of 164). "The order matters" is claimed only if F is better with
  p < 0.05.
- **Secondary, F against E:** HumanEvalFix in the benchmark format, HumanEval+, MBPP+, test
  generation, explaining code. F replaces E as the default only if the primary holds and none of
  these is significantly worse.

## Run G: real bugs in the training data

Run E's data plus ConDefects Python programs from contests **before 2024-02-01**, in the prompt of
the real-bug check (`training/data/real_bugs.py`, `build_mix_v3r.py`). The check itself uses
contests from 2024-02-01 on, so no task is shared; rows that share 13 words in a row with one of its
382 programs are dropped.

- **Primary:** ConDefects (382 programs), run G against the 3B base (54 fixed). "Training on real
  bugs helps on real bugs" is claimed only if G is better with p < 0.05.
- **Secondary:** G against E on ConDefects, QuixBugs, HumanEvalFix, HumanEval+, MBPP+, test
  generation.
- To be said with the result: G is trained on the same site and the same prompt as the check, so a
  gain shows that real examples help on bugs of this kind; it does not show a gain on bugs from
  elsewhere. QuixBugs is the only set here from another source.

## Adapter variants (run E at half and three-quarter strength, average of D and E)

Exploratory: three variants and three benchmarks, chosen by looking at them. A variant that looks
better than run E on HumanEval+ without losing HumanEvalFix is then run once on ConDefects and test
generation, which were not used to pick it, and only that second result is reported as a finding.

## Quantization (f16, Q8_0, Q5_K_M, Q4_K_M, Q4_K_M with an importance matrix)

Descriptive: every file on the same llama.cpp build, HumanEvalFix and HumanEval+, each file against
f16. The laptop default changes only if a file of at most 2.6 GB is better than Q4_K_M on
HumanEvalFix with p < 0.05; otherwise the Q4_K_M gap between runs D and E is reported as noise.

## The assistant's repair step

Changed on 2026-11-11 to ask in the benchmark format, with sampled retries
(`backend/agents/debug.py`), because run E had already been measured in both formats on the same
164 bugs (104 against 59 fixed). Its check is descriptive: the repair loop on the laptop (Q4_K_M,
three attempts) and one run of the whole assistant on `demo_repo`.

Code and text written with AI help (Claude).
