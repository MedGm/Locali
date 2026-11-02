"""Helpers for the forced-divergence walk (capability study, step 3).

A follower model answers greedily; where its answer first leaves a leader model's answer, the
leader's token is forced and the follower continues. Token ids are those of the shared Qwen
tokenizer; top alternatives come from vLLM with return_tokens_as_token_ids ("token_id:<id>").
"""

import random
import re

# The base model opens with "```\npython\n", the fine-tuned models with "```python\n".
FENCE = re.compile(r"\A```(?:python\n|\npython\n)")
FENCE_TOKENS = 3


def first_divergence(continuation: list[int], leader: list[int], offset: int) -> int | None:
    """Position in the leader of the first continuation token that differs from it.

    The continuation was generated after the first `offset` leader tokens. None if it agrees with
    the leader for as long as both last.
    """
    for j, token in enumerate(continuation):
        if offset + j >= len(leader):
            return None
        if token != leader[offset + j]:
            return offset + j
    return None


def refence(leader_text: str, follower_text: str) -> str:
    """The leader's answer with its opening code fence written the way the follower writes it."""
    lead, follow = FENCE.match(leader_text), FENCE.match(follower_text)
    if not lead or not follow:
        return leader_text
    return follow.group(0) + leader_text[lead.end():]


def rank_of(token: int, top: dict[str, float]) -> int | None:
    """1-based rank of a token id among top alternatives, None if it is not among them."""
    ordered = sorted(top, key=top.get, reverse=True)
    key = f"token_id:{token}"
    return ordered.index(key) + 1 if key in ordered else None


def nudge_positions(n_tokens: int, k: int, seed: str) -> list[int]:
    """Up to k distinct random positions in an answer of n_tokens, after the fence, before the last.

    Used for the control: does forcing any other likely token, not the leader's, also flip the result?
    """
    candidates = range(FENCE_TOKENS, n_tokens - 1)
    return sorted(random.Random(seed).sample(candidates, min(k, len(candidates))))


def second_choice(token: int, top: dict[str, float]) -> int | None:
    """The most likely alternative to `token` among the top alternatives."""
    others = [t for t in sorted(top, key=top.get, reverse=True) if t != f"token_id:{token}"]
    return int(others[0].split(":", 1)[1]) if others else None


def uncertain_positions(chosen_logprobs: list[float], k: int, exclude: int | None) -> list[int]:
    """The k positions after the fence (and before the last token) where the model was least sure
    of the token it chose, in answer order. `exclude` (the first divergence) is skipped."""
    candidates = [i for i in range(FENCE_TOKENS, len(chosen_logprobs) - 1) if i != exclude]
    return sorted(sorted(candidates, key=lambda i: chosen_logprobs[i])[:k])
