"""Pilot: code N development clauses synchronously and report tokens and cost.
Usage: python run_pilot.py [N]   (default 20). Requires ANTHROPIC_API_KEY."""
import sys, random, os, anthropic
import prompts, common
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
codes = prompts.load_codebook(); shared = prompts.shared_system(codes)
dev = [r for r in prompts.load_clauses() if r['set'] == 'development']
sample = random.Random(7).sample(dev, N)
client = anthropic.Anthropic()
out = os.path.join(common.RESULTS, 'pilot.jsonl')
tot = {'input_tokens': 0, 'output_tokens': 0, 'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 0}
for i, r in enumerate(sample, 1):
    for attempt in range(2):
        msg = client.messages.create(**prompts.build_params(r, codes, shared))
        if msg.stop_reason != 'max_tokens': break
    rec = common.record(r, 'pilot', msg)
    common.append(out, rec)
    for k in tot: tot[k] += rec['usage'].get(k) or 0
    print(f"{i:>2}/{N} {r['form']:<11} {r['clause_id']:<12} codes={rec['codes']} out_tok={rec['usage']['output_tokens']} stop={rec['stop_reason']} err={rec['error']}")
c = common.cost(tot)
print('\nTOTAL tokens', tot)
print(f'Pilot cost (standard API): ${c:.3f}  | per clause ${c/N:.4f}')
per = c / N
print(f'Projected Study 2 (1,935 clauses x 3 runs + 262 dev): standard ${per*(1935*3+262):.0f}, with Batch API ~${per*(1935*3+262)/2:.0f}')
