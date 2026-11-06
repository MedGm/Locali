# Retrospective: what went in, what we learned, what came out

Written 2026-10-24, after the speculative decoding study and the second seed. The question: given
what we started from and the evidence we collected, where did the result come from, and where is
the next real gain?

## 1. What we started with

| Input | What it was | What it set |
|---|---|---|
| The brief (`docs/project-brief.pdf`) | A software-engineering assistant on small models: benchmarking, PEFT fine-tuning, quantization, serving efficiency, agents, MCP, security, LLMOps, a web app | The scope: 17 components and 8 security controls (`docs/spec-checklist.md`) |
| Hardware | A laptop without GPU (i5-10210U, 16 GB) and Kaggle (2 x T4, 30 GPU-h/week) | Models of 1.5-4B; training only with QLoRA/LoRA on one T4 |
| Candidate models | Qwen2.5-Coder-1.5B, Qwen3.5-2B, Qwen3.5-4B, Phi-4-mini; Qwen3.5-9B as the large reference and teacher | Qwen3.5 could not be fine-tuned on a T4 (W1 spike), so Qwen2.5-Coder-1.5B became the model to train |
| Public benchmarks | HumanEval+, MBPP+, HumanEvalPack (fix, detect), CRUXEval-O, SecurityEval, a vulnerability set, plus our own completion, test-generation and refactoring tasks | What "better" means |
| Training raw material | CodeRM-UnitTest problems (solutions with unit tests), our mutation operators, the 9B teacher | 14,151 synthetic examples (mixture v2): repair of injected bugs, test writing, review, execution traces |

The starting position, measured before any training (Kaggle, FP16): the chosen model was the
cheapest per correct answer (54 J per HumanEval+ solution against 421 J for the 9B), but the
weakest on exactly the tasks the assistant needs: bug repair 25.0 % (9B: 65.8 %), bugs caught by
its tests 46.3 % (9B: 95.7 %), behaviour-preserving refactors 69.9 % (9B: 92.6 %), and bug
detection at chance with a "yes" bias (accuracy 53 %, recall 88 %).

## 2. How evidence steered the work

Each step was decided by a measurement from the step before:

1. **Baselines** showed where the 1.5B model was weak (repair, tests, refactoring, detection), so
   those became the training tasks (T1-T3).
2. **Fine-tune v1** gained on its tasks but cost code reasoning (CRUXEval-O 30.1 → 25.5,
   p = 0.0005) and made 41 % false bug reports on clean code. **v2** added execution traces (T4),
   five more bug operators and 500 verified clean reviews; the CRUXEval drop disappeared.
3. **Three PEFT variants** (QLoRA, 16-bit LoRA, rsLoRA) gave the same quality; QLoRA was kept as
   the cheapest. **Phi-4-mini** got worse from the same data: the targets were weaker than what it
   already did.
4. **Quantization ladder** on the laptop: Q8 lossless, Q4 −2 to −4 points, so Q8 became the
   default. It also showed that the fine-tune writes a third fewer tokens, a saving on its own.
5. **Serving, context and agents**: batching, CUDA graphs and context slicing were measured and
   applied; prompt compression was not worth it.
6. **"Why are the scores low?"** led to repair with execution feedback: +3.6 to +5.5 points, and
   the finding that the model mostly repeats its first answer.
7. **The PhD direction** led to speculative decoding and energy per correct answer, and to a
   second seed, which confirmed two gains and withdrew one.

Every comparison was paired (exact McNemar on the same problems), the harness was validated on
reference solutions before any model was scored, and answers were kept so that scoring fixes
could be re-applied without regenerating. That discipline is why the conclusions can be trusted,
including the negative ones.

## 3. What we got

| | Base 1.5B | Fine-tuned 1.5B | 9B reference |
|---|---|---|---|
| Bug repair (HumanEvalFix) | 25.0 % | **36.0 %** (p = 0.006, both seeds) | 65.8 % |
| ... with 3 attempts and the test error | 29.9 % | **41.5 %** | not run |
| MBPP+ | 56.2 % | **62.1 %** (p = 0.005, both seeds) | 62.1 % |
| HumanEval+ | 65.0 % | 62.0 % (n.s.) | 84.0 % |
| Bugs caught by generated tests | 46.3 % | **82.3 %** | 95.7 % |
| Refactoring, behaviour preserved | 69.9 % | **93.9 %** | 92.6 % |
| Bug detection | 53.0 % | 65.5 % with one seed, 54.6 % with the other | 72.0 % |
| CPU energy per solved HumanEval+ problem | 962 J (F16) | **189 J** (Q4 + n-gram lookup) | does not fit the laptop |

So: test writing and refactoring reach the 9B level; repair improves by 11 points but stays at
about half of the 9B; plain code generation does not improve; and the deployed model is five times
cheaper per correct answer than where we started.

## 4. What the result looks like

**A bug it now fixes** (HumanEvalFix Python/30, operator misuse):

```python
def get_positive(l: list):
    return [e for e in l if e < 0]        # buggy: keeps the negatives
```

The base model answers `e >= 0`, which keeps `0` and fails the test
`get_positive([5, 3, -5, 2, 3, 3, 9, 0, 123, 1, -10]) == [5, 3, 2, 3, 3, 9, 123, 1]`.
The fine-tune answers `e > 0`, which passes. Similarly for Python/41 (`return n**3`, should be
`n**2`): the base model returns the buggy code unchanged, the fine-tune fixes it.

**A bug it cannot fix, even with feedback** (Python/79, missing logic):

```python
def decimal_to_binary(decimal):
    return "db" + bin(decimal)[2:] + "d"   # the suffix should be "db"
```

The fine-tune answered `"db" + bin(decimal)[2:].zfill(8) + "d"` three times in a row. It changed
a part that was not wrong, and the error it was shown each time, a bare `AssertionError`, said
nothing about what was wrong. Of the 99 problems it never fixed with plain feedback, 45 got the
same answer three times.

**Where the gain comes from**, by HumanEvalFix bug type (problems fixed):

| Bug type | n | Base | Fine-tuned | 9B |
|---|---|---|---|---|
| Operator misuse | 25 | 5 | **16** | 13 |
| Value misuse | 44 | 13 | 18 | 35 |
| Excess logic | 31 | 6 | 8 | 19 |
| Missing logic | 33 | 4 | 7 | 22 |
| Variable misuse | 23 | 9 | 6 | 13 |
| Function misuse | 8 | 4 | 4 | 6 |

This table is the clearest single finding of the retrospective. The fine-tune beats even the 9B
on operator bugs, which look exactly like the single-token mutations it was trained on (`<` → `<=`).
On logic bugs, which need understanding what the function should do, it barely moves (missing
logic 4 → 7, against 22 for the 9B), and on variable misuse it got worse even though v2 added that
operator. **The model learned the shape of our synthetic bugs, not repair in general.**

## 5. What held us back

**In the data (the main limit).**
- Bugs were single-line mutations; real bugs (HumanEvalFix) are often multi-line or missing logic.
- The target was the whole fixed function, but it always differed from the input in one line, so
  the model learned to find and patch one token, not to reread a function.
- Explanations came from the 9B teacher, but the fixes did not: the teacher's stronger repair
  ability (65.8 %) was never distilled.
- No example ever showed a failed attempt and its error, so feedback could not be used.
- Python only: in other languages it gains in JavaScript and Go but is level or worse in C++,
  Rust and Java.

**In the model choice.** The trainable model was the weakest on the target tasks. Qwen3.5-4B
started at 53.7 % repair, higher than our fine-tune's 36.0 %, but could not be trained on a T4 in
September; that blocker was never re-checked.

**In the evaluation.**
- Most configurations ran once; the second seed showed that one apparent gain (bug detection) was
  noise. Other single-run claims carry the same risk.
- All benchmarks are public and old; a contamination-free set ("Locali-Fresh") was planned in W1
  and never built.
- Errors shown in the feedback loop were bare `AssertionError`s until late; the "explained" errors
  added only 2-3 problems, so missing information is not the whole story.

**In the process.**
- Long jobs ran on the laptop before moving to Kaggle; the laptop was blocked for hours that
  Kaggle could have absorbed.
- Much time went into the web app (about 27 of 196 commits) while the model's ceiling was set by the data.
- Harness bugs were found late (a fence parser that hid half of the test-generation answers;
  a missing dependency that wasted a Kaggle run), and one energy measurement was spoiled by running
  scoring on the same machine.

## 6. Where the next gains are, in order of expected value

1. **Train on realistic bugs with whole-function fixes from the teacher** (v3 plan, part 1-3). The
   bug-type table says this is where the gap is: logic bugs, where the 9B is 3-5 times better.
   Keep only teacher fixes that pass the tests: that distils the 9B's repair, not just its words.
2. **Teach it to use feedback** (v3 plan, part 4): rejection sampling on its own failures, with
   the explained errors as input. Measured target: fewer identical retries and more fixes at
   attempt 2-3.
3. **Re-check a stronger trainable base.** A 3-4B model starting above our fine-tune may beat any
   amount of data work on the 1.5B; with speculative n-gram decoding and Q4 its laptop cost may
   still be acceptable. This also answers the planned 7B comparison.
4. **Build a small contamination-free repair set** (30-50 bugs from recent real commits) so gains
   are not judged only on public benchmarks.
5. **Repeat key runs** (a third seed for the fine-tune; 2-3 repeats of energy runs) before claims
   go into the paper.
6. **Measure energy per fixed bug for the whole repair loop**, retries included: that is the number
   the assistant actually spends, and it decides whether feedback is worth its extra calls.
7. **Process:** every long job on Kaggle by default, scoring there too (the isolated runner now
   does that), the laptop only for CPU-specific measurements, and nothing else running during them.
