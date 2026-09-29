import re,csv,os,subprocess,glob,json,collections
BASE=os.path.expanduser('~/mnt/Final Files/LLM Source')
PDF={'CCDC 2':'CCDC_2-2020','CCDC 2 CcQ':'CCDC_2CcQ','CCDC 3':'CCDC_3-2016','CCDC 5A':'CCDC_5A','CCDC 5B':'CCDC_5B','CCDC 14':'CCDC_14','CCDC 17':'CCDC_17','CCDC 30':'CCDC_30'}
BOIL=[r'^CCDC\s?\S+\s[–-]\s\d{4}$',r'^Note:?$',r'^Note: This contract is protected',r'^This contract is protected by copyright',r'contract if the document cover page bears',r'^this contract if the document cover page',r'except to the extent that any alterations, additions or modifications are set forth in supplementary conditions\.$',r'^\d{1,3}$']
def lines_of(form):
    f=glob.glob(f'{BASE}/Standard Forms/{PDF[form]}*.pdf')[0]
    t=subprocess.run(['pdftotext',f,'-'],capture_output=True,text=True).stdout
    out=[]
    for l in t.split('\n'):
        s=l.strip().replace('\f','')
        if any(re.search(b,s) for b in BOIL): continue
        out.append(s)
    return out
PARA=re.compile(r'^([A-C])?\d+\.\d+(\.\d+)?\.?(\s|$)')
def build(form):
    L=lines_of(form)
    # definitions
    s=next(i for i,l in enumerate(L) if re.match(r'The following Definitions',l))
    e=next(i for i in range(s,len(L)) if L[i].startswith('PART 1 GENERAL PROVISIONS'))
    defs='\n'.join(x for x in L[s:e] if x and not re.match(r'^GENERAL CONDITIONS',x))
    app=next((i for i,l in enumerate(L) if l.startswith('APPENDIX 1')),len(L))
    heads={}
    for i,l in enumerate(L[:app]):
        m=re.match(r'^ARTICLE ([A-C])-(\d+)\s+(.+)$',l)
        g=re.match(r'^GC (\d+\.\d+)\s+([A-Z][A-Z ,\-–’\'/()&]+)$',l)
        p=re.match(r'^PART (\d+)\s+([A-Z][A-Z ,\-–’\'/()&]+)$',l)
        key=None
        if m: key=('ART',m.group(1),int(m.group(2)));title=l
        elif g: key=('GC',g.group(1));title=l
        elif p: heads[('PART',int(p.group(1)))]=l; continue
        if key:
            lead=[];cont=True
            for x in L[i+1:i+40]:
                if PARA.match(x) or re.match(r'^(ARTICLE|GC|PART) ',x): break
                if not x: cont=False; continue
                if cont and x.upper()==x and re.search(r'[A-Z]',x): title+=' '+x; continue
                cont=False; lead.append(x)
            heads[key]=(title,' '.join(lead))
    appx={}
    if app<len(L):
        intro=' '.join(x for x in L[app:app+6] if x and not x.startswith('AMENDMENTS'))
        intro=intro.split('AMENDMENTS TO THE AGREEMENT')[0].strip()
        for l in L[app:]:
            m=re.match(r'^\d+\.\s+GC (\d+\.\d+)\s+(.+)$',l)
            if m: appx[m.group(1)]=l
        appx['_intro']=intro
    return defs,heads,appx
rows=list(csv.DictReader(open(f'{BASE}/CCDC_ai_input_Clauses.csv',encoding='utf-8-sig')))
os.makedirs(f'{BASE}/definitions',exist_ok=True)
cache={};missing=[]
for f in PDF:
    d,h,a=build(f); cache[f]=(h,a)
    open(f"{BASE}/definitions/{f.replace(' ','_')}_definitions.txt",'w').write(d+'\n')
    print(f,'definitions chars',len(d),'| headings',len(h),'| appendix items',len(a))
out=[]
for r in rows:
    h,a=cache[r['form']]; cid=r['clause_id'].strip()
    part='';parent='';lead='';apx=''
    m=re.match(r'^([A-C])-?(\d+)\.\d+$',cid); g=re.match(r'^GC (\d+)\.(\d+)\.\d+(-A)?$',cid)
    if m:
        k=('ART',m.group(1),int(m.group(2)))
        if k in h: parent,lead=h[k]
    elif g:
        k=('GC',f'{g.group(1)}.{g.group(2)}'); part=h.get(('PART',int(g.group(1))),'')
        if k in h: parent,lead=h[k]
        if g.group(3):
            apx=(a.get('_intro','')+' | '+a.get(k[1],'')).strip(' |')
    if not parent and apx and g and a.get(f'{g.group(1)}.{g.group(2)}'): parent=a[f'{g.group(1)}.{g.group(2)}']
    if not parent: missing.append((r['form'],cid))
    out.append({**r,'part_heading':part,'parent_heading':parent,'parent_leadin':lead,'appendix_context':apx})
cols=['row_id','form','clause_id','section','part_heading','parent_heading','parent_leadin','appendix_context','clause_text']
with open(f'{BASE}/CCDC_ai_input_Clauses_with_context.csv','w',newline='',encoding='utf-8-sig') as fh:
    w=csv.DictWriter(fh,fieldnames=cols); w.writeheader(); w.writerows(out)
print('rows',len(out),'missing parent',len(missing),missing[:15])
print('with leadin',sum(1 for x in out if x['parent_leadin']),'appendix rows',sum(1 for x in out if x['appendix_context']))
