from evaluation.divergence import (
    first_divergence,
    nudge_positions,
    rank_of,
    refence,
    second_choice,
    uncertain_positions,
)


def test_first_divergence_is_the_first_differing_token_counted_in_the_leader():
    leader = [1, 2, 3, 4, 5, 6]
    # the follower's continuation starts after 2 forced tokens
    assert first_divergence([3, 4, 9, 9], leader, offset=2) == 4


def test_first_divergence_at_the_first_continued_token():
    assert first_divergence([7], [1, 2, 3], offset=1) == 1


def test_no_divergence_when_the_continuation_follows_the_leader_to_its_end():
    assert first_divergence([3, 4, 99], [1, 2, 3, 4], offset=2) is None


def test_no_divergence_when_the_continuation_stops_early_on_the_leader():
    assert first_divergence([3], [1, 2, 3, 4], offset=2) is None


def test_refence_gives_the_leader_answer_the_follower_fence():
    base = "```\npython\ndef f():\n    return 1\n```"
    tuned = "```python\ndef g():\n    pass\n```"
    assert refence(base, tuned) == "```python\ndef f():\n    return 1\n```"
    assert refence(tuned, base) == "```\npython\ndef g():\n    pass\n```"


def test_refence_keeps_the_answer_when_either_has_no_opening_fence():
    assert refence("def f(): pass", "```python\nx\n```") == "def f(): pass"
    assert refence("```python\nx\n```", "x = 1") == "```python\nx\n```"


def test_rank_of_a_token_among_the_top_alternatives():
    top = {"token_id:5": -0.1, "token_id:9": -2.5, "token_id:2": -4.0}
    assert rank_of(9, top) == 2
    assert rank_of(5, top) == 1
    assert rank_of(7, top) is None


def test_nudge_positions_are_distinct_reproducible_and_skip_the_fence():
    first = nudge_positions(50, 3, seed="D|base|HumanEval/54")
    assert first == nudge_positions(50, 3, seed="D|base|HumanEval/54")
    assert len(set(first)) == 3
    assert all(3 <= p < 49 for p in first)


def test_nudge_positions_of_a_short_answer():
    assert nudge_positions(5, 3, seed="x") == [3]
    assert nudge_positions(3, 3, seed="x") == []


def test_second_choice_is_the_best_other_token():
    top = {"token_id:5": -0.1, "token_id:9": -2.5, "token_id:2": -1.0}
    assert second_choice(5, top) == 2
    assert second_choice(2, top) == 5
    assert second_choice(5, {"token_id:5": -0.0}) is None


def test_uncertain_positions_are_the_least_likely_chosen_tokens_after_the_fence():
    chosen = [-5.0, -4.0, -3.0, -0.1, -2.0, -0.0, -1.5, -0.9, -0.3]
    assert uncertain_positions(chosen, 2, exclude=None) == [4, 6]
    assert uncertain_positions(chosen, 2, exclude=4) == [6, 7]
    assert uncertain_positions([-1.0, -1.0, -1.0], 2, exclude=None) == []
