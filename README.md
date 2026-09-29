# Replication package: LLM replication of an expert qualitative analysis of CCDC contracts

Companion to: Mehdipoor, Mozaffari, Hesarbani, Mojarad and Iordanova, "Comparative Evaluation of Large
Language Models and Human Experts for Reviewing CCDC Standard Construction Contracts", IEEE Access.

## Contents
- `code/` - all scripts: data preparation, Study 1 (inductive), Study 2 (deductive), scoring.
  Prompts are in `code/study1/s1_prompts.py` and `code/study2/prompts.py`.
- `data/` - the expert codebook (19 codes), the clause index (identifiers only), the development/test split
  .
- `results/study1/` - every model output of the three replicates (Stages 1-5), final codebooks, request log.
- `results/study2/` - every model output (pilot, development runs, three main runs), batch log, scoring output.

## Withheld
- Clause text and Definitions of the CCDC forms (CCDC copyright). With licensed copies of the forms,
  the clause records can be rebuilt with `code/build_clause_context_and_definitions.py` and matched on
  `data/clause_index.csv`.
- Full texts of the 72 studies (publishers' copyright); they are listed in the paper's supplementary list.
- The expert clause-level coding. Scoring scripts therefore require this file from the authors.

## Model and settings
Claude Sonnet 5 (`claude-sonnet-5`) via the Anthropic Claude API, adaptive thinking with effort=medium,
structured outputs (JSON schema), no temperature setting. All runs on 28 September 2026. See the paper,
Section III-H, and the request logs (`results/*/calls.jsonl`, `results/study2/batches.jsonl`).
