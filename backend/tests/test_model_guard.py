from dataclasses import dataclass

from backend.agents.model import guarded

KEY = "AKIA" + "IOSFODNN7EXAMPLE"


@dataclass
class Reply:
    text: str
    input_tokens: int
    output_tokens: int


def test_outgoing_messages_are_redacted_and_calls_recorded():
    seen, log = [], []
    model = guarded(lambda msgs: (seen.append(msgs), Reply("ok " + KEY, 12, 3))[1], log.append, step=lambda: "debug")
    assert model([{"role": "user", "content": f'key = "{KEY}"'}]) == "ok [REDACTED:aws-access-key]"
    assert KEY not in seen[0][0]["content"]
    [entry] = log
    assert entry["step"] == "debug" and entry["input_tokens"] == 12 and entry["output_tokens"] == 3
    assert KEY not in str(entry) and entry["latency_s"] >= 0


def test_plain_string_models_still_work():
    log = []
    model = guarded(lambda msgs: "fine", log.append, step=lambda: "review")
    assert model([{"role": "user", "content": "x"}]) == "fine"
    assert log[0]["output_tokens"] is None


def test_guard_redacts_known_values_even_without_context():
    seen, log = [], []
    model = guarded(lambda msgs: (seen.append(msgs), "it is Zq8vR2mW9xLp4TnB7cYd")[1], log.append,
                    step=lambda: "review", known={"Zq8vR2mW9xLp4TnB7cYd"})
    answer = model([{"role": "user", "content": "value Zq8vR2mW9xLp4TnB7cYd here"}])
    assert "Zq8vR2mW9xLp4TnB7cYd" not in seen[0][0]["content"] + answer + str(log)
