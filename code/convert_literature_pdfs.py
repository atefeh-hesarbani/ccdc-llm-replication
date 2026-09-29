import pymupdf, json, re, os, sys, unicodedata, collections, csv, subprocess
BASE=os.path.expanduser('~/mnt/72 Articels'); OUT=os.path.join(BASE,'Text_for_LLM')
m=json.load(open(os.path.expanduser('~/work/map.json')))
ml={x[0]:x for x in json.load(open(os.path.join(OUT,'master_list_index.json')))}
only=set(int(a) for a in sys.argv[1:])
PAT=[r'downloaded from', r'copyright asce', r'for personal use only', r'all rights reserved', r'^©', r'creative commons', r'^\s*\d{1,4}\s*$', r'^page \d+( of \d+)?$', r'emerald\.com/insight', r'www\.mdpi\.com/journal', r'tandfonline\.com/journals', r'^\s*(downloaded|accessed) (by|on)']
REF=re.compile(r'^\s*(\d+\.?\s*)?(references|reference list|bibliography|literature cited|works cited|references and notes)\s*:?\s*$',re.I)
APP=re.compile(r'^\s*((appendix|appendices)\b|(table|figure|fig\.)\s*[a-z]?\d+[\.:\s])',re.I)
def norm(l): return re.sub(r'\d+','#',l.strip().lower())
def pages_text(f,rng):
    doc=pymupdf.open(os.path.join(BASE,f))
    a,b=rng if rng else (1,doc.page_count)
    return [doc[i].get_text() for i in range(a-1,b)]
def clean(pages):
    pl=[[re.sub('[\u200b\u200c\u200d\u2060\ufeff\u00ad]','',unicodedata.normalize('NFKC',l)).rstrip() for l in p.split('\n')] for p in pages]
    pl=[[l for l in p if l.strip()] for p in pl]
    EDGE=4
    cnt=collections.Counter()
    for p in pl: cnt.update(set(norm(l) for l in p[:EDGE]+p[-EDGE:]))
    rep={k for k,v in cnt.items() if len(pl)>=3 and v>=max(3,0.4*len(pl)) and len(k)<150}
    STRICT=[x for x in PAT if not x.startswith('^\\s*\\d') and not x.startswith('^page')]
    removed=0; lines=[]
    for p in pl:
        ints=[int(l) for l in p if re.fullmatch(r'\s*\d{1,4}\s*',l)]
        linenum=len(ints)>=15 and sum(1 for a,b in zip(ints,ints[1:]) if b-a==1)>=0.8*(len(ints)-1)
        for j,l in enumerate(p):
            s=l.strip(); edge=j<EDGE or j>=len(p)-EDGE
            pure_int=bool(re.fullmatch(r'\d{1,4}',s))
            if (edge and norm(s) in rep) or (edge and (pure_int or re.fullmatch(r'page \d+( of \d+)?',s,re.I))) or (linenum and pure_int) or any(re.search(x,s,re.I) for x in STRICT):
                removed+=1; continue
            lines.append(s)
        lines.append('')
    idx=[i for i,l in enumerate(lines) if REF.match(l)]
    ref_cut=None; kept_app=False
    total=sum(len(l) for l in lines)
    reflike=lambda l: bool(re.search(r'\b(19|20)\d{2}[a-z]?\b',l) and re.search(r'(doi|https?://|et al\.|\bpp?\.\s*\d|\b\d+\s*\(\d+\)|journal|proceedings|vol\.)',l,re.I))
    if idx:
        i=idx[-1]
        if sum(len(l) for l in lines[:i])>total*0.4:
            tail=lines[i:]; start=None
            for j,l in enumerate(tail):
                if APP.match(l):
                    rest=[x for x in tail[j:] if x]
                    if sum(reflike(x) for x in rest)<=max(2,0.03*len(rest)): start=j; break
            ref_cut=sum(1 for l in (tail[:start] if start is not None else tail) if l)
            lines=lines[:i]+(tail[start:] if start is not None else [])
            kept_app=start is not None
    txt='\n'.join(lines)
    txt=re.sub(r'(\w)-\n(\w)',r'\1\2',txt)
    txt=re.sub(r'(?<![\w*])\*(?=(e|is|erefore|ere|ey|en|us|at|ese|ose|rough|ird)\b)','Th',txt)
    txt=re.sub(r'\n{3,}','\n\n',txt).strip()+'\n'
    return txt,removed,ref_cut,kept_app
rows=[]
for key,nums in m.items():
    if not nums: continue
    num=nums[0]
    if only and num not in only: continue
    f,rng=(key.split('#')[0],tuple(map(int,key.split('#')[1].split('-')))) if '#' in key else (key,None)
    if num==51:
        txt=open(os.path.expanduser('~/work/ocr51.txt')).read(); pages=None
        txt,removed,ref_cut,kept_app=clean(txt.split('\f'))
        method='OCR'
    elif num in (11,59,72):
        pages=subprocess.run(['pdftotext','-f',str(rng[0]),'-l',str(rng[1]),os.path.join(BASE,f),'-'],capture_output=True,text=True).stdout.split('\f')[:rng[1]-rng[0]+1]
        txt,removed,ref_cut,kept_app=clean(pages); method='text layer (pdftotext)'
    else:
        pages=pages_text(f,rng); txt,removed,ref_cut,kept_app=clean(pages); method='text layer'
    open(os.path.join(OUT,f'{num:02d}.txt'),'w').write(txt)
    letters=sum(c.isalpha() for c in txt); ascii_l=sum(c.isascii() and c.isalpha() for c in txt)
    flags=[]
    if ref_cut is None: flags.append('no reference heading found')
    if len(txt)<15000: flags.append('short text')
    if letters and ascii_l/letters<0.95: flags.append('possible garbled text')
    if pages and any(len(p.strip())<50 for p in pages): flags.append(f'{sum(len(p.strip())<50 for p in pages)} near-empty page(s)')
    if not re.search(r'abstract',txt[:6000],re.I): flags.append('no "Abstract" near start')
    rows.append({'study_id':f'{num:02d}','title':ml[num][2],'source_file':f,'pdf_pages_used':f'{rng[0]}-{rng[1]}' if rng else 'all','method':method,'chars':len(txt),'header_footer_lines_removed':removed,'reference_lines_removed':ref_cut or 0,'appendix_kept':'yes' if kept_app else '','qc_flags':'; '.join(flags),'status':'converted'})
json.dump(rows,open(os.path.expanduser(f'~/work/rows_{"part" if only else "all"}.json'),'w'))
print(len(rows)); 
for r in rows:
    if r['qc_flags']: print(r['study_id'],r['chars'],r['qc_flags'])
