"""Helpers for the forced-divergence walk (capability study, step 3).

A follower model answers greedily; where its answer first leaves a leader model's answer, the
leader's token is forced and the follower continues. Token ids are those of the shared Qwen
tokenizer; top alternatives come from vLLM with return_tokens_as_token_ids ("token_id:<id>").
"""

import re

# The base model opens with "```\npython\n", the fine-tuned models with "```python\n".
FENCE = re.compile(r"\A```(?:python\n|\npython\n)")


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
