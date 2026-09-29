# Study 2 – deductive clause coding with Claude

1. `pip install anthropic` and set `ANTHROPIC_API_KEY`.
2. Pilot (synchronous, ~20 clauses, <$1): `python run_pilot.py 20`
   -> Results/study2/pilot.jsonl + projected cost.
3. Development comparison (Sonnet 5 medium / Sonnet 5 high / Sonnet 5.5 medium on the
   262 development clauses): `python dev_compare.py` (submits, waits, collects, scores).
   Scoring of any run: `python score_dev.py <run names>`.
   Single development rounds: `python run_batch.py submit --set development --run dev1`,
   then `status <id>`, then `collect <id> --run dev1`.
4. Main runs (after instructions are frozen): `submit --set all --run 1` (then 2, 3).

Configuration (see prompts.py): claude-sonnet-5, effort=medium, max_tokens=16000,
structured output (JSON schema), prompt caching of the instruction/codebook and
Definitions blocks. No temperature is set (not accepted by the model).
