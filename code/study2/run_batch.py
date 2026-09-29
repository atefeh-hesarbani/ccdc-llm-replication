"""Study 2 via the Message Batches API.
  python run_batch.py submit --set development --run dev1
  python run_batch.py submit --set development --run dev_high --effort high
  python run_batch.py submit --set development --run dev_s55 --model claude-sonnet-5-5
  python run_batch.py submit --set all --run 1        (all 1,935 clauses)
  python run_batch.py status  <batch_id>
  python run_batch.py collect <batch_id> --run 1
Requires ANTHROPIC_API_KEY."""
import argparse, json, os, anthropic
import prompts, common
ap = argparse.ArgumentParser(); ap.add_argument('cmd'); ap.add_argument('batch_id', nargs='?')
ap.add_argument('--set', default='development'); ap.add_argument('--run', default='1')
ap.add_argument('--model', default=None); ap.add_argument('--effort', default=None)
a = ap.parse_args(); client = anthropic.Anthropic()
log = os.path.join(common.RESULTS, 'batches.jsonl')
if a.cmd == 'submit':
    codes = prompts.load_codebook(); shared = prompts.shared_system(codes)
    rows = [r for r in prompts.load_clauses() if a.set == 'all' or r['set'] == a.set]
    reqs = [{'custom_id': f"run{a.run}_{r['row_id']}", 'params': prompts.build_params(r, codes, shared, a.model, a.effort)} for r in rows]
    b = client.messages.batches.create(requests=reqs)
    common.append(log, {'batch_id': b.id, 'run': a.run, 'set': a.set, 'n': len(reqs), 'model': a.model or prompts.MODEL, 'effort': a.effort or prompts.EFFORT, 'created': str(b.created_at)})
    print('submitted', b.id, len(reqs), 'requests |', a.model or prompts.MODEL, a.effort or prompts.EFFORT)
elif a.cmd == 'status':
    b = client.messages.batches.retrieve(a.batch_id); print(b.processing_status, b.request_counts)
elif a.cmd == 'collect':
    rows = {r['row_id']: r for r in prompts.load_clauses()}
    out = os.path.join(common.RESULTS, f'run{a.run}.jsonl'); total = 0; retry = []
    for e in client.messages.batches.results(a.batch_id):
        r = rows[e.custom_id.rsplit('_', 1)[1]]
        if e.result.type == 'succeeded':
            rec = common.record(r, a.run, e.result.message)
            if rec['stop_reason'] == 'max_tokens': retry.append(r['row_id'])
        else:
            rec = common.record(r, a.run, None, error=e.result.type); retry.append(r['row_id'])
        total += common.cost(rec['usage'], batch=True); common.append(out, rec)
    print('saved to', out, '| cost ~$%.2f' % total, '| to re-request:', len(retry), retry[:20])
