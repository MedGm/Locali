import pytest

from evaluation.redteam import CASES, run_case
from evaluation.tests.test_codegen import needs_docker


def params():
    for c in CASES:
        yield pytest.param(c, id=c.id, marks=[needs_docker] if c.needs_docker else [])


@pytest.mark.parametrize("c", params())
def test_attack_fails_with_the_control_and_works_without_it(c, tmp_path):
    on = run_case(c, True, tmp_path / "on")
    off = run_case(c, False, tmp_path / "off")
    assert on["attack_succeeded"] is False, on["detail"]
    assert off["attack_succeeded"] is True, off["detail"]  # the case really is an attack
