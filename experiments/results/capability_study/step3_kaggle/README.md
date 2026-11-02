# Capability study, step 3: how far is a wrong answer from a right one?

Step 2 showed that the fine-tuned 3B models still solve every problem the base solves when
sampling (pass@20 equal) and that the base's correct answers stay likely under them. So the right
program is still in the model. This step asks how many decisions separate the wrong greedy answer
from the right one, and what those decisions are.

Job: `training/kaggle/divergence/kaggle_divergence.py` (Kaggle 2×T4, vLLM 0.29.0, FP16 + LoRA,
kernel version 4, 2026-11-02, 26 min of walks). Pure helpers with tests:
`evaluation/divergence.py`. Tables: `uv run python experiments/scripts/capability_step3.py
experiments/results/capability_study/step3_kaggle` (output in `tables.md`).

## Method: forced-divergence walk

For every HumanEval+ problem where one model's step 2 greedy answer passes (the leader) and
another's fails (the follower), 70 pairs in all:

1. The follower answers greedily. (Its answer matches the step 2 greedy answer in 68 of 70 walks;
   the other two differ through GPU non-determinism.)
2. At the first token where it leaves the leader's answer, the leader's token is forced, and the
   follower continues greedily.
3. This repeats until the answer passes the HumanEval+ tests, follows the leader to its end, or 12
   tokens have been forced.

The leader's answer gets the follower's code fence first (the base writes "```\npython\n", the
fine-tuned models "```python\n").

Control: a single changed token can flip pass/fail by luck. So for each walk, the follower's own
greedy answer is also changed at one place at a time: its own second choice, at 5 random positions
and at the 5 positions where it was least sure (lowest probability of the chosen token). 700
control answers in all.

## 1. One or two tokens are enough

| Follower ← leader | walks | passes after 1 forced | 2 | 3–5 | 6–12 | not within 12 | median |
|---|---|---|---|---|---|---|---|
| base ← D | 7 | 6 | 1 | 0 | 0 | 0 | 1 |
| base ← E | 8 | 8 | 0 | 0 | 0 | 0 | 1 |
| D ← base | 22 | 4 | 12 | 4 | 1 | 1 | 2 |
| D ← E | 9 | 3 | 3 | 2 | 1 | 0 | 2 |
| E ← base | 19 | 10 | 4 | 3 | 2 | 0 | 1 |
| E ← D | 5 | 4 | 0 | 1 | 0 | 0 | 1 |

69 of 70 failing answers pass after at most 12 forced tokens, in leader answers of 46 to 556 tokens.
The exception is D on HumanEval/83 (the counting formula, which the base itself solves in 0 of 20
samples, step 2). D needs 2 tokens in the median, E and the base 1.

The leader's token is rarely far down the follower's list. Rank among the follower's top 5 at all
156 divergences:

| Follower ← leader | divergences | rank 1 * | 2 | 3 | 4–5 | not in top 5 |
|---|---|---|---|---|---|---|
| D ← base | 63 | 11 | 24 | 14 | 4 | 10 |
| E ← base | 47 | 9 | 29 | 3 | 5 | 1 |
| all six directions | 156 | 28 | 82 | 22 | 12 | 12 |

\* See "Decoding settings" below: rank 1 means the repetition penalty, not the model, chose
another token.

## 2. Better than luck, except D's first step

How often does one changed token make the follower's answer pass?

| Follower ← leader | leader's token at the first divergence | own second choice, least sure positions | own second choice, random positions |
|---|---|---|---|
| base ← D | 6/7 (86 %) | 11/35 (31 %) | 4/35 (11 %) |
| base ← E | 8/8 (100 %) | 5/40 (12 %) | 0/40 (0 %) |
| D ← base | 4/22 (18 %) | 27/110 (25 %) | 8/110 (7 %) |
| D ← E | 3/9 (33 %) | 8/45 (18 %) | 7/45 (16 %) |
| E ← base | 10/19 (53 %) | 26/95 (27 %) | 13/95 (14 %) |
| E ← D | 4/5 (80 %) | 11/25 (44 %) | 2/25 (8 %) |

- Luck is real: changing one uncertain token alone fixes 12 to 44 % of answers. The walks must be
  read against that.
- For the base, E, and E ← D, the leader's token at the first divergence beats the control by a
  wide margin. The divergence point is a real decision.
- For D following the base, the first forced token (18 %) is no better than a nudge at an
  uncertain position (25 %). D's first divergence is mostly not the decision that matters (next
  section). There is no matched control for "2 forced tokens", so the two-token result for D is
  suggestive, not proven.

## 3. What the decisions are: the base spells things out, the fine-tuned models do not

What the leader writes at the first divergence:

| Follower ← leader | docstring or comment | import | signature | code |
|---|---|---|---|---|
| D ← base | 16 | 2 | 0 | 4 |
| E ← base | 7 | 3 | 1 | 8 |
| D ← E | 5 | 1 | 0 | 3 |
| base ← D or E | 1 | 1 | 3 | 10 |

- In 16 of 22 cases, the base starts the body by restating the docstring or with a comment,
  where D goes straight to code. That is the style difference of step 1. Forcing it alone rarely
  fixes D's answer: D restates the docstring and then still writes its compact version.
- The second forced token (D ← base, 18 walks) is where the base spells out its approach and D
  does not:
  - a step comment in 4 walks (HumanEval/70, 97, 144, 154; for example
    `# Get the unit digit of each number`);
  - a setup variable before a loop in 3 (68, 89, 142);
  - a helper function in 2 (86, 139);
  - a different code choice in the rest.
- D's side at these points is often a one-line `return` built from a comprehension or library
  call. Examples:

  | Problem | D writes | The base writes, and D completes correctly |
  |---|---|---|
  | HumanEval/97 | `return (a % 10) * (b % 10)` (wrong for negative numbers) | `# Get the unit digit of each number` |
  | HumanEval/154 | `return any(b in a[i:] + a[:i] for i in range(len(b)))` | `# Check if the second word is a substring of the first word` |
  | HumanEval/144 | a one-line `Fraction` comparison | `# Convert the string representations of the fractions to Fraction objects` |
- E, trained on its own (the base's) replay answers, diverges at a docstring or comment less often
  (7 of 19) and needs fewer tokens (median 1).

## Decoding settings (also applies to step 2)

The vLLM server used the model's `generation_config.json` as default sampling parameters:
repetition penalty 1.05, top-k 20, top-p 0.8, temperature 0.7. Each request set temperature (0
for greedy, 0.8 for samples) and step 2's samples also set top-p 0.95. So:

- the step 2 greedy runs and these walks used repetition penalty 1.05;
- the step 2 samples also used top-k 20.

This is the same for all three models, so the comparisons hold. But the Kaggle vLLM numbers are not
decoded exactly like the laptop's llama.cpp runs (no penalty). The returned log-probabilities
are raw, before the penalty. The 28 rank-1 divergences above are places where the penalty, not
the model's own preference, made the follower pick another token. Setting `--generation-config
vllm` would turn this off.

## What this says

- A fine-tuned model's wrong answer is one or two decisions away from a right one, and the right
  token is usually the model's second or third choice.
- The decisions that matter are about how much the answer spells out: comments, setup variables
  and helper functions versus a compact one-liner. The base's spelled-out style seems to work as a
  small plan written before the code; fine-tuning on short target answers removed it. On MBPP+
  (simpler tasks) the compact style costs nothing (step 2); on HumanEval+ it skips edge cases.
- Not tested yet: whether making the fine-tuned model spell things out (a forced comment line, an
  instruction, or training targets that keep the comments) recovers HumanEval+ on all problems,
  not just the 70 studied here, and what the repetition penalty contributes.

## Files

- `walks.jsonl`: one walk per row (follower, leader, problem, every step with its text, score and
  divergence, and the 10 control nudges).
- `logs/`: vLLM and setup logs; `kaggle_kernel.log` is the notebook log.
- `tables.md`: output of the analysis script.

Code and text written with AI help (Claude); every figure above comes from the files listed here.
