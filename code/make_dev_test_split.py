"""Split the Study 2 clause set into a development set (250 clauses) and a test set.
Stratified random sampling within each CCDC form, proportional to form size,
then top-up so every code appears in >=5 development clauses (expert coding)."""
import csv, random, collections, os
SEED = 20260928
DEV_SIZE = 250
MIN_PER_CODE = 5
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
clauses = list(csv.DictReader(open(f'{BASE}/LLM Source/CCDC_ai_input_Clauses.csv', encoding='utf-8-sig')))
ref = {r['row_id']: r for r in csv.DictReader(open(f'{BASE}/Human/expert_coding_reference.csv', encoding='utf-8-sig'))}
codes = {rid: set(map(int, r['expert_codes'].split(';'))) if r['expert_codes'] else set() for rid, r in ref.items()}
rng = random.Random(SEED)
eligible = [c for c in clauses if c['row_id'] in ref]
by_form = collections.defaultdict(list)
for c in eligible: by_form[c['form']].append(c['row_id'])
# proportional allocation (largest remainder)
total = len(eligible)
quota = {f: DEV_SIZE * len(v) / total for f, v in by_form.items()}
alloc = {f: int(q) for f, q in quota.items()}
for f in sorted(quota, key=lambda f: quota[f] - alloc[f], reverse=True)[:DEV_SIZE - sum(alloc.values())]:
    alloc[f] += 1
dev = set()
for f in sorted(by_form):
    dev |= set(rng.sample(sorted(by_form[f]), alloc[f]))
initial = len(dev)
added = []
for code in range(1, 20):
    have = sum(1 for r in dev if code in codes[r])
    if have < MIN_PER_CODE:
        pool = sorted(r for r in codes if code in codes[r] and r not in dev)
        pick = rng.sample(pool, MIN_PER_CODE - have)
        dev |= set(pick); added += [(code, p) for p in pick]
out = []
for c in clauses:
    s = 'excluded' if c['row_id'] not in ref else ('development' if c['row_id'] in dev else 'test')
    out.append({'row_id': c['row_id'], 'form': c['form'], 'clause_id': c['clause_id'], 'set': s})
with open(f'{BASE}/LLM Source/study2_dev_test_split.csv', 'w', newline='', encoding='utf-8-sig') as fh:
    w = csv.DictWriter(fh, fieldnames=['row_id', 'form', 'clause_id', 'set']); w.writeheader(); w.writerows(out)
cnt = collections.Counter(o['set'] for o in out)
print('seed', SEED, '| initial dev', initial, '| top-up added', len(added), added)
print(dict(cnt))
print('dev per form', dict(collections.Counter(o['form'] for o in out if o['set'] == 'development')))
print('dev per code', {k: sum(1 for r in dev if k in codes[r]) for k in range(1, 20)})
print('dev uncoded', sum(1 for r in dev if not codes[r]), '| test uncoded', sum(1 for o in out if o['set'] == 'test' and not codes[o['row_id']]))
