# Contributing

Bug reports and pull requests are welcome.

- Open an issue describing the problem or proposal before starting significant work.
- For code changes: add or update a test in `tests/test_verify.py` that would have caught the
  bug (or that exercises the new behavior), and run `python -m pytest tests/ -v` before opening a PR.
- Keep `redteam/` dependency-free (stdlib only). If a change needs a new dependency, it almost
  certainly belongs in the `eval/` or companion `synth-corpus` layer instead.
- Match the existing style: small, focused functions; every finding carries a `citation`.

## Running the checks locally

```
python -m pytest tests/ -v         # zero-dependency detector suite
python eval/eval.py                # full eval (requires the synth-corpus sibling repo, see README)
```
