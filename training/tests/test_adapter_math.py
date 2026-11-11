import numpy as np

from training.adapter_math import average, averaged_config, scale

RNG = np.random.default_rng(0)


def adapter() -> dict:
    return {"m.q_proj.lora_A.weight": RNG.normal(size=(2, 5)), "m.q_proj.lora_B.weight": RNG.normal(size=(4, 2))}


def delta(state: dict) -> np.ndarray:
    return state["m.q_proj.lora_B.weight"] @ state["m.q_proj.lora_A.weight"]


def test_scaling_scales_the_weight_change_and_leaves_the_input_alone():
    a = adapter()
    before = delta(a)
    assert np.allclose(delta(scale(a, 0.5)), 0.5 * before) and np.allclose(delta(a), before)


def test_average_is_exact_at_twice_the_rank():
    a, b = adapter(), adapter()
    merged = average(a, b, weight=0.25)
    assert merged["m.q_proj.lora_A.weight"].shape == (4, 5) and merged["m.q_proj.lora_B.weight"].shape == (4, 4)
    assert np.allclose(delta(merged), 0.25 * delta(a) + 0.75 * delta(b))
    assert averaged_config({"r": 16, "lora_alpha": 16, "x": 1}) == {"r": 32, "lora_alpha": 32, "x": 1}
