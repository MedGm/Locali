## Greedy pass@1 by prompt shape

| Model | HumanEval+ code (std) | HumanEval+ English | p | MBPP+ English (std) | MBPP+ code stub | p |
|---|---|---|---|---|---|---|
| base | 81.0% | 79.8% | 0.815 (10/8) | 64.5% | 69.5% | 0.0204 (21/40) |
| D | 71.8% | 73.6% | 0.375 (1/4) | 64.2% | 68.2% | 0.0534 (19/34) |
| E | 74.2% | 76.1% | 0.648 (8/11) | 64.2% | 68.2% | 0.0581 (20/35) |

| Model, task | answers with comments | output tokens |
|---|---|---|
| base, humaneval_plus | 0.36 | 242 |
| D, humaneval_plus | 0.01 | 96 |
| E, humaneval_plus | 0.07 | 160 |
| base, humaneval_plus_english | 0.63 | 172 |
| D, humaneval_plus_english | 0.00 | 66 |
| E, humaneval_plus_english | 0.18 | 88 |
| base, mbpp_plus | 0.98 | 123 |
| D, mbpp_plus | 0.00 | 47 |
| E, mbpp_plus | 0.94 | 123 |
| base, mbpp_plus_stub | 0.31 | 147 |
| D, mbpp_plus_stub | 0.00 | 65 |
| E, mbpp_plus_stub | 0.03 | 103 |

| Model vs base, paired | HumanEval+ code | HumanEval+ English | MBPP+ English | MBPP+ code stub |
|---|---|---|---|---|
| D | -9.2% (22/7, p 0.00813) | -6.1% (21/11, p 0.11) | -0.3% (26/25, p 1) | -1.3% (28/23, p 0.576) |
| E | -6.7% (19/8, p 0.0522) | -3.7% (15/9, p 0.307) | -0.3% (18/17, p 1) | -1.3% (26/21, p 0.56) |

Lost / gained problems, English prompt (pass = 1):

- base: lost-10 code 10, English 7; gained-4 code 0, English 2
- D: lost-10 code 0, English 1; gained-4 code 4, English 4
- E: lost-10 code 0, English 5; gained-4 code 4, English 1

## Sampling, HumanEval+ standard prompt, T = 0.8

| Model | pass@1 | pass@5 | pass@20 | lost-10 solved at least once | lost-10 pass rate |
|---|---|---|---|---|---|
| base | 76.6% | 88.8% | 92.0% | 9/10 | 56% |
| D | 68.0% | 86.8% | 92.0% | 10/10 | 31% |
| E | 72.9% | 87.0% | 92.0% | 9/10 | 30% |

Per lost problem, samples passing out of 20 (base / D / E):

- HumanEval/54: 16 / 12 / 15
- HumanEval/55: 17 / 6 / 0
- HumanEval/83: 0 / 3 / 4
- HumanEval/86: 3 / 3 / 4
- HumanEval/89: 14 / 5 / 10
- HumanEval/97: 16 / 9 / 5
- HumanEval/100: 12 / 13 / 11
- HumanEval/141: 9 / 2 / 2
- HumanEval/144: 20 / 6 / 6
- HumanEval/154: 4 / 3 / 2
- HumanEval/59 (gained): 14 / 15 / 18
- HumanEval/64 (gained): 9 / 10 / 15
- HumanEval/99 (gained): 15 / 11 / 18
- HumanEval/160 (gained): 4 / 20 / 12

## Log-probability of each model's greedy HumanEval+ answer, without the first 3 tokens

Mean per token, and in brackets the share of tokens below -2.

| Scored by \ answer of | base | D | E |
|---|---|---|---|
| base | -0.030 (0.0%) | -0.105 (1.6%) | -0.048 (0.5%) |
| D | -0.107 (1.4%) | -0.048 (0.0%) | -0.050 (0.4%) |
| E | -0.059 (0.8%) | -0.056 (0.6%) | -0.023 (0.0%) |

Nats the base's answer loses when D scores it instead of the base (median):

- both pass (110 problems): -17.5
- lost by D (22 problems): -25.0
- other (31 problems): -22.7

Lost-10: total log-probability of the base's (correct) answer under each model, the number of its tokens below -2 under D and E, and D's and E's own answers:

| Problem | tokens | base answer under base / D / E | tokens < -2 under D / E | D own | E own |
|---|---|---|---|---|---|
| HumanEval/54 | 161 | -2.9 / -8.6 / -4.7 | 0 / 0 | -2.2 | -3.1 |
| HumanEval/55 | 123 | -3.2 / -9.5 / -10.7 | 1 / 2 | -5.1 | -1.7 |
| HumanEval/83 | 236 | -31.4 / -50.8 / -33.2 | 6 / 6 | -7.9 | -8.1 |
| HumanEval/86 | 255 | -14.3 / -45.8 / -23.3 | 5 / 3 | -3.9 | -2.5 |
| HumanEval/89 | 258 | -11.6 / -37.2 / -23.4 | 7 / 4 | -4.7 | -6.1 |
| HumanEval/97 | 252 | -6.6 / -34.7 / -19.4 | 4 / 2 | -1.3 | -0.8 |
| HumanEval/100 | 219 | -8.3 / -27.4 / -21.1 | 4 / 4 | -6.7 | -2.7 |
| HumanEval/141 | 461 | -24.7 / -59.2 / -30.0 | 8 / 4 | -9.5 | -6.2 |
| HumanEval/144 | 225 | -7.3 / -26.6 / -11.0 | 3 / 1 | -4.0 | -4.8 |
| HumanEval/154 | 325 | -8.7 / -36.8 / -17.1 | 5 / 2 | -4.5 | -4.1 |
