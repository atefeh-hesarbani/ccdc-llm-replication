"""Study 1 - inductive codebook generation, 3 independent replicates x 5 stages.
  python run_study1.py pilot     Stage 1 on 2 studies (synchronous), to check output and cost
  python run_study1.py           full run; resumable - run it again after any interruption
Stage 1 (72 studies x 3 replicates) goes through the Message Batches API; Stages 2-5 are
sequential synchronous requests, with the 3 replicates processed in parallel.
Outputs: Results/study1/rep1..rep3/, calls.jsonl (every request), summary.csv."""
import datetime, json, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
import anthropic
import s1_prompts as P

REPS = ['1', '2', '3']
PRICE = {'input': 2.0, 'output': 10.0, 'cache_write': 2.5, 'cache_read': 0.2}   # Sonnet 5, USD / MTok
client = anthropic.Anthropic(timeout=1800.0, max_retries=4)
os.makedirs(P.RESULTS, exist_ok=True)
LOCK = threading.Lock()
STATE = os.path.join(P.RESULTS, 'state.json')
state = json.load(open(STATE)) if os.path.exists(STATE) else {}


def save_state():
    with LOCK:
        json.dump(state, open(STATE, 'w'), indent=1)


def cost(u, batch=False):
    c = (u.get('input_tokens', 0) * PRICE['input'] + u.get('output_tokens', 0) * PRICE['output']
         + (u.get('cache_creation_input_tokens') or 0) * PRICE['cache_write']
         + (u.get('cache_read_input_tokens') or 0) * PRICE['cache_read']) / 1e6
    return c * (0.5 if batch else 1.0)


def log_call(rep, stage, item, message, batch, error=None, attempt=1):
    u = message.usage.model_dump() if message is not None else {}
    rec = {'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds'), 'rep': rep, 'stage': stage,
           'item': item, 'attempt': attempt, 'batch': batch, 'model': getattr(message, 'model', None),
           'stop_reason': getattr(message, 'stop_reason', None), 'usage': u, 'cost': round(cost(u, batch), 5), 'error': error}
    with LOCK:
        with open(os.path.join(P.RESULTS, 'calls.jsonl'), 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec) + '\n')


def call(rep, stage, item, params, tries=3):
    """Synchronous request; re-requested (same input) if it fails, is truncated or breaks the schema."""
    for attempt in range(1, tries + 1):
        try:
            m = client.messages.create(**params)
        except anthropic.APIError as e:
            log_call(rep, stage, item, None, False, error=str(e)[:300], attempt=attempt); time.sleep(20); continue
        if m.stop_reason == 'max_tokens':
            log_call(rep, stage, item, m, False, error='max_tokens', attempt=attempt); continue
        try:
            out = P.parse(m)
        except Exception as e:
            log_call(rep, stage, item, m, False, error=f'parse: {e}', attempt=attempt); continue
        log_call(rep, stage, item, m, False, attempt=attempt)
        return out
    raise RuntimeError(f'rep {rep} {stage} {item}: no valid response after {tries} attempts')


def rdir(rep):
    d = os.path.join(P.RESULTS, f'rep{rep}'); os.makedirs(d, exist_ok=True); return d


def jload(path):
    return json.load(open(path, encoding='utf-8'))


def jsave(path, obj):
    json.dump(obj, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ Stage 1
def stage1():
    studies = P.load_studies()
    assert len(studies) == 72, f'expected 72 study texts, found {len(studies)}'
    texts = dict(studies)
    if 'stage1_batch' not in state:
        reqs = [{'custom_id': f'r{rep}_s{sid}', 'params': P.params(P.S1_SYSTEM, P.s1_user(sid, t), P.S1_SCHEMA)}
                for rep in REPS for sid, t in studies]
        b = client.messages.batches.create(requests=reqs)
        state['stage1_batch'] = b.id; state['stage1_submitted'] = str(b.created_at); save_state()
        print(f'Stage 1: submitted {b.id} ({len(reqs)} requests)')
    if not state.get('stage1_collected'):
        while True:
            b = client.messages.batches.retrieve(state['stage1_batch'])
            if b.processing_status == 'ended':
                break
            c = b.request_counts
            print(f'Stage 1: {b.processing_status} | done {c.succeeded + c.errored}/216 - waiting 60 s '
                  '(you can close this and run the script again later)')
            time.sleep(60)
        recs = {rep: {} for rep in REPS}; failed = []
        for e in client.messages.batches.results(state['stage1_batch']):
            rep, sid = re.match(r'r(\d)_s(\d+)', e.custom_id).groups()
            m = e.result.message if e.result.type == 'succeeded' else None
            err = None if m else e.result.type
            if m is not None:
                if m.stop_reason == 'max_tokens':
                    err = 'max_tokens'
                else:
                    try:
                        recs[rep][sid] = P.parse(m)
                    except Exception as ex:
                        err = f'parse: {ex}'
            log_call(rep, 'stage1', sid, m, True, error=err)
            if err:
                failed.append((rep, sid))
        state['stage1_rerequested'] = len(failed); save_state()
        for rep, sid in failed:
            print(f'Stage 1: re-requesting rep {rep} study {sid}')
            recs[rep][sid] = call(rep, 'stage1', sid, P.params(P.S1_SYSTEM, P.s1_user(sid, texts[sid]), P.S1_SCHEMA), tries=3)
        for rep in REPS:
            out = [dict(recs[rep][sid], study_id=sid) for sid, _ in studies]
            jsave(os.path.join(rdir(rep), 'stage1_master_list.json'), out)
        state['stage1_collected'] = True; save_state()
        print('Stage 1: collected')


# ------------------------------------------------------------------ Stages 2-5 for one replicate
def later_stages(rep):
    d = rdir(rep)
    records = jload(os.path.join(d, 'stage1_master_list.json'))

    p2 = os.path.join(d, 'stage2_themes.json')
    if not os.path.exists(p2):
        jsave(p2, call(rep, 'stage2', 'all', P.params(P.S2_SYSTEM, P.s2_user(records), P.S2_SCHEMA)))
        print(f'rep {rep}: Stage 2 done')
    themes = jload(p2)['themes']

    s3 = []
    for t in themes:
        p3 = os.path.join(d, f"stage3_{t['theme_id']}.json")
        if not os.path.exists(p3):
            out = call(rep, 'stage3', t['theme_id'], P.params(P.S3_SYSTEM, P.s3_user(t, records), P.S3_SCHEMA))
            out['theme_id'] = t['theme_id']; jsave(p3, out)
        s3.append(jload(p3))
    print(f'rep {rep}: Stage 3 done ({len(themes)} themes)')

    p4 = os.path.join(d, 'stage4_preliminary_codes.json')
    if not os.path.exists(p4):
        jsave(p4, call(rep, 'stage4', 'all', P.params(P.S4_SYSTEM, P.s4_user(themes, s3), P.S4_SCHEMA)))
        print(f'rep {rep}: Stage 4 done')
    codebook = P.codebook_from_stage4(jload(p4)['codes'])

    for i, form in enumerate(P.FORMS, 1):
        p5 = os.path.join(d, f"stage5_{i}_{form.replace(' ', '_')}.json")
        if not os.path.exists(p5):
            prm = P.params(P.S5_SYSTEM, P.s5_user(form, codebook, P.load_clauses(form)), P.S5_SCHEMA)
            prm['max_tokens'] = P.MAX_TOKENS_STAGE5
            out = call(rep, 'stage5', form, prm)
            out['form'] = form; jsave(p5, out)
            print(f'rep {rep}: Stage 5 {form} done ({len(out["changes"])} changes, {len(out["codebook"])} codes)')
        codebook = jload(p5)['codebook']
    jsave(os.path.join(d, 'final_codebook.json'), codebook)
    print(f'rep {rep}: finished ({len(codebook)} final codes)')


# ------------------------------------------------------------------ summary
def summary():
    texts = dict(P.load_studies())
    norm = lambda s: re.sub(r'\s+', ' ', s).strip().lower()
    ntexts = {k: norm(v) for k, v in texts.items()}
    rows = []
    for rep in REPS:
        d = rdir(rep)
        rec = jload(os.path.join(d, 'stage1_master_list.json'))
        ideas = [(r['study_id'], i) for r in rec for i in r['ideas']]
        found = sum(norm(i['quote']).strip('"…. ') in ntexts[s] for s, i in ideas)
        th = jload(os.path.join(d, 'stage2_themes.json'))['themes']
        s3 = [jload(os.path.join(d, f"stage3_{t['theme_id']}.json")) for t in th]
        cats = sum(len(x['categories']) for x in s3)
        codes3 = sum(len(c['codes']) for x in s3 for c in x['categories'])
        subs = sum(len(k['sub_codes']) for x in s3 for c in x['categories'] for k in c['codes'])
        pre = len(jload(os.path.join(d, 'stage4_preliminary_codes.json'))['codes'])
        s5 = [jload(os.path.join(d, f"stage5_{i}_{f.replace(' ', '_')}.json")) for i, f in enumerate(P.FORMS, 1)]
        rows.append({'replicate': rep, 'studies_with_ideas': sum(1 for r in rec if r['ideas']), 'ideas': len(ideas),
                     'quotes_found_verbatim': round(found / max(1, len(ideas)), 3), 'themes': len(th),
                     'categories': cats, 'stage3_codes': codes3, 'stage3_sub_codes': subs, 'preliminary_codes': pre,
                     **{f'codes_after_{f}': len(x['codebook']) for f, x in zip(P.FORMS, s5)},
                     **{f'changes_{f}': len(x['changes']) for f, x in zip(P.FORMS, s5)},
                     'final_codes': len(s5[-1]['codebook'])})
        with open(os.path.join(d, 'final_codebook.csv'), 'w', newline='', encoding='utf-8-sig') as f:
            import csv
            w = csv.DictWriter(f, fieldnames=['code_id', 'label', 'definition', 'include_when', 'exclude_when', 'memo'])
            w.writeheader(); w.writerows(s5[-1]['codebook'])
    import csv
    with open(os.path.join(P.RESULTS, 'summary.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    tot = sum(json.loads(l)['cost'] for l in open(os.path.join(P.RESULTS, 'calls.jsonl')))
    for r in rows:
        print(f"rep {r['replicate']}: {r['themes']} themes, {r['stage3_codes']} stage-3 codes, "
              f"{r['preliminary_codes']} preliminary codes, {r['final_codes']} final codes; "
              f"quotes found verbatim {r['quotes_found_verbatim']}")
    print('total cost of Study 1 ~$%.2f' % tot)


# ------------------------------------------------------------------ pilot
def pilot():
    d = os.path.join(P.RESULTS, 'pilot'); os.makedirs(d, exist_ok=True)
    studies = P.load_studies(); tot = 0.0
    for sid, text in studies[:2]:
        m = client.messages.create(**P.params(P.S1_SYSTEM, P.s1_user(sid, text), P.S1_SCHEMA))
        log_call('pilot', 'stage1', sid, m, False)
        out = P.parse(m); jsave(os.path.join(d, f'stage1_{sid}.json'), out)
        c = cost(m.usage.model_dump()); tot += c
        print(f"study {sid}: stop={m.stop_reason} in={m.usage.input_tokens} out={m.usage.output_tokens} "
              f"ideas={len(out['ideas'])} cost=${c:.3f}")
    print(f'pilot cost ${tot:.3f} | Stage 1 projection (72 x 3, batch) ~${tot / 2 * 216 / 2:.2f}')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'pilot':
        pilot(); sys.exit()
    stage1()
    with ThreadPoolExecutor(max_workers=3) as ex:
        for f in [ex.submit(later_stages, rep) for rep in REPS]:
            f.result()
    summary()
