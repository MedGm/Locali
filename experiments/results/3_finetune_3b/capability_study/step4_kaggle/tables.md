## HumanEval+ pass@1 (163 problems), greedy

| Model | penalty | standard | comments | scaffold |
|---|---|---|---|---|
| base | 1.05 | 132 (81.0%) | 124 (76.1%) | 116 (71.2%) |
| base | 1.0 | 130 (79.8%) | 133 (81.6%) | 119 (73.0%) |
| D | 1.05 | 117 (71.8%) | 120 (73.6%) | 109 (66.9%) |
| D | 1.0 | 117 (71.8%) | 122 (74.8%) | 115 (70.6%) |
| E | 1.05 | 121 (74.2%) | 123 (75.5%) | 121 (74.2%) |
| E | 1.0 | 127 (77.9%) | 126 (77.3%) | 119 (73.0%) |

## Against the same model's standard prompt, penalty 1.05 (only standard / only this, exact McNemar)

| Model | comments, 1.05 | scaffold, 1.05 | standard, 1.0 | comments, 1.0 | scaffold, 1.0 |
|---|---|---|---|---|---|
| base | 12/4, p 0.077 | 21/5, p 0.0025 | 8/6, p 0.79 | 8/9, p 1 | 18/5, p 0.011 |
| D | 4/7, p 0.55 | 22/14, p 0.24 | 9/9, p 1 | 9/14, p 0.4 | 19/17, p 0.87 |
| E | 8/10, p 0.81 | 17/17, p 1 | 4/10, p 0.18 | 10/15, p 0.42 | 17/15, p 0.86 |

## Against the base in the same condition (only base / only fine-tuned)

| Model | standard, 1.05 | comments, 1.05 | scaffold, 1.05 | standard, 1.0 | comments, 1.0 | scaffold, 1.0 |
|---|---|---|---|---|---|---|
| D | -9.2% (22/7, p 0.0081) | -2.5% (19/15, p 0.61) | -4.3% (18/11, p 0.26) | -8.0% (24/11, p 0.041) | -6.7% (21/10, p 0.071) | -2.5% (14/10, p 0.54) |
| E | -6.7% (19/8, p 0.052) | -0.6% (13/12, p 1) | +3.1% (7/12, p 0.36) | -1.8% (12/9, p 0.66) | -4.3% (12/5, p 0.14) | +0.0% (5/5, p 1) |

## Style, penalty 1.05: comment lines in the body per answer, output tokens, lost-10 passed

| Model | condition | comment lines | output tokens | lost-10 passed | cut off (length) |
|---|---|---|---|---|---|
| base | standard | 1.0 | 242 | 10 | 0 |
| base | comments | 3.9 | 252 | 8 | 0 |
| base | scaffold | 3.4 | 154 | 6 | 0 |
| D | standard | 0.0 | 97 | 0 | 0 |
| D | comments | 0.0 | 172 | 2 | 1 |
| D | scaffold | 2.4 | 88 | 4 | 0 |
| E | standard | 0.2 | 159 | 0 | 0 |
| E | comments | 1.6 | 211 | 4 | 0 |
| E | scaffold | 4.0 | 138 | 7 | 0 |
