"""Development comparison on the 262-clause development set (Batch API).
  python dev_compare.py
Submits one batch per condition, waits, collects and scores. If interrupted,
run it again: it resumes from Results/study2/dev_compare_batches.json."""
import json, os, time, anthropic
import prompts, common, score_dev

CONDITIONS = [  # run name, model, effort, prompt version
    ('dev_s5_medium',    'claude-sonnet-5',   'medium', 'v1'),
    ('dev_s5_high',      'claude-sonnet-5',   'high',   'v1'),
    ('dev_s55_medium',   'claude-sonnet-5-5', 'medium', 'v1'),
    ('dev_s5_medium_v2', 'claude-sonnet-5',   'medium', 'v2'),   # development round 1
]
client = anthropic.Anthropic()
state_path = os.path.join(common.RESULTS, 'dev_compare_batches.json')
state = json.load(open(state_path)) if os.path.exists(state_path) else {}
codes = prompts.load_codebook()
clauses = prompts.load_clauses(); dev = [r for r in clauses if r['set'] == 'development']
rows = {r['row_id']: r for r in clauses}

for run, model, effort, version in CONDITIONS:
    if run in state: continue
    shared = prompts.shared_system(codes, version)
    reqs = [{'custom_id': f"run{run}_{r['row_id']}", 'params': prompts.build_params(r, codes, shared, model, effort, version)} for r in dev]
    try:
        b = client.messages.batches.create(requests=reqs)
    except anthropic.APIError as e:
        print(f'{run}: submission failed -> {e}'); continue
    state[run] = {'batch_id': b.id, 'model': model, 'effort': effort, 'prompt_version': version, 'collected': False}
    json.dump(state, open(state_path, 'w'), indent=1)
    common.append(os.path.join(common.RESULTS, 'batches.jsonl'), {'batch_id': b.id, 'run': run, 'set': 'development', 'n': len(reqs), 'model': model, 'effort': effort, 'prompt_version': version, 'created': str(b.created_at)})
    print(f'{run}: submitted {b.id} ({len(reqs)} requests)')

while True:
    pending = False
    for run, s in state.items():
        if s['collected']: continue
        b = client.messages.batches.retrieve(s['batch_id'])
        if b.processing_status != 'ended':
            pending = True; c = b.request_counts
            print(f'{run}: {b.processing_status} | done {c.succeeded + c.errored}/{c.processing + c.succeeded + c.errored + c.canceled + c.expired}'); continue
        out = os.path.join(common.RESULTS, f'run{run}.jsonl')
        if os.path.exists(out): os.replace(out, out + '.old')
        errs = 0
        for e in client.messages.batches.results(s['batch_id']):
            r = rows[e.custom_id.rsplit('_', 1)[1]]
            if e.result.type == 'succeeded':
                rec = common.record(r, run, e.result.message)
            else:
                msg = getattr(getattr(e.result, 'error', None), 'error', None)
                rec = common.record(r, run, None, error=f'{e.result.type}: {getattr(msg, "message", "")}')
            errs += bool(rec['error']); common.append(out, rec)
        s['collected'] = True; json.dump(state, open(state_path, 'w'), indent=1)
        print(f'{run}: collected -> {out} ({errs} errors)')
    if not pending: break
    print('waiting 60 s ... (you can close this and run the script again later)'); time.sleep(60)

ref = score_dev.expert(); cb = {int(c['id']): c['label'] for c in codes}
res = [score_dev.score(run, ref, cb) for run in state]
print(); print('  '.join(f'{k:>14}' for k in res[0]))
for r in res: print('  '.join(f'{v:>14.3f}' if isinstance(v, float) else f'{v:>14}' for v in r.values()))
