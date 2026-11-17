# ctable-readings

Small experiments for one question: when a language model turns a vague smart-home
request into device settings, can a conditional table (c-table) over the model's
sampled readings tell whether the deployment is safe under every plausible reading,
and ask the operator only when the readings disagree on safety?

This repo has two pilot checks.

1. Coverage - does the set of k sampled readings contain the reading the operator
   actually meant? If not, the c-table can say "safe" with no question asked.
2. Independent vs tied c-variables - if each disagreement becomes its own c-variable,
   the table also holds mixes of settings that no sample proposed. A global condition
   (the valuation must equal one of the sampled readings) removes them. We count how
   much that changes the verdict and the question asked.

Everything here is small and synthetic: 40 hand-written requests over 8 device
scenarios, 2 open settings per request, intended readings labeled by me. Treat the
numbers as a pilot, not a benchmark.

## Layout

- `ctable_readings/dataset.py` - the 40 requests, the plausible readings for each
  setting, the intended reading, and one safety property per scenario
- `ctable_readings/ctable.py` - a toy finite-domain c-table: constants where samples
  agree, c-variables where they disagree, optional global condition, verdict
  (safe under all / unsafe under all / some), the smallest question, and the
  violation condition
- `ctable_readings/parse.py` - turns model text into a reading
- `scripts/sample.py` - samples 8 readings per request under 4 settings (MLX, 4-bit
  Qwen2.5 1.5B and 3B), resumable
- `scripts/analyze.py` - scores the saved samples, writes `results/summary.json`,
  `results/per_request.csv`, and the figures
- `results/samples.jsonl` - every raw model output
- `tests/` - unit tests for the c-table logic, parser and dataset

## Run

```
python3 -m pytest -q tests
python3 scripts/sample.py      # needs mlx_lm and the two models in the HF cache
python3 scripts/analyze.py
```

## Limits

The requests and intended labels are mine, so coverage depends on how often I chose
the less common reading. The model fills a fixed set of settings from a menu (or a
number), which is easier than writing whole rules. The c-table is a toy that lists
every valuation; Pyotr (Anwar, Caesar and Wang) stores c-tables in PostgreSQL and checks
conditions with Z3, BDDs or difference-of-cubes.

Made by Aarush Kandukoori
