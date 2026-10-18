from backend.envfile import load_env


def test_reads_values_without_overriding_the_environment(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n\nLOCALI_A=one\nLOCALI_B = 'two words'  \nexport LOCALI_C=\"three\"\nLOCALI_D=four # note\nnot a line\n"
    )
    monkeypatch.setenv("LOCALI_A", "from-shell")
    for k in ("LOCALI_B", "LOCALI_C", "LOCALI_D"):
        monkeypatch.delenv(k, raising=False)
    loaded = load_env(env)
    import os

    assert os.environ["LOCALI_A"] == "from-shell"
    assert os.environ["LOCALI_B"] == "two words" and os.environ["LOCALI_C"] == "three"
    assert os.environ["LOCALI_D"] == "four"
    assert sorted(loaded) == ["LOCALI_B", "LOCALI_C", "LOCALI_D"]


def test_a_missing_file_is_fine(tmp_path):
    assert load_env(tmp_path / "nope.env") == []
