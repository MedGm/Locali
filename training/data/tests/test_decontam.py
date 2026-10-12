from training.data.decontam import NgramIndex, tokens

EVAL = "def has_close_elements(numbers, threshold):\n    for idx, elem in enumerate(numbers):\n        for idx2, elem2 in enumerate(numbers):\n            if idx != idx2: return True"


def test_tokens_are_lowercase_words_ignoring_punctuation():
    assert tokens("def F(x, y):  return X+1") == ["def", "f", "x", "y", "return", "x", "1"]


def test_flags_text_sharing_a_13_token_window():
    index = NgramIndex(n=13)
    index.add("humaneval", EVAL)

    copied = "# helper\nfor idx, elem in enumerate(numbers):\n    for idx2, elem2 in enumerate(numbers):\n        if idx != idx2:"
    assert index.sources(copied) == {"humaneval"}


def test_does_not_flag_shorter_overlap():
    index = NgramIndex(n=13)
    index.add("humaneval", EVAL)

    assert index.sources("for idx, elem in enumerate(numbers): pass") == set()


def test_reports_every_matching_source():
    index = NgramIndex(n=5)
    index.add("a", "one two three four five six")
    index.add("b", "two three four five six seven")

    assert index.sources("x two three four five six y") == {"a", "b"}
