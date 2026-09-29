"""Study 2 main runs: 3 independent runs over all 1,935 clauses (Batch API),
frozen configuration (claude-sonnet-5, effort=medium, current prompts.py).
  python main_runs.py
Submits run1-run3, waits, collects into Results/study2/run1.jsonl ... run3.jsonl,
and re-requests (once per round, up to 3 rounds) any clause that errored, failed the
schema or hit max_tokens. Safe to re-run: resumes from Results/study2/main_runs_state.json."""
import hashlib, json, os, time, anthropic
import prompts, common

RUNS = ['1', '2', '3']
MAX_RETRY_ROUNDS = 3
client = anthropic.Anthropic()
state_path = os.path.join(common.RESULTS, 'main_runs_state.json')
state = json.load(open(state_path)) if os.path.exists(state_path) else {}
codes = prompts.load_codebook(); shared = prompts.shared_system(codes)
clauses = prompts.load_clauses(); rows = {r['row_id']: r for r in clauses}
frozen = hashlib.sha256(open(prompts.__file__, 'rb').read()).hexdigest()[:16]
save = lambda: json.dump(state, open(state_path, 'w'), indent=1)

def submit(run, row_ids, round_):
    reqs = [{'custom_id': f"run{run}r{round_}_{rid}", 'params': prompts.build_params(rows[rid], codes, shared)} for rid in row_ids]
    b = client.messages.batches.create(requests=reqs)
    state[run]['batches'].append({'batch_id': b.id, 'round': round_, 'n': len(reqs), 'collected': False})
    save()
    common.append(os.path.join(common.RESULTS, 'batches.jsonl'), {'batch_id': b.id, 'run': run, 'round': round_, 'set': 'all', 'n': len(reqs), 'model': prompts.MODEL, 'effort': prompts.EFFORT, 'prompts_sha256_16': frozen, 'created': str(b.created_at)})
    print(f'run{run} round {round_}: submitted {b.id} ({len(reqs)} requests)')

for run in RUNS:
    if run not in state:
        state[run] = {'model': prompts.MODEL, 'effort': prompts.EFFORT, 'prompts_sha256_16': frozen, 'batches': [], 'retried': 0}
        submit(run, [r['row_id'] for r in clauses], 0)
    elif state[run]['prompts_sha256_16'] != frozen:
        raise SystemExit('prompts.py changed since submission - stop (configuration must stay frozen).')

while True:
    pending = False
    for run in RUNS:
        s = state[run]
        for bt in s['batches']:
            if bt['collected']: continue
            b = client.messages.batches.retrieve(bt['batch_id'])
            if b.processing_status != 'ended':
                pending = True; c = b.request_counts
                print(f"run{run} round {bt['round']}: {b.processing_status} | done {c.succeeded + c.errored}/{bt['n']}"); continue
            out = os.path.join(common.RESULTS, f'run{run}.jsonl'); failed = []
            for e in client.messages.batches.results(bt['batch_id']):
                r = rows[e.custom_id.rsplit('_', 1)[1]]
                if e.result.type == 'succeeded':
                    rec = common.record(r, run, e.result.message)
                else:
                    msg = getattr(getattr(e.result, 'error', None), 'error', None)
                    rec = common.record(r, run, None, error=f'{e.result.type}: {getattr(msg, "message", "")}')
                rec['round'] = bt['round']
                if rec['error'] or rec['stop_reason'] == 'max_tokens': failed.append(r['row_id'])
                common.append(out, rec)
            bt['collected'] = True; bt['failed'] = len(failed); save()
            print(f"run{run} round {bt['round']}: collected ({len(failed)} to re-request)")
            if failed and bt['round'] < MAX_RETRY_ROUNDS:
                s['retried'] += len(failed); submit(run, failed, bt['round'] + 1); pending = True
    if not pending: break
    print('waiting 60 s ... (you can close this and run the script again later)'); time.sleep(60)

tot = 0.0
for run in RUNS:
    recs = {}
    for l in open(os.path.join(common.RESULTS, f'run{run}.jsonl'), encoding='utf-8'):
        r = json.loads(l); tot += common.cost(r['usage'] or {}, batch=True); recs[r['row_id']] = r
    bad = sum(1 for r in recs.values() if r['error'] or r['codes'] is None)
    print(f"run{run}: {len(recs)} clauses, {bad} without valid output, re-requested {state[run]['retried']}")
print('total cost of main runs ~$%.2f' % tot)
