Base vs fine-tuned with a correction for testing many tasks at once. 

Bold: significantly better after Holm within its family (adjusted p < 0.05); italic: significantly worse. Built by `experiments/scripts/multiple_comparisons.py`.

## 3B run D

Confirmatory (2 tests, Holm within the family)

| Task | n | Base % | Fine-tune % | Δ points | only base / only fine-tune | p | Holm p |
|---|---|---|---|---|---|---|---|
| humanevalfix | 164 | 46.3 | **61.6** | +15.2 | 11 / 36 | 0.00035 | 0.00035 |
| testgen | 164 | 62.2 | **82.9** | +20.7 | 11 / 45 | 5.4e-06 | 1.1e-05 |

Exploratory (9 tests, Holm within the family)

| Task | n | Base % | Fine-tune % | Δ points | only base / only fine-tune | p | Holm p |
|---|---|---|---|---|---|---|---|
| humaneval_plus | 163 | 81.0 | 72.4 | -8.6 | 21 / 7 | 0.013 | 0.088 |
| mbpp_plus | 377 | 64.7 | 64.2 | -0.5 | 27 / 25 | 0.89 | 1 |
| completion | 163 | 56.4 | 62.0 | +5.5 | 7 / 16 | 0.093 | 0.37 |
| cruxeval_o | 800 | 42.2 | 43.4 | +1.1 | 37 / 46 | 0.38 | 1 |
| refactor | 163 | 86.5 | 87.7 | +1.2 | 11 / 13 | 0.84 | 1 |
| bugdetect | 328 | 61.6 | 67.4 | +5.8 | 26 / 45 | 0.032 | 0.16 |
| vulndetect | 712 | 54.9 | 52.7 | -2.2 | 31 / 15 | 0.026 | 0.16 |
| securecodegen | 121 | 69.4 | **81.8** | +12.4 | 2 / 17 | 0.00073 | 0.0066 |
| humanevalexplain | 164 | 68.3 | 57.9 | -10.4 | 27 / 10 | 0.0076 | 0.061 |

## 3B run E (default)

Confirmatory (2 tests, Holm within the family)

| Task | n | Base % | Fine-tune % | Δ points | only base / only fine-tune | p | Holm p |
|---|---|---|---|---|---|---|---|
| humanevalfix | 164 | 46.3 | **63.4** | +17.1 | 10 / 38 | 6.2e-05 | 6.2e-05 |
| testgen | 164 | 62.2 | **82.3** | +20.1 | 11 / 44 | 8.7e-06 | 1.7e-05 |

Exploratory (9 tests, Holm within the family)

| Task | n | Base % | Fine-tune % | Δ points | only base / only fine-tune | p | Holm p |
|---|---|---|---|---|---|---|---|
| humaneval_plus | 163 | 81.0 | 74.8 | -6.1 | 18 / 8 | 0.076 | 0.45 |
| mbpp_plus | 377 | 64.7 | 64.2 | -0.5 | 18 / 16 | 0.86 | 1 |
| completion | 163 | 56.4 | **65.6** | +9.2 | 2 / 17 | 0.00073 | 0.0058 |
| cruxeval_o | 800 | 42.2 | 43.6 | +1.4 | 30 / 41 | 0.24 | 1 |
| refactor | 163 | 86.5 | 87.7 | +1.2 | 12 / 14 | 0.85 | 1 |
| bugdetect | 328 | 61.6 | 66.5 | +4.9 | 20 / 36 | 0.044 | 0.31 |
| vulndetect | 712 | 54.9 | 54.5 | -0.4 | 14 / 11 | 0.69 | 1 |
| securecodegen | 121 | 69.4 | **82.6** | +13.2 | 1 / 17 | 0.00014 | 0.0013 |
| humanevalexplain | 164 | 68.3 | 68.3 | +0.0 | 15 / 15 | 1 | 1 |

## 1.5B QLoRA v2 (fast option)

Confirmatory (2 tests, Holm within the family)

| Task | n | Base % | Fine-tune % | Δ points | only base / only fine-tune | p | Holm p |
|---|---|---|---|---|---|---|---|
| humanevalfix | 164 | 25.0 | **36.0** | +11.0 | 11 / 29 | 0.0064 | 0.0064 |
| testgen | 164 | 46.3 | **82.3** | +36.0 | 9 / 68 | 2.4e-12 | 4.9e-12 |

Exploratory (9 tests, Holm within the family)

| Task | n | Base % | Fine-tune % | Δ points | only base / only fine-tune | p | Holm p |
|---|---|---|---|---|---|---|---|
| humaneval_plus | 163 | 65.0 | 62.0 | -3.1 | 21 / 16 | 0.51 | 1 |
| mbpp_plus | 377 | 56.2 | **62.1** | +5.8 | 18 / 40 | 0.0054 | 0.037 |
| completion | 163 | 35.6 | 36.8 | +1.2 | 11 / 13 | 0.84 | 1 |
| cruxeval_o | 800 | 30.1 | 28.7 | -1.4 | 53 / 42 | 0.3 | 1 |
| refactor | 163 | 69.9 | **93.9** | +23.9 | 3 / 42 | 8.7e-10 | 7.8e-09 |
| bugdetect | 328 | 53.0 | **65.5** | +12.5 | 45 / 86 | 0.00043 | 0.0034 |
| vulndetect | 712 | 51.0 | 51.5 | +0.6 | 10 / 14 | 0.54 | 1 |
| securecodegen | 121 | 76.9 | 81.0 | +4.1 | 1 / 6 | 0.12 | 0.75 |
| humanevalexplain | 164 | 56.7 | 53.0 | -3.7 | 22 / 16 | 0.42 | 1 |

