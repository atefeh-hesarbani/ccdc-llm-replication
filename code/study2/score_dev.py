"""Score Study 2 runs against the expert reference.
  python score_dev.py pilot dev_med dev_high dev_s55     (run names = Results/study2/<name>.jsonl or run<name>.jsonl)
Writes Results/study2/score_<name>_per_code.csv and prints a comparison table."""
import csv, json, os, sys
import prompts, common

def expert():
    ref = {}
    with open(os.path.join(prompts.BASE, 'Human', 'expert_coding_reference.csv'), encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            e = r['expert_codes'].strip()
            ref[r['row_id'].zfill(4)] = set() if e in ('', 'N/A') else {int(x) for x in e.split(';')}
    return ref

def load(name):
    for fn in (f'{name}.jsonl', f'run{name}.jsonl'):
        p = os.path.join(common.RESULTS, fn)
        if os.path.exists(p):
            return [json.loads(l) for l in open(p, encoding='utf-8')]
    sys.exit(f'no results file for {name}')

def kappa(a, b, c, d):  # a=both1, b=llm1 exp0, c=llm0 exp1, d=both0
    n = a + b + c + d; po = (a + d) / n
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else float('nan')

def score(name, ref, codes):
    recs = {}
    for r in load(name):
        recs[r['row_id'].zfill(4)] = r            # last record per clause wins
    rows = [(rid, r) for rid, r in recs.items() if rid in ref]
    ok = [(rid, r) for rid, r in rows if r['codes'] is not None and not r['error']]
    cnt = {k: [0, 0, 0, 0] for k in codes}
    exact = 0; th = out = 0; cost = 0.0
    for rid, r in ok:
        m, e = set(r['codes']), ref[rid]; exact += (m == e)
        for k in codes:
            i = 0 if (k in m and k in e) else 1 if k in m else 2 if k in e else 3
            cnt[k][i] += 1
    for rid, r in rows:
        u = r['usage'] or {}
        th += ((u.get('output_tokens_details') or {}).get('thinking_tokens') or 0); out += u.get('output_tokens', 0)
        cost += common.cost(u, batch=(r['run'] != 'pilot'))
    TP = sum(v[0] for v in cnt.values()); FP = sum(v[1] for v in cnt.values()); FN = sum(v[2] for v in cnt.values())
    P = TP / max(1, TP + FP); R = TP / max(1, TP + FN); F = 2 * P * R / max(1e-9, P + R)
    per = []
    for k in codes:
        a, b, c, d = cnt[k]; p = a / (a + b) if a + b else float('nan'); rc = a / (a + c) if a + c else float('nan')
        f1 = 2 * a / (2 * a + b + c) if (2 * a + b + c) else float('nan')
        per.append({'code': k, 'label': codes[k], 'expert_n': a + c, 'llm_n': a + b, 'TP': a, 'FP': b, 'FN': c,
                    'precision': p, 'recall': rc, 'f1': f1, 'kappa': kappa(a, b, c, d)})
    with open(os.path.join(common.RESULTS, f'score_{name}_per_code.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(per[0])); w.writeheader(); w.writerows(per)
    valid = [x for x in per if x['expert_n'] > 0]
    macro = sum(x['f1'] if x['f1'] == x['f1'] else 0 for x in valid) / max(1, len(valid))
    ks = [x['kappa'] for x in valid if x['kappa'] == x['kappa']]
    return {'run': name, 'n': len(ok), 'errors': len(rows) - len(ok), 'exact': exact / max(1, len(ok)),
            'P': P, 'R': R, 'microF1': F, 'macroF1': macro, 'mean_kappa': sum(ks) / max(1, len(ks)),
            'think_tok/clause': th / max(1, len(rows)), 'out_tok/clause': out / max(1, len(rows)), 'cost$': cost}

if __name__ == '__main__':
    ref = expert(); codes = {int(c['id']): c['label'] for c in prompts.load_codebook()}
    res = [score(n, ref, codes) for n in sys.argv[1:]]
    keys = list(res[0])
    print('  '.join(f'{k:>14}' for k in keys))
    for r in res:
        print('  '.join(f'{v:>14.3f}' if isinstance(v, float) else f'{v:>14}' for v in r.values()))
