"""Prompts, schemas and data loaders for Study 1 (inductive codebook generation).
Blind design: nothing in this file refers to the expert themes, codes or their number."""
import csv, json, os

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'LLM Source')
TEXTS = os.path.join(SRC, '72_Text_for_LLM')
RESULTS = os.path.join(BASE, 'Results', 'study1')

MODEL = 'claude-sonnet-5'
EFFORT = 'medium'
MAX_TOKENS = 32000
MAX_TOKENS_STAGE5 = 64000   # Stage 5 returns the full codebook; raised after truncation at 32,000 (2026-09-28)
FORMS = ['CCDC 2', 'CCDC 2 CcQ', 'CCDC 3', 'CCDC 5A', 'CCDC 5B', 'CCDC 14', 'CCDC 17', 'CCDC 30']  # Table 1 order

LENS = """RESEARCH LENS
The research examines how the standard construction contracts published by the Canadian Construction Documents Committee (CCDC) address modern methods of construction (MMC), prefabrication and related contractual issues. The literature analysed consists of studies on MMC, prefabrication, project delivery and contractual issues."""

NO_TARGET = """There is no target number of items. Produce as many or as few as the material supports."""


# ---------------------------------------------------------------- Stage 1
S1_SYSTEM = f"""You are carrying out the first stage of a qualitative literature analysis for a research study.

{LENS}

TASK
You will receive the full text of one study. Record the following fields for it, in the manner of a research master list:
- objectives: what the study sets out to do;
- problem_statement: the problem or gap the study addresses;
- methodology: the research method, data and setting;
- key_background_studies: the earlier studies that the text treats as central to its argument (author and year, with a few words on why each matters); include only studies discussed in the main text;
- findings: the main findings and conclusions;
- keywords: the study's keywords, or, if none are given, the terms that best describe it.

Then list the recurring ideas in the study that relate to the research lens. An idea is a point the study makes about a process, responsibility, risk, practice or contractual issue relevant to the lens. State each idea in one sentence in your own words and support it with a short verbatim quotation (at most 40 words) copied exactly from the text, so that it can be traced. {NO_TARGET} If the study contains nothing relevant to the lens, return an empty list of ideas.

Base every field only on the text supplied."""

S1_SCHEMA = {
    'type': 'object',
    'properties': {
        'study_id': {'type': 'string'},
        'objectives': {'type': 'string'},
        'problem_statement': {'type': 'string'},
        'methodology': {'type': 'string'},
        'key_background_studies': {'type': 'array', 'items': {'type': 'string'}},
        'findings': {'type': 'string'},
        'keywords': {'type': 'array', 'items': {'type': 'string'}},
        'ideas': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'idea': {'type': 'string'}, 'quote': {'type': 'string'}},
            'required': ['idea', 'quote'], 'additionalProperties': False}},
    },
    'required': ['study_id', 'objectives', 'problem_statement', 'methodology', 'key_background_studies',
                 'findings', 'keywords', 'ideas'],
    'additionalProperties': False,
}


def s1_user(study_id, text):
    return f"Study identifier: {study_id}\n\nFull text of the study:\n<<<\n{text.strip()}\n>>>"


# ---------------------------------------------------------------- Stage 2
S2_SYSTEM = f"""You are carrying out the second stage of a qualitative literature analysis.

{LENS}

TASK
You will receive the master list produced in the first stage: one record per study, each with its recurring ideas. Group the recurring ideas across all studies into broad themes. A theme gathers ideas that concern the same broad area of concern for contracts on MMC and prefabrication projects. For each theme give:
- theme_id: T1, T2, ... in the order you present them;
- label: a short name;
- memo: a paragraph explaining what the theme covers, what distinguishes it from the other themes, and the main ideas it gathers;
- study_ids: the identifiers of all studies whose ideas address the theme.

A study may address several themes. Every idea should belong to at least one theme; list in unassigned_ideas any idea that fits no theme (study identifier and idea). {NO_TARGET}"""

S2_SCHEMA = {
    'type': 'object',
    'properties': {
        'themes': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'theme_id': {'type': 'string'}, 'label': {'type': 'string'}, 'memo': {'type': 'string'},
                           'study_ids': {'type': 'array', 'items': {'type': 'string'}}},
            'required': ['theme_id', 'label', 'memo', 'study_ids'], 'additionalProperties': False}},
        'unassigned_ideas': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['themes', 'unassigned_ideas'], 'additionalProperties': False,
}


def s2_user(records):
    parts = ['MASTER LIST']
    for r in records:
        ideas = '\n'.join(f"  - {i['idea']}" for i in r['ideas']) or '  (none)'
        parts.append(f"[Study {r['study_id']}]\nObjectives: {r['objectives']}\nFindings: {r['findings']}\n"
                     f"Keywords: {', '.join(r['keywords'])}\nRecurring ideas:\n{ideas}")
    return '\n\n'.join(parts)


# ---------------------------------------------------------------- Stage 3
S3_SYSTEM = f"""You are carrying out the third stage of a qualitative literature analysis.

{LENS}

TASK
You will receive one broad theme, with its memo, and the recurring ideas (with supporting quotations) of the studies that address it. Break the theme down into more specific categories, codes and sub-codes that describe the processes, responsibilities, risks and contractual issues within it.
- A category is a coherent part of the theme.
- A code is a specific issue within a category that could be recognised in a contract.
- A sub-code is a finer distinction within a code; use sub-codes only where the material supports them.
For each code give a short description and the identifiers of the studies that support it. {NO_TARGET}"""

S3_SCHEMA = {
    'type': 'object',
    'properties': {
        'theme_id': {'type': 'string'},
        'categories': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'label': {'type': 'string'}, 'memo': {'type': 'string'},
                'codes': {'type': 'array', 'items': {
                    'type': 'object',
                    'properties': {
                        'label': {'type': 'string'}, 'description': {'type': 'string'},
                        'sub_codes': {'type': 'array', 'items': {
                            'type': 'object',
                            'properties': {'label': {'type': 'string'}, 'description': {'type': 'string'}},
                            'required': ['label', 'description'], 'additionalProperties': False}},
                        'study_ids': {'type': 'array', 'items': {'type': 'string'}}},
                    'required': ['label', 'description', 'sub_codes', 'study_ids'], 'additionalProperties': False}}},
            'required': ['label', 'memo', 'codes'], 'additionalProperties': False}},
    },
    'required': ['theme_id', 'categories'], 'additionalProperties': False,
}


def s3_user(theme, records):
    ids = set(theme['study_ids'])
    parts = [f"THEME {theme['theme_id']}: {theme['label']}\nMemo: {theme['memo']}\n\nIDEAS OF THE STUDIES ADDRESSING THIS THEME"]
    for r in records:
        if r['study_id'] in ids and r['ideas']:
            parts.append(f"[Study {r['study_id']}]\n" + '\n'.join(f"  - {i['idea']} (\"{i['quote']}\")" for i in r['ideas']))
    return '\n\n'.join(parts)


# ---------------------------------------------------------------- Stage 4
S4_SYSTEM = f"""You are carrying out the fourth stage of a qualitative analysis.

{LENS}

TASK
You will receive the complete literature-based structure: every theme with its categories, codes and sub-codes. Review it as a whole and produce a set of preliminary contract codes for analysing the clauses of standard construction contracts:
- combine codes that cover the same issue, including codes that appear under different themes;
- rename codes so that they suit the analysis of contract clauses, using the language of construction contracts;
- keep distinctions that matter for how a contract addresses MMC and prefabrication.
For each preliminary code give:
- code_id: P1, P2, ... in the order you present them;
- label: a short name;
- definition: one or two sentences;
- memo: why the code is needed, what it gathers from the literature, and which earlier codes it combines or renames;
- source_themes: the identifiers of the themes it draws on.
{NO_TARGET}"""

S4_SCHEMA = {
    'type': 'object',
    'properties': {
        'codes': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'code_id': {'type': 'string'}, 'label': {'type': 'string'}, 'definition': {'type': 'string'},
                           'memo': {'type': 'string'}, 'source_themes': {'type': 'array', 'items': {'type': 'string'}}},
            'required': ['code_id', 'label', 'definition', 'memo', 'source_themes'], 'additionalProperties': False}},
    },
    'required': ['codes'], 'additionalProperties': False,
}


def s4_user(themes, stage3):
    parts = ['LITERATURE-BASED STRUCTURE']
    by_id = {s['theme_id']: s for s in stage3}
    for t in themes:
        s = by_id.get(t['theme_id'])
        block = [f"THEME {t['theme_id']}: {t['label']}\nMemo: {t['memo']}"]
        for c in (s['categories'] if s else []):
            block.append(f"  Category: {c['label']} - {c['memo']}")
            for k in c['codes']:
                block.append(f"    Code: {k['label']} - {k['description']} (studies: {', '.join(k['study_ids'])})")
                for sc in k['sub_codes']:
                    block.append(f"      Sub-code: {sc['label']} - {sc['description']}")
        parts.append('\n'.join(block))
    return '\n\n'.join(parts)


# ---------------------------------------------------------------- Stage 5
S5_SYSTEM = f"""You are carrying out the fifth stage of a qualitative analysis: refining a codebook against standard construction contracts.

{LENS}

TASK
You will receive the current version of the codebook and the full clause text of one CCDC standard form. Review the form clause by clause and identify:
(i) clauses relevant to the research lens that no existing code represents clearly; and
(ii) codes that are too broad to separate different contractual issues.
You may then clarify, combine, split, rename or add codes. Apply three rules whenever you add or revise a code:
1. The code must relate to the research lens and to issues identified in the literature.
2. The code must represent something identifiable at clause or sub-clause level.
3. The code must be useful for comparing different contract forms; do not create a code only because this form uses a particular term or contains a unique clause.
A code does not need to appear in every form: the absence of a code from a form is a valid result and is not a reason to remove or change the code. If no change is needed, return an empty list of changes and the codebook unchanged. {NO_TARGET}

For every change give the action (clarify, combine, split, rename or add), the identifiers of the codes affected, a description of the change, its justification, and the identifiers of the clauses that prompted it.

Return the complete updated codebook. Keep the identifier of every code that continues; give new codes new identifiers (C1, C2, ... continuing the existing numbering). For each code give a label, a definition, inclusion criteria (include_when: when a clause should receive the code), exclusion criteria (exclude_when: when it should not, including how to distinguish it from related codes) and a memo."""

S5_SCHEMA = {
    'type': 'object',
    'properties': {
        'form': {'type': 'string'},
        'changes': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'action': {'type': 'string', 'enum': ['clarify', 'combine', 'split', 'rename', 'add']},
                           'codes_affected': {'type': 'array', 'items': {'type': 'string'}},
                           'description': {'type': 'string'}, 'justification': {'type': 'string'},
                           'clause_ids': {'type': 'array', 'items': {'type': 'string'}}},
            'required': ['action', 'codes_affected', 'description', 'justification', 'clause_ids'], 'additionalProperties': False}},
        'codebook': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'code_id': {'type': 'string'}, 'label': {'type': 'string'}, 'definition': {'type': 'string'},
                           'include_when': {'type': 'string'}, 'exclude_when': {'type': 'string'}, 'memo': {'type': 'string'}},
            'required': ['code_id', 'label', 'definition', 'include_when', 'exclude_when', 'memo'], 'additionalProperties': False}},
    },
    'required': ['form', 'changes', 'codebook'], 'additionalProperties': False,
}


def codebook_from_stage4(codes):
    """Stage 4 codes (P1..) become the starting codebook C1.. for Stage 5."""
    return [{'code_id': f'C{i}', 'label': c['label'], 'definition': c['definition'], 'include_when': '',
             'exclude_when': '', 'memo': c['memo']} for i, c in enumerate(codes, 1)]


def s5_user(form, codebook, clauses):
    cb = json.dumps(codebook, ensure_ascii=False, indent=1)
    lines = []
    for r in clauses:
        head = ' | '.join(x for x in (r['part_heading'], r['parent_heading']) if x and x.strip())
        lead = f" [{r['parent_leadin'].strip()}]" if r['parent_leadin'].strip() else ''
        lines.append(f"{r['clause_id']} ({head}){lead}: {r['clause_text'].strip()}")
    return (f"CURRENT CODEBOOK\n{cb}\n\nFORM: {form}\nFULL CLAUSE TEXT (clause identifier, heading, lead-in, text):\n<<<\n"
            + '\n'.join(lines) + '\n>>>')


# ---------------------------------------------------------------- common
def params(system, user, schema, cache=False):
    sys_block = {'type': 'text', 'text': system}
    if cache:
        sys_block['cache_control'] = {'type': 'ephemeral'}
    return {'model': MODEL, 'max_tokens': MAX_TOKENS, 'system': [sys_block],
            'messages': [{'role': 'user', 'content': user}],
            'output_config': {'effort': EFFORT, 'format': {'type': 'json_schema', 'schema': schema}}}


def load_studies():
    out = []
    for fn in sorted(os.listdir(TEXTS)):
        if fn[:2].isdigit() and fn.endswith('.txt'):
            out.append((fn[:2], open(os.path.join(TEXTS, fn), encoding='utf-8').read()))
    return out


def load_clauses(form):
    return [r for r in csv.DictReader(open(os.path.join(SRC, 'CCDC_ai_input_Clauses_with_context.csv'), encoding='utf-8-sig'))
            if r['form'] == form]


def parse(message):
    return json.loads(''.join(b.text for b in message.content if b.type == 'text'))
