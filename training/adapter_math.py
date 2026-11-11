"""Arithmetic on LoRA adapters, without the base model: scale one, or average two.

A LoRA layer adds (alpha / r) * B @ A to a weight. Scaling B by s scales that change by s.
The average of two adapters is exact as one adapter of twice the rank: A stacked, B side by side
with the weights applied, so B @ A = w1 * B1 @ A1 + w2 * B2 @ A2. Its config needs r and
lora_alpha doubled, so alpha / r stays what it was.

Works on dicts of arrays (numpy or torch) as loaded from adapter_model.safetensors.
"""

import numpy as np


def scale(state: dict, factor: float) -> dict:
    """The adapter whose change to every weight is `factor` times the original's."""
    return {k: v * factor if ".lora_B." in k else v for k, v in state.items()}


def average(first: dict, second: dict, weight: float = 0.5) -> dict:
    """weight * first + (1 - weight) * second, as one adapter of the summed rank."""
    assert first.keys() == second.keys(), "adapters target different layers"
    out = {}
    for key, value in first.items():
        if ".lora_A." in key:
            out[key] = np.concatenate([value, second[key]], axis=0)
        elif ".lora_B." in key:
            out[key] = np.concatenate([value * weight, second[key] * (1 - weight)], axis=1)
        else:
            raise ValueError(f"not a LoRA tensor: {key}")
    return out


def averaged_config(config: dict) -> dict:
    return {**config, "r": 2 * config["r"], "lora_alpha": 2 * config["lora_alpha"]}
