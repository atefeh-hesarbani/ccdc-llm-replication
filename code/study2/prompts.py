"""Prompt, schema and request builder for Study 2 (deductive clause coding).
All requests share the same instruction + codebook block (cached) and a
form-specific Definitions block (cached); only the user message varies."""
import csv, json, os

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'LLM Source')

MODEL = 'claude-sonnet-5'
EFFORT = 'medium'
MAX_TOKENS = 16000
PROMPT_VERSION = 'v1'   # frozen version used by main_runs.py ('v1' or 'v2')

CODING_RULES = """CODING RULES
1. A clause may receive no code, one code or several codes.
2. Read the clause in context and interpret it as a whole. Base your decision on its meaning, purpose and contractual effect, not only on the presence of specific words.
3. Assign a code when the meaning of the clause clearly addresses the concept of that code, even where the exact term does not appear. Both direct and implied contractual meanings count.
4. Do not assign a code on the basis of a weak or merely possible connection.
5. Use the definitions and the inclusion and exclusion criteria to decide between related codes."""

# v2 (development round 1): general procedural additions only; codebook wording unchanged,
# no code-specific rules.
CODING_RULES_V2 = CODING_RULES + """
6. Consider each of the nineteen codes in turn and check the clause against its inclusion and exclusion criteria before deciding. A clause often addresses more than one issue: assign every code whose inclusion criteria are met and whose exclusion criteria do not apply, not only the most prominent one.
7. Apply the exclusion criteria as written: when an exclusion criterion applies, do not assign the code, even if the clause is related to its topic."""

RULES = {'v1': CODING_RULES, 'v2': CODING_RULES_V2}

INTRO = """You are coding clauses of Canadian Construction Documents Committee (CCDC) standard construction contracts for a qualitative research study. You will receive one clause at a time, together with its heading and context, and must decide which codes from the codebook below apply to it."""

OUTPUT = """OUTPUT
Return every code that applies. For each code give its identifier, its label, a short justification (one or two sentences) that refers to the wording or effect of the clause, and your confidence (high, medium or low). If no code applies, return an empty list of codes."""


def load_codebook():
    return json.load(open(os.path.join(SRC, 'codebook_19_codes.json'), encoding='utf-8'))['codes']


def codebook_text(codes):
    parts = ['CODEBOOK (19 codes)']
    for c in codes:
        parts.append(f"[{c['id']}] {c['label']}\nDefinition: {c['definition']}\n"
                     f"Include when: {c['include_when']}\nExclude when: {c['exclude_when']}")
    return '\n\n'.join(parts)


def shared_system(codes, version=None):
    return '\n\n'.join([INTRO, RULES[version or PROMPT_VERSION], codebook_text(codes), OUTPUT])


def definitions_text(form):
    fn = os.path.join(SRC, 'definitions', form.replace(' ', '_') + '_definitions.txt')
    return f'DEFINITIONS OF {form}\n(Capitalized terms in the clauses have the following meanings.)\n\n' + open(fn, encoding='utf-8').read()


def schema(codes):
    return {
        'type': 'object',
        'properties': {
            'clause_id': {'type': 'string'},
            'codes': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'code_id': {'type': 'integer', 'enum': [c['id'] for c in codes]},
                        'code_label': {'type': 'string', 'enum': [c['label'] for c in codes]},
                        'justification': {'type': 'string'},
                        'confidence': {'type': 'string', 'enum': ['high', 'medium', 'low']},
                    },
                    'required': ['code_id', 'code_label', 'justification', 'confidence'],
                    'additionalProperties': False,
                },
            },
        },
        'required': ['clause_id', 'codes'],
        'additionalProperties': False,
    }


def user_message(r):
    na = lambda v, d='(none)': v.strip() if v and v.strip() else d
    return (f"Contract form: {r['form']}\n"
            f"Part of the contract: {r['section']}\n"
            f"Clause identifier: {r['clause_id']}\n"
            f"Part heading: {na(r['part_heading'], '(not applicable)')}\n"
            f"Article / General Condition heading: {na(r['parent_heading'])}\n"
            f"Lead-in wording: {na(r['parent_leadin'])}\n"
            f"Appendix context: {na(r['appendix_context'], '(not applicable)')}\n\n"
            f"Clause text:\n<<<\n{r['clause_text'].strip()}\n>>>")


def load_clauses():
    rows = list(csv.DictReader(open(os.path.join(SRC, 'CCDC_ai_input_Clauses_with_context.csv'), encoding='utf-8-sig')))
    split = {r['row_id']: r['set'] for r in csv.DictReader(open(os.path.join(SRC, 'study2_dev_test_split.csv'), encoding='utf-8-sig'))}
    for r in rows:
        r['set'] = split[r['row_id']]
    return rows


def build_params(r, codes, shared=None, model=None, effort=None, version=None):
    shared = shared or shared_system(codes, version)
    return {
        'model': model or MODEL,
        'max_tokens': MAX_TOKENS,
        'system': [
            {'type': 'text', 'text': shared, 'cache_control': {'type': 'ephemeral'}},
            {'type': 'text', 'text': definitions_text(r['form']), 'cache_control': {'type': 'ephemeral'}},
        ],
        'messages': [{'role': 'user', 'content': user_message(r)}],
        'output_config': {'effort': effort or EFFORT, 'format': {'type': 'json_schema', 'schema': schema(codes)}},
    }


def parse(message):
    text = ''.join(b.text for b in message.content if getattr(b, 'type', '') == 'text')
    return json.loads(text)
