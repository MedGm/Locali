"""Pull Python code out of a model response."""

import re

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE = re.compile(r"```[ \t]*(?:python|py|python3)?[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_code(text: str, entry_point: str | None = None) -> str:
    """Return the most plausible code block.

    Order: a fenced block that defines `entry_point`, else the first fenced block,
    else the whole response. Reasoning inside <think> tags is ignored.
    """
    text = _THINK.sub("", text)
    blocks = [b.strip("\n") for b in _FENCE.findall(text)]
    if entry_point:
        defining = re.compile(rf"^\s*(async\s+)?def\s+{re.escape(entry_point)}\s*\(", re.MULTILINE)
        for block in blocks:
            if defining.search(block):
                return block
    if blocks:
        return blocks[0]
    return text.strip("\n")
