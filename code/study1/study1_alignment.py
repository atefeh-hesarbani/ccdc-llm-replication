"""Study 1 post-processing.
  python3 study1_alignment.py prepare   -> Results/study1/alignment/ : traceability of quotations,
        counts per stage, and two blank judge workbooks (Judge_A, Judge_B) for the alignment protocol.
  python3 study1_alignment.py score     -> reads the two completed workbooks and reports inter-judge
        kappa, coverage, novelty, granularity and stability (after the judges' consensus sheet is filled)."""
import csv, json, os, re, sys
import s1_prompts as P
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

OUT = os.path.join(P.RESULTS, 'alignment'); os.makedirs(OUT, exist_ok=True)
REPS = ['1', '2', '3']
EXPERT_THEMES = ['Modern Methods', 'Procurement', 'Delivery Models', 'Productivity', 'Cost', 'Schedule',
                 'Sustainability', 'Risk', 'Supply Chain', 'Collaboration']
EXPERT = json.load(open(os.path.join(P.SRC, 'codebook_19_codes.json'), encoding='utf-8'))['codes']
RELATIONS = ['equivalent', 'broader than expert code(s)', 'narrower than (part of) an expert code', 'partial overlap', 'no counterpart']
WRAP = Alignment(wrap_text=True, vertical='top'); BOLD = Font(bold=True); FILL = PatternFill('solid', fgColor='FFF2CC')


def rep_data(rep):
    d = os.path.join(P.RESULTS, f'rep{rep}')
    j = lambda f: json.load(open(os.path.join(d, f), encoding='utf-8'))
    return {'master': j('stage1_master_list.json'), 'themes': j('stage2_themes.json')['themes'],
            'prelim': j('stage4_preliminary_codes.json')['codes'], 'final': j('final_codebook.json')}


def traceability(master):
    texts = {f'{i:02d}': open(os.path.join(P.TEXTS, f'{i:02d}.txt'), encoding='utf-8').read() for i in range(1, 73)}
    norm = lambda s: re.sub(r'\s+', ' ', s).strip().lower()
    loose = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
    nt = {k: norm(v) for k, v in texts.items()}; lt = {k: loose(v) for k, v in texts.items()}
    exact = punct = ellip = none = 0
    for r in master:
        for i in r['ideas']:
            q, s = i['quote'], r['study_id']
            if norm(q).strip('"“”…. ') in nt[s]: exact += 1
            elif loose(q) in lt[s]: punct += 1
            elif all(loose(p) in lt[s] for p in re.split(r'\.\.\.|…', q) if len(loose(p)) > 15) and re.search(r'\.\.\.|…', q): ellip += 1
            else: none += 1
    n = exact + punct + ellip + none
    return {'ideas': n, 'verbatim': exact, 'verbatim_ignoring_punctuation': punct, 'verbatim_segments_joined_by_ellipsis': ellip,
            'not_traceable_verbatim': none, 'traceable_share': round((n - none) / n, 3)}


def sheet_matrix(wb, title, rows, col_ids, row_fields, note):
    ws = wb.create_sheet(title)
    ws.append([note]); ws['A1'].font = BOLD
    head = list(row_fields) + col_ids + ['relation_type', 'notes']
    ws.append(head)
    for c in ws[2]: c.font = BOLD; c.alignment = WRAP
    dv = DataValidation(type='list', formula1='"' + ','.join(RELATIONS) + '"', allow_blank=True); ws.add_data_validation(dv)
    dv01 = DataValidation(type='list', formula1='"1"', allow_blank=True); ws.add_data_validation(dv01)
    for r in rows:
        ws.append([r.get(f, '') for f in row_fields] + [''] * len(col_ids) + ['', ''])
        i = ws.max_row
        for k in range(len(col_ids)):
            cell = ws.cell(i, len(row_fields) + 1 + k); cell.fill = FILL; dv01.add(cell)
        dv.add(ws.cell(i, len(head) - 1)); ws.cell(i, len(head) - 1).fill = FILL
        for k in range(1, len(row_fields) + 1): ws.cell(i, k).alignment = WRAP
    for k, w in enumerate([10, 30, 45, 40, 40][:len(row_fields)], 1):
        ws.column_dimensions[ws.cell(2, k).column_letter].width = w
    ws.freeze_panes = ws.cell(3, len(row_fields) + 1)


def prepare():
    data = {r: rep_data(r) for r in REPS}
    rows = []
    for r in REPS:
        t = traceability(data[r]['master'])
        rows.append({'replicate': r, 'studies_with_ideas': sum(1 for m in data[r]['master'] if m['ideas']), **t,
                     'themes': len(data[r]['themes']), 'preliminary_codes': len(data[r]['prelim']), 'final_codes': len(data[r]['final'])})
    with open(os.path.join(OUT, 'stage_counts_and_traceability.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for r in rows: print(r)
    exp_ids = [f"E{c['id']}" for c in EXPERT]
    for judge in ('A', 'B'):
        wb = Workbook(); ws = wb.active; ws.title = 'Instructions'
        for line in [
            f'Study 1 alignment - Judge {judge}. Work independently; do not consult the other judge until both workbooks are complete.',
            'Judge correspondence on the definitions and the inclusion/exclusion criteria, not on the labels.',
            'Codes_Rep1..3: for each induced code, enter 1 under every expert code (E1..E19) it corresponds to, fully or in part; leave blank otherwise.',
            'Then choose relation_type: equivalent / broader than expert code(s) / narrower than (part of) an expert code / partial overlap / no counterpart.',
            'An expert code whose column has no 1 in a replicate is recorded as not recovered by that replicate (reverse direction).',
            'Themes_Rep1..3: the same for induced themes against the ten expert themes (T_E1..T_E10).',
            'Stability: for each code of replicates 2 and 3, enter the identifiers of the corresponding code(s) in replicate 1 (and, for replicate 3, in replicate 2); leave blank if none.',
            'Expert_Codebook and Expert_Themes are for reference.']:
            ws.append([line])
        ws.column_dimensions['A'].width = 150
        ec = wb.create_sheet('Expert_Codebook'); ec.append(['id', 'label', 'definition', 'include_when', 'exclude_when'])
        for c in EXPERT: ec.append([f"E{c['id']}", c['label'], c['definition'], c['include_when'], c['exclude_when']])
        for col, wdt in zip('ABCDE', (6, 24, 60, 60, 60)): ec.column_dimensions[col].width = wdt
        for row in ec.iter_rows(min_row=2):
            for c in row: c.alignment = WRAP
        et = wb.create_sheet('Expert_Themes'); et.append(['id', 'theme'])
        for i, t in enumerate(EXPERT_THEMES, 1): et.append([f'T_E{i}', t])
        for r in REPS:
            sheet_matrix(wb, f'Codes_Rep{r}', data[r]['final'], exp_ids, ['code_id', 'label', 'definition', 'include_when', 'exclude_when'],
                         f'Replicate {r}: final induced codebook ({len(data[r]["final"])} codes) against the 19 expert codes')
        for r in REPS:
            th = [{'theme_id': t['theme_id'], 'label': t['label'], 'memo': t['memo']} for t in data[r]['themes']]
            sheet_matrix(wb, f'Themes_Rep{r}', th, [f'T_E{i}' for i in range(1, 11)], ['theme_id', 'label', 'memo'],
                         f'Replicate {r}: induced themes against the ten expert themes')
        st = wb.create_sheet('Stability')
        st.append(['replicate', 'code_id', 'label', 'definition', 'matching codes in replicate 1', 'matching codes in replicate 2', 'notes'])
        for c in st[1]: c.font = BOLD
        for r in ('2', '3'):
            for c in data[r]['final']:
                st.append([r, c['code_id'], c['label'], c['definition'], '', '' if r == '3' else 'n/a', ''])
        for col, wdt in zip('ABCDEFG', (9, 8, 40, 70, 22, 22, 30)): st.column_dimensions[col].width = wdt
        r1 = wb.create_sheet('Rep1_Codes_reference'); r1.append(['code_id', 'label', 'definition'])
        for c in data['1']['final']: r1.append([c['code_id'], c['label'], c['definition']])
        r2 = wb.create_sheet('Rep2_Codes_reference'); r2.append(['code_id', 'label', 'definition'])
        for c in data['2']['final']: r2.append([c['code_id'], c['label'], c['definition']])
        wb.save(os.path.join(OUT, f'Study1_alignment_Judge_{judge}.xlsx'))
    print('workbooks written to', OUT)


if __name__ == '__main__':
    if sys.argv[1:] == ['prepare']: prepare()
    else: print(__doc__)
