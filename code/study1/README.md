# Study 1 - inductive codebook generation with Claude

Blind design: the model never receives the expert themes, codes, their number or the master list.

1. Pilot (Stage 1 on 2 studies, synchronous, < $1): `python3 run_study1.py pilot`
   -> Results/study1/pilot/ + projected Stage 1 cost.
2. Full run (3 independent replicates x 5 stages): `python3 run_study1.py`
   - Stage 1: 72 studies x 3 replicates through the Message Batches API.
   - Stages 2-5: synchronous requests; the 3 replicates run in parallel.
   - Resumable: if interrupted, run the same command again; finished steps are not repeated.
3. Outputs (Results/study1/):
   - rep1..rep3/stage1_master_list.json, stage2_themes.json, stage3_T*.json,
     stage4_preliminary_codes.json, stage5_<n>_<form>.json, final_codebook.json / .csv
   - calls.jsonl: every request (model, time, tokens, cost, errors, attempts)
   - summary.csv: counts per stage and replicate, share of quotations found verbatim, codes after each form

Configuration (s1_prompts.py): claude-sonnet-5, effort=medium, max_tokens=32000,
structured output (JSON schema), no temperature. The research lens is stated without examples
so as not to suggest any category.
