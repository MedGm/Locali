"""Unbiased pass@k estimator (Chen et al., 2021, "Evaluating Large Language Models Trained on Code")."""

from math import comb


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that at least one of k samples, drawn from n with c correct, passes."""
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)
