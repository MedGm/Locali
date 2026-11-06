# Capability study, step 1: what exactly changed on HumanEval+

Question: the fine-tuned 3B runs (A to E) score 6 to 9 points below the base on HumanEval+. Which
problems, how do the answers fail, and what differs between the base's answers and theirs? No new
generation: the saved greedy answers of the base and runs A to E (Kaggle T4, FP16), 2026-11-02.

## 1. The loss is 10 problems, not 6 to 9 points of general decline

| HumanEval+ (163) | Problems |
|---|---|
| base passes, all five fine-tuned runs pass | 101 |
| base fails, all five fail | 20 |
| **base passes, all five fail** | **10** |
| base fails, all five pass | 4 |
| flips between fine-tuned runs | 28 |

The 10: HumanEval/54, 55, 83, 86, 89, 97, 100, 141, 144, 154. The 4 gained: 59, 64, 99, 160.

## 2. The lost answers are wrong logic, mostly caught by the original tests

`experiments/scripts/stats/he_plus_probe.py` runs each answer against the original HumanEval tests
(humanevalpack) and compares it with the reference solution on every HumanEval+ input
(`probe.json`, sandboxed).

| Problem | Task | Base | Fine-tuned (E; A and D fail the same way) | Original tests | HumanEval+ inputs wrong |
|---|---|---|---|---|---|
| 54 | same set of characters | `set(s0) == set(s1)` | `sorted(s0) == sorted(s1)` (same multiset) | fail | 122 / 1006 |
| 83 | count n-digit numbers starting or ending with 1 | inclusion-exclusion, commented | `2 * 9**(n-1) - 8**(n-1)` (wrong formula) | fail | 108 / 109 |
| 100 | pile of stones, next odd/even | `+2` | `+1` if even, `+2` if odd (misreads "next even number") | fail | 56 / 112 |
| 141 | valid file name, 4 rules | one check per rule, commented | one regex, rules lost | fail | 18 / 1026 |
| 144 | is x * n a whole number | `Fraction` | hand-made modulo test, wrong | fail | 180 / 1010 |
| 89 | rotate letters by 4 | shifts letters only, both cases | shifts every character | fail (E: pass) | 472 / 1003 |
| 154 | rotation of b is a substring of a | checks `b in a` first | `len(b) > len(a)` guard, empty b wrong | pass (D: fail) | 3 / 1006 |
| 86 | sort the characters of each word | `split(' ')` keeps blanks | `split()` loses newlines and runs of spaces | pass | 108 / 1006 |
| 97 | product of the unit digits | `abs(a) % 10` | `a % 10`, wrong for negatives | pass | 441 / 976 |
| 55 | n-th Fibonacci | loop | naive recursion | pass | 20 / 45 time out |

Seven of the ten fail the original HumanEval tests: these are not missed edge cases but wrong
readings of the specification. The base's answers walk through the specification one rule at a
time, often with a comment per rule ("# Check for exactly one dot", "# Shift by 4 places"); the
fine-tuned answers compress it into one expression (regex, `sorted`, a closed formula, a
comprehension) and drop one rule on the way. The 4 gained problems are the mirror image: the base
is wrong on the original tests (59, 64, 99, 160), the fine-tuned runs are right on every input.

## 3. The same model writes in two styles, chosen by the prompt

| | HumanEval+ answers with comments | output tokens | MBPP+ answers with comments | output tokens |
|---|---|---|---|---|
| base | 0.35 | 242 | 0.98 | 123 |
| runs A to D | 0.01 | 97 (D) | 0.00 | 47 (D) |
| E (self-distilled replay) | 0.07 | 159 | **0.94** | **123** |

Comments themselves are not the cause: A to D dropped them on MBPP+ too and lost nothing there.
What stands out is E: on MBPP+ it writes exactly like the base, on HumanEval+ it still writes like
D. Both benchmarks use the same instruction with the problem in a code block; the difference is
what is in the block. MBPP+ puts an English sentence there, HumanEval+ puts Python code (a
signature and a docstring).

In the training mixture, every task row except replay (repair, review, tests, traces: 78 % of
rows) has Python code in a fenced block in the prompt, and its answer is terse code without
comments. Replay prompts are mostly English (62 % without a code block), and E changed exactly the
replay answers. The reading this suggests: **fine-tuning taught a prompt-format-to-style mapping.
Code in the prompt now triggers the "task" style learnt from repair and review, which rewrites
code compactly; English in the prompt triggers the general style.** HumanEval+ prompts look like
the repair prompts, so they get the repair style, and that style loses spec details on these 10
problems.

This is a hypothesis from correlations. Step 2 tests it directly.

## Next (step 2)

- Swap the formats: HumanEval+ problems written as English (the docstring as text, the signature
  named) and MBPP+ problems written as a code stub. If the hypothesis holds, D and E recover on
  English HumanEval+ and lose on code-stub MBPP+, while the base changes little.
- Is the correct program still in the fine-tuned model? Sample 20 answers per problem (T = 0.8)
  for base, D and E on HumanEval+, and score the log-probability of the base's correct program
  under D and E: forgetting, or only a changed first choice?
