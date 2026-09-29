"""Final scoring of Study 2 (run after main_runs.py).
  python score_main.py                 # uses run1, run2, run3
  python score_main.py --runs dev_s5_medium dev_s5_high dev_s55_medium --set development   (test of the script)
Outputs in Results/study2/final/:
  final_model_coding.csv        majority-vote coding (code kept if assigned in >=2 of 3 runs)
  agreement_overall.csv         exact match, micro/macro P-R-F1, mean kappa, Krippendorff alpha
  agreement_per_code.csv        TP/FP/FN/TN, precision, recall, F1, kappa per code
  frequency_expert.csv / frequency_model.csv   19 x 8 code frequency tables (all 1,933 clauses)
  findings_per_form.csv         Spearman rank correlation of code frequencies per form
  gaps.csv                      zero-frequency code-form cells, expert vs model
  run_consistency.csv           agreement among the three runs
  disagreement_review.csv       sample of test-set disagreements for manual classification"""
import argparse, csv, json, os, random
import prompts, common, score_dev

ap = argparse.ArgumentParser()
ap.add_argument('--runs', nargs='+', default=['1', '2', '3'])
ap.add_argument('--set', default='test', help='set for agreement statistics: test | development | all')
ap.add_argument('--out', default='final')
a = ap.parse_args()
OUT = os.path.join(common.RESULTS, a.out); os.makedirs(OUT, exist_ok=True)
codes = {int(c['id']): c['label'] for c in prompts.load_codebook()}; K = sorted(codes)
clauses = prompts.load_clauses(); cl = {r['row_id'].zfill(4): r for r in clauses}
FORMS = ['CCDC 2', 'CCDC 2 CcQ', 'CCDC 3', 'CCDC 5A', 'CCDC 5B', 'CCDC 14', 'CCDC 17', 'CCDC 30']
ref = score_dev.expert()

def load_run(name):
    recs = {}
    for r in score_dev.load(name):
        recs[r['row_id'].zfill(4)] = r
    return recs
runs = [load_run(n) for n in a.runs]
R = len(runs)

# ---------- majority vote ----------
final, just, missing = {}, {}, []
for rid in cl:
    sets = [set(run[rid]['codes']) for run in runs if rid in run and run[rid]['codes'] is not None and not run[rid]['error']]
    if len(sets) < R: missing.append(rid)
    if not sets: continue
    need = len(sets) // 2 + 1
    final[rid] = {k for k in K if sum(k in s for s in sets) >= need}
    just[rid] = {}
    for run in runs:
        r = run.get(rid)
        if r and r['raw']:
            for c in r['raw']['codes']:
                just[rid].setdefault(c['code_id'], c['justification'])
with open(os.path.join(OUT, 'final_model_coding.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['row_id', 'form', 'clause_id', 'set', 'model_codes', 'expert_codes', 'n_valid_runs'])
    for rid, r in cl.items():
        if rid not in final: continue
        w.writerow([rid, r['form'], r['clause_id'], r['set'], ';'.join(map(str, sorted(final[rid]))),
                    ';'.join(map(str, sorted(ref[rid]))) if rid in ref else 'EXCLUDED',
                    sum(1 for run in runs if rid in run and run[rid]['codes'] is not None)])

# ---------- agreement on the chosen set ----------
ids = [rid for rid in final if rid in ref and (a.set == 'all' or cl[rid]['set'] == a.set)]
def kappa(tp, fp, fn, tn):
    n = tp + fp + fn + tn; po = (tp + tn) / n; pe = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else float('nan')
def alpha_nominal(units):
    """Krippendorff's alpha, nominal; units = list of lists of values (one list per unit, >=2 values)."""
    from collections import Counter
    o = Counter(); nc = Counter()
    for vals in units:
        m = len(vals)
        if m < 2: continue
        cnt = Counter(vals)
        for c in cnt:
            for k in cnt:
                pairs = cnt[c] * (cnt[k] - (1 if c == k else 0))
                o[(c, k)] += pairs / (m - 1)
    for (c, k), v in o.items():
        if c == k: pass
    for (c, k), v in o.items(): nc[c] += v
    n = sum(nc.values())
    Do = sum(v for (c, k), v in o.items() if c != k)
    De = sum(nc[c] * nc[k] for c in nc for k in nc if c != k) / (n - 1)
    return 1 - Do / De if De else float('nan')

per = []; TP = FP = FN = 0
for k in K:
    tp = sum(1 for i in ids if k in final[i] and k in ref[i]); fp = sum(1 for i in ids if k in final[i] and k not in ref[i])
    fn = sum(1 for i in ids if k not in final[i] and k in ref[i]); tn = len(ids) - tp - fp - fn
    TP += tp; FP += fp; FN += fn
    p = tp / (tp + fp) if tp + fp else float('nan'); rc = tp / (tp + fn) if tp + fn else float('nan')
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else float('nan')
    per.append({'code': k, 'label': codes[k], 'expert_n': tp + fn, 'model_n': tp + fp, 'TP': tp, 'FP': fp, 'FN': fn, 'TN': tn,
                'precision': round(p, 3), 'recall': round(rc, 3), 'F1': round(f1, 3), 'kappa': round(kappa(tp, fp, fn, tn), 3)})
with open(os.path.join(OUT, 'agreement_per_code.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(per[0])); w.writeheader(); w.writerows(per)
valid = [x for x in per if x['expert_n'] > 0]
P = TP / (TP + FP); Rr = TP / (TP + FN)
units_me = [[int(k in final[i]), int(k in ref[i])] for i in ids for k in K]
overall = {'set': a.set, 'n_clauses': len(ids), 'exact_match': round(sum(final[i] == ref[i] for i in ids) / len(ids), 3),
           'micro_precision': round(P, 3), 'micro_recall': round(Rr, 3), 'micro_F1': round(2 * P * Rr / (P + Rr), 3),
           'macro_precision': round(sum(x['precision'] for x in valid if x['precision'] == x['precision']) / len(valid), 3),
           'macro_recall': round(sum(x['recall'] for x in valid) / len(valid), 3),
           'macro_F1': round(sum(x['F1'] for x in valid) / len(valid), 3),
           'mean_kappa': round(sum(x['kappa'] for x in valid) / len(valid), 3),
           'alpha_model_vs_expert': round(alpha_nominal(units_me), 3),
           'clauses_missing_a_run': len(missing)}

# ---------- run consistency ----------
ids_all = [rid for rid in final if all(rid in run and run[rid]['codes'] is not None for run in runs)]
units_runs = [[int(k in run[i]['codes']) for run in runs] for i in ids_all for k in K]
overall['alpha_among_runs'] = round(alpha_nominal(units_runs), 3)
overall['identical_all_runs'] = round(sum(all(set(run[i]['codes']) == set(runs[0][i]['codes']) for run in runs) for i in ids_all) / len(ids_all), 3)
with open(os.path.join(OUT, 'agreement_overall.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['measure', 'value']); [w.writerow([k, v]) for k, v in overall.items()]
with open(os.path.join(OUT, 'run_consistency.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['code', 'label', 'clauses_all_runs_agree', 'clauses_split'])
    for k in K:
        agree = sum(len({int(k in run[i]['codes']) for run in runs}) == 1 for i in ids_all)
        w.writerow([k, codes[k], agree, len(ids_all) - agree])

# ---------- findings level (all clauses in the reference) ----------
ids_f = [rid for rid in final if rid in ref]
def freq(src):
    return {(k, fm): sum(1 for i in ids_f if cl[i]['form'] == fm and k in src[i]) for k in K for fm in FORMS}
fe, fmod = freq(ref), freq(final)
for name, tab in (('frequency_expert.csv', fe), ('frequency_model.csv', fmod)):
    with open(os.path.join(OUT, name), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['code', 'label'] + FORMS + ['total'])
        for k in K: w.writerow([k, codes[k]] + [tab[(k, fm)] for fm in FORMS] + [sum(tab[(k, fm)] for fm in FORMS)])
def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v); i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]: j += 1
        for t in range(i, j + 1): r[order[t]] = (i + j) / 2 + 1
        i = j + 1
    return r
def spearman(x, y):
    rx, ry = ranks(x), ranks(y); n = len(x); mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry)); vx = sum((a - mx) ** 2 for a in rx); vy = sum((b - my) ** 2 for b in ry)
    return cov / (vx * vy) ** 0.5 if vx and vy else float('nan')
with open(os.path.join(OUT, 'findings_per_form.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['form', 'n_clauses', 'spearman_rho', 'expert_gaps', 'model_gaps', 'gaps_both', 'gaps_expert_only', 'gaps_model_only'])
    for fm in FORMS:
        x = [fe[(k, fm)] for k in K]; y = [fmod[(k, fm)] for k in K]
        ge = {k for k in K if fe[(k, fm)] == 0}; gm = {k for k in K if fmod[(k, fm)] == 0}
        w.writerow([fm, sum(1 for i in ids_f if cl[i]['form'] == fm), round(spearman(x, y), 3), len(ge), len(gm), len(ge & gm), len(ge - gm), len(gm - ge)])
with open(os.path.join(OUT, 'gaps.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['code', 'label', 'form', 'expert_freq', 'model_freq', 'gap_status'])
    for k in K:
        for fm in FORMS:
            e0, m0 = fe[(k, fm)] == 0, fmod[(k, fm)] == 0
            if e0 or m0:
                w.writerow([k, codes[k], fm, fe[(k, fm)], fmod[(k, fm)], 'gap in both' if e0 and m0 else 'gap in expert coding only' if e0 else 'gap in model coding only'])

# ---------- consistency on identical clause text across forms ----------
import re, itertools, collections
norm = lambda t: re.sub(r'[^a-z]', '', t.lower())
grp = collections.defaultdict(list)
for i in ids_f:
    if len(norm(cl[i]['clause_text'])) > 40: grp[norm(cl[i]['clause_text'])].append(i)
pairs = [(x, y) for v in grp.values() if len(v) > 1 for x, y in itertools.combinations(v, 2)]
with open(os.path.join(OUT, 'consistency_identical_text.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['form_a', 'form_b', 'pairs', 'expert_same_codes', 'model_same_codes'])
    bypair = collections.defaultdict(list)
    for x, y in pairs: bypair[tuple(sorted((cl[x]['form'], cl[y]['form']), key=FORMS.index))].append((x, y))
    for (fa, fb), pp in sorted(bypair.items(), key=lambda t: -len(t[1])):
        w.writerow([fa, fb, len(pp), round(sum(ref[x] == ref[y] for x, y in pp) / len(pp), 3), round(sum(final[x] == final[y] for x, y in pp) / len(pp), 3)])
    w.writerow(['ALL', '', len(pairs), round(sum(ref[x] == ref[y] for x, y in pairs) / len(pairs), 3), round(sum(final[x] == final[y] for x, y in pairs) / len(pairs), 3)])

# ---------- disagreement sample (chosen set) ----------
rng = random.Random(20260928); rows = []
for k in K:
    for typ in ('FP', 'FN'):
        lst = [i for i in ids if (typ == 'FP' and k in final[i] and k not in ref[i]) or (typ == 'FN' and k not in final[i] and k in ref[i])]
        pick = sorted(rng.sample(lst, 20)) if len(lst) > 20 else lst
        for i in pick:
            rows.append([k, codes[k], typ, len(lst), cl[i]['form'], cl[i]['clause_id'], ';'.join(map(str, sorted(ref[i]))),
                         ';'.join(map(str, sorted(final[i]))), just[i].get(k, ''), cl[i]['clause_text'], '', ''])
with open(os.path.join(OUT, 'disagreement_review.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['code', 'label', 'type', 'n_of_this_type', 'form', 'clause_id', 'expert_codes', 'model_codes', 'model_justification', 'clause_text',
                'classification (model error / expert omission or inconsistency / ambiguous)', 'notes'])
    w.writerows(rows)

print('\n'.join(f'{k:>24}: {v}' for k, v in overall.items()))
print('outputs in', OUT)
