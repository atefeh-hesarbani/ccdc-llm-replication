"""Build the public replication package for the paper.
  python3 make_repository.py            -> Final Files/Repository/ccdc-llm-replication/ and a .zip of it
  python3 make_repository.py --with-expert-codes   also include the expert's clause-level codes

Withheld because of CCDC copyright: all clause text and the Definitions of the forms, and any file
that contains them. Withheld because of publishers' copyright: the full texts of the 72 studies.
By default the expert's clause-level codes are also withheld, as stated in the paper; use the flag
above if the authors decide to release them (then update the Availability paragraph)."""
import csv, json, os, shutil, sys, zipfile

BASE = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # Final Files
OUT = os.path.join(BASE, 'Repository', 'ccdc-llm-replication')
WITH_EXPERT = '--with-expert-codes' in sys.argv
S = lambda *p: os.path.join(BASE, *p)
D = lambda *p: os.path.join(OUT, *p)

if os.path.exists(OUT):
    sys.exit(f'{OUT} already exists - rename or move it first.')
os.makedirs(OUT)


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(src, dst)


def copytree(src, dst, skip=()):
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != '__pycache__' and not d.startswith('_') and d not in skip]
        for f in files:
            if f.endswith('.pyc') or f in skip:
                continue
            rel = os.path.relpath(os.path.join(root, f), src)
            copy(os.path.join(root, f), os.path.join(dst, rel))


# 1. code
copytree(S('Code'), D('code'))
copy(os.path.abspath(__file__), D('code', 'make_repository.py'))

# 2. inputs without copyrighted text
copy(S('LLM Source', 'codebook_19_codes.json'), D('data', 'expert_codebook_19_codes.json'))
copy(S('LLM Source', 'codebook_19_codes.xlsx'), D('data', 'expert_codebook_19_codes.xlsx'))
copy(S('LLM Source', 'study2_dev_test_split.csv'), D('data', 'study2_dev_test_split.csv'))
with open(S('LLM Source', 'CCDC_ai_input_Clauses.csv'), encoding='utf-8-sig') as f, \
        open(D('data', 'clause_index.csv'), 'w', newline='', encoding='utf-8') as g:
    w = csv.writer(g); w.writerow(['row_id', 'form', 'clause_id', 'section'])
    for r in csv.DictReader(f):
        w.writerow([r['row_id'], r['form'], r['clause_id'], r['section']])
if WITH_EXPERT:
    copy(S('Human', 'expert_coding_reference.csv'), D('data', 'expert_coding_reference.csv'))
    copy(S('Human', 'expert_coding_cleaning_log.csv'), D('data', 'expert_coding_cleaning_log.csv'))

# 3. Study 1 outputs (model-generated; quotations from the studies are at most 40 words)
copytree(S('Results', 'study1'), D('results', 'study1'))

# 4. Study 2 outputs
copytree(S('Results', 'study2'), D('results', 'study2'), skip=('final',))
os.makedirs(D('results', 'study2', 'final'), exist_ok=True)
for f in os.listdir(S('Results', 'study2', 'final')):
    if f == 'disagreement_review.csv':          # contains clause text
        continue
    src = S('Results', 'study2', 'final', f)
    if f == 'final_model_coding.csv' and not WITH_EXPERT:
        with open(src, encoding='utf-8') as a, open(D('results', 'study2', 'final', f), 'w', newline='', encoding='utf-8') as b:
            rows = list(csv.DictReader(a)); keep = [k for k in rows[0] if k != 'expert_codes']
            w = csv.DictWriter(b, fieldnames=keep, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
    else:
        copy(src, D('results', 'study2', 'final', f))

# 5. README
readme = f"""# Replication package: LLM replication of an expert qualitative analysis of CCDC contracts

Companion to: Mehdipoor, Mozaffari, Hesarbani, Mojarad and Iordanova, "Comparative Evaluation of Large
Language Models and Human Experts for Reviewing CCDC Standard Construction Contracts", IEEE Access.

## Contents
- `code/` - all scripts: data preparation, Study 1 (inductive), Study 2 (deductive), scoring.
  Prompts are in `code/study1/s1_prompts.py` and `code/study2/prompts.py`.
- `data/` - the expert codebook (19 codes), the clause index (identifiers only), the development/test split
  {'and the expert clause-level coding with its reconciliation log' if WITH_EXPERT else ''}.
- `results/study1/` - every model output of the three replicates (Stages 1-5), final codebooks, request log.
- `results/study2/` - every model output (pilot, development runs, three main runs), batch log, scoring output.

## Withheld
- Clause text and Definitions of the CCDC forms (CCDC copyright). With licensed copies of the forms,
  the clause records can be rebuilt with `code/build_clause_context_and_definitions.py` and matched on
  `data/clause_index.csv`.
- Full texts of the 72 studies (publishers' copyright); they are listed in the paper's supplementary list.
{'' if WITH_EXPERT else '- The expert clause-level coding. Scoring scripts therefore require this file from the authors.'}

## Model and settings
Claude Sonnet 5 (`claude-sonnet-5`) via the Anthropic Claude API, adaptive thinking with effort=medium,
structured outputs (JSON schema), no temperature setting. All runs on 28 September 2026. See the paper,
Section III-H, and the request logs (`results/*/calls.jsonl`, `results/study2/batches.jsonl`).
"""
open(D('README.md'), 'w', encoding='utf-8').write(readme)

# 6. zip
zpath = OUT + '.zip'
with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(OUT):
        for f in files:
            p = os.path.join(root, f); z.write(p, os.path.relpath(p, os.path.dirname(OUT)))
n = sum(len(fs) for _, _, fs in os.walk(OUT))
print(f'{n} files -> {OUT}\nzip: {zpath} ({os.path.getsize(zpath) // 1024} KB)')
