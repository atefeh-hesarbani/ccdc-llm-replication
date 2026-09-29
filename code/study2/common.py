import json, os, datetime
import prompts
RESULTS = os.path.join(prompts.BASE, 'Results', 'study2')
os.makedirs(RESULTS, exist_ok=True)
# Claude Sonnet 5 prices, USD per million tokens (standard API; Batch API = 50%)
PRICE = {'input': 2.0, 'output': 10.0, 'cache_write': 2.0 * 1.25, 'cache_read': 2.0 * 0.1}

def cost(u, batch=False):
    c = (u.get('input_tokens', 0) * PRICE['input'] + u.get('output_tokens', 0) * PRICE['output']
         + (u.get('cache_creation_input_tokens') or 0) * PRICE['cache_write']
         + (u.get('cache_read_input_tokens') or 0) * PRICE['cache_read']) / 1e6
    return c * (0.5 if batch else 1.0)

def record(r, run, message, error=None):
    u = message.usage.model_dump() if message is not None else {}
    rec = {'row_id': r['row_id'], 'form': r['form'], 'clause_id': r['clause_id'], 'set': r['set'], 'run': run,
           'timestamp_utc': datetime.datetime.utcnow().isoformat(timespec='seconds'),
           'model': getattr(message, 'model', None), 'stop_reason': getattr(message, 'stop_reason', None),
           'usage': u, 'codes': None, 'raw': None, 'error': error}
    if message is not None and error is None:
        try:
            out = prompts.parse(message); rec['raw'] = out
            rec['codes'] = sorted({c['code_id'] for c in out['codes']})
        except Exception as e:
            rec['error'] = f'parse: {e}'
    return rec

def append(path, rec):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
