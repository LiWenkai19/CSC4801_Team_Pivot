# LLM blind test generation (P10 experiment)

This directory reproduces Lecture 14 Exercise 1 (AI-assisted test generation) and
Exercise 3 (assertion writing / quality evaluation) on this project. It is **not**
a `tests/advanced/run.py` mode and is **not** part of CI.

## Protocol

1. The experiment owner wrote `contracts/F{1,2,3}.md` from
   `docs/REQUIREMENTS.md`, `SPEC.md`, and the target function/component
   signatures only. The contracts contain hand-calculated expected values.
2. Three fresh generator agents (separate contexts) each received **only** one
   contract, one prompt, the target signature/import path, and the test harness.
   They were explicitly forbidden to open `backend/app/` or `frontend/src/`, to
   read existing tests, or to execute the target.
3. The generated files were committed **before** the experiment owner ran them or
   reviewed the implementations. `git log --follow` on the generated files and
   `docs/advanced_testing/LLM_TEST_EXPERIMENT.md` record the commit order.
4. The generated files were then run unchanged; every failure was attributed to
   an implementation defect, a contract ambiguity, or a generation error.
5. Assertion strength was measured with five hand-written mutants injected through
   a test double/`monkeypatch` runner; no production file was modified.

## Layout

```text
llm_blind/
  contracts/F1.md F2.md F3.md   # owner-written contracts with hand calculations
  prompts/F1.txt F2.txt F3.txt  # exact prompts given to the generator agents
  generated/test_F1.py           # blind-generated pytest tests (frozen before review)
  generated/test_F2.py
  generated/test_F3.mjs
  generated/conftest.py          # no-DB harness (owner-written)
  generated/session_double.py    # SQLModel Session double (owner-written)
  generated/render_helper.mjs    # TSX loader + renderToStaticMarkup (owner-written)
  run_experiment.py              # runs the frozen files, writes results.json
  mutation/                      # five hand-written mutants + kill matrix
  results.json                   # machine-readable run results + attribution
```

## Reproduce

From the repository root, with the project virtual environment and
`frontend/node_modules` installed (`npm --prefix frontend ci`):

```sh
python tests/advanced/experiments/llm_blind/run_experiment.py \
  --out "$TMPDIR/p10-llm-blind" \
  --node-modules frontend/node_modules
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe tests\advanced\experiments\llm_blind\run_experiment.py `
  --out "$env:TEMP\p10-llm-blind" `
  --node-modules frontend\node_modules
```

`--out` must be outside the checkout; logs and JUnit XML go there. The summary is
written to `results.json` in this directory. Determinism: `PYTHONHASHSEED=4801`,
fixed timestamps in F2, no network, no real database, no real service.

Run the mutation kill matrix separately after the generated run:

```sh
python tests/advanced/experiments/llm_blind/mutation/run_mutants.py \
  --out "$TMPDIR/p10-mutants"
```

## Results (this branch)
- Frozen generation commit: `c0859d0` (tests generated before the implementation
  was reviewed or run).
- Post-freeze setup repairs (expected values unchanged): `467a6f2` (F1
  parametrize ids; F2 synthetic `User.role`) and `e76641f` (F2 IntegrityError
  harness exposes the concurrent winner).
- Final run: F1 93 passed + 1 documented out-of-contract skip (94 collected),
  F2 19/19, F3 11/11; **123 passed, 1 skipped, 0 failed**.
- Five hand-written mutants: generated tests kill **5/5**, handwritten tests kill
  **3/5**; the survivors expose a confounded normalization case and a missing
  “job does not exist” partition in the handwritten suite.
- No production defect was found, so there is no `docs/advanced_testing/findings/P10.md`.
- Full evidence and the L14 slide-30 analysis:
  [`docs/advanced_testing/LLM_TEST_EXPERIMENT.md`](../../../../docs/advanced_testing/LLM_TEST_EXPERIMENT.md).

The generated tests are experiments, not part of the required unit suite; rerun
`python tests/run_tests.py` separately.

## Scope and limitations

- Generated tests are experiments, not part of the required unit suite
  (`python tests/run_tests.py`). They are never imported by it.
- F1 is a pure function; F2 is the `book` service with a session double (no real
  PostgreSQL); F3 is the real React component rendered with
  `renderToStaticMarkup` (escaping evidence, not a browser/XSS proof).
- The report `docs/advanced_testing/LLM_TEST_EXPERIMENT.md` compares the generated tests
  with the handwritten tests in `tests/unit/test_matching.py`,
  `tests/unit/test_scheduling.py` and `tests/unit/test_rendering.py` on partitions,
  case count, unique findings and mutant kills.
