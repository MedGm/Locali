## Forced tokens until the follower's answer passes

| Follower ← leader | walks | first answer = step 2 greedy | passes with 0 forced | 1 forced | 2 forced | 3-5 forced | 6-12 forced | not within 12 |
|---|---|---|---|---|---|---|---|---|
| base ← D | 7 | 7 | 0 | 6 | 1 | 0 | 0 | 0 |
| base ← E | 8 | 8 | 0 | 8 | 0 | 0 | 0 | 0 |
| D ← base | 22 | 21 | 0 | 4 | 12 | 4 | 1 | 1 |
| D ← E | 9 | 9 | 0 | 3 | 3 | 2 | 1 | 0 |
| E ← base | 19 | 19 | 0 | 10 | 4 | 3 | 2 | 0 |
| E ← D | 5 | 4 | 0 | 4 | 0 | 1 | 0 | 0 |

## Rank of the leader's token among the follower's top 5, at each divergence

Raw log-probabilities. vLLM applied the model's generation_config (repetition penalty 1.05), so the leader's token can rank 1 when the penalty made the follower choose another.

| Follower ← leader | divergences | rank 1 | rank 2 | rank 3 | rank 4-5 | rank not in top 5 | median log-prob gap (follower's token − leader's) |
|---|---|---|---|---|---|---|---|
| base ← D | 8 | 0 | 4 | 1 | 3 | 0 | 2.24 |
| base ← E | 8 | 1 | 6 | 1 | 0 | 0 | 0.20 |
| D ← base | 63 | 11 | 24 | 14 | 4 | 10 | 0.62 |
| D ← E | 23 | 6 | 13 | 3 | 0 | 1 | 0.36 |
| E ← base | 47 | 9 | 29 | 3 | 5 | 1 | 1.05 |
| E ← D | 7 | 1 | 6 | 0 | 0 | 0 | 1.12 |

## Control: does any single nudge fix the answer?

One forced token each. Leader: the leader's token at the first divergence. Uncertain: the follower's own second choice at one of its 5 least sure positions. Random: its second choice at a random position.

| Follower ← leader | leader's token at first divergence | uncertain nudge | random nudge |
|---|---|---|---|
| base ← D | 6/7 (86%) | 11/35 (31%) | 4/35 (11%) |
| base ← E | 8/8 (100%) | 5/40 (12%) | 0/40 (0%) |
| D ← base | 4/22 (18%) | 27/110 (25%) | 8/110 (7%) |
| D ← E | 3/9 (33%) | 8/45 (18%) | 7/45 (16%) |
| E ← base | 10/19 (53%) | 26/95 (27%) | 13/95 (14%) |
| E ← D | 4/5 (80%) | 11/25 (44%) | 2/25 (8%) |

## What the leader writes at the first divergence

| Follower ← leader | docstring or comment | import | signature | code |
|---|---|---|---|---|
| base ← D | 1 | 0 | 1 | 5 |
| base ← E | 0 | 1 | 2 | 5 |
| D ← base | 16 | 2 | 0 | 4 |
| D ← E | 5 | 1 | 0 | 3 |
| E ← base | 7 | 3 | 1 | 8 |
| E ← D | 0 | 0 | 0 | 5 |

## The lost 10: follower D or E, leader base

| Problem | follower | forced to pass | first divergence: leader's line vs follower's line | leader rank |
|---|---|---|---|---|
| HumanEval/54 | D | 5 | `` + `from typing import *` vs `def same_chars(s0: str, s1: str) -> bool:` | 2 |
| HumanEval/54 | E | 2 | `` + `from typing import *` vs `def same_chars(s0: str, s1: str) -> bool:` | 2 |
| HumanEval/55 | D | 4 | `` + ` """Return n-th Fibonacci number.` vs ` if n <= 1:` | 1 |
| HumanEval/55 | E | 4 | `def fib(n: int` + `) -> int:` vs `):` | 2 |
| HumanEval/83 | D | not within 12 | `` + ` """` vs ` if n == 1:` | 2 |
| HumanEval/83 | E | 12 | `` + ` """` vs ` if n == 1:` | 1 |
| HumanEval/86 | D | 6 | `` + ` """` vs ` return ' '.join([''.join(sorted(word)) for word in s.split()])` | 1 |
| HumanEval/86 | E | 7 | `` + ` def sort_word(word):` vs ` return ' '.join([''.join(sorted(word)) for word in s.split()])` | 2 |
| HumanEval/89 | D | 2 | `` + ` """Create a function encrypt that takes a string as an argument and` vs ` alphabet = 'abcdefghijklmnopqrstuvwxyz'` | 3 |
| HumanEval/89 | E | 1 | `` + ` encrypted = ""` vs ` return ''.join(chr((ord(c) - ord('a') + 4) % 26 + ord('a')) for c in s)` | 2 |
| HumanEval/97 | D | 2 | `` + ` """Complete the function that takes two integers and returns ` vs ` return (a % 10) * (b % 10)` | 2 |
| HumanEval/97 | E | 1 | `` + ` # Get the unit digit of each number` vs ` return (a % 10) * (b % 10)` | 4-5 |
| HumanEval/100 | D | 2 | `` + ` stones = []` vs ` result = [n]` | 1 |
| HumanEval/100 | E | 2 | `` + ` stones = []` vs ` result = [n]` | 1 |
| HumanEval/141 | D | 1 | `` + `def file_name_check(file_name):` vs `import re` | 2 |
| HumanEval/141 | E | 1 | `` + `def file_name_check(file_name):` vs `import re` | 1 |
| HumanEval/144 | D | 2 | `` + ` """Your task is to implement a function that will simplify the expression` vs ` return Fraction(x) * Fraction(n).denominator == Fraction(n) * Fraction(x).denominator` | not in top 5 |
| HumanEval/144 | E | 3 | `` + `from fractions import Fraction` vs `def simplify(x, n):` | 2 |
| HumanEval/154 | D | 2 | `` + ` """You are given 2 words. You need to return True if the second word or any of its rotations is a substring in the first word` vs ` return any(b in a[i:] + a[:i] for i in range(len(b)))` | 3 |
| HumanEval/154 | E | 1 | `` + ` # Check if the second word is a substring of the first word` vs ` if len(b) > len(a):` | 4-5 |
