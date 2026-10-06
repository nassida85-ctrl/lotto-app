import json, math, urllib.request, os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

DATA='https://smok95.github.io/lotto/results/all.json'

def u32(x): return x & 0xffffffff
class R:
    def __init__(self,a): self.a=u32(a)
    def random(self):
        self.a=u32(self.a+0x6D2B79F5); t=self.a
        t=u32((t^(t>>15))*(t|1)); t=u32(t ^ u32(t + u32((t^(t>>7))*(t|61))))
        return u32(t^(t>>14))/4294967296.0

def mm(d):
    v=list(d.values()); lo=min(v); hi=max(v)
    return {k:(.5 if hi==lo else (x-lo)/(hi-lo)) for k,x in d.items()}

def pct(a,p):
    a=sorted(a); i=(len(a)-1)*p; l=int(i); h=math.ceil(i)
    return a[l] if l==h else a[l]*(h-i)+a[h]*(i-l)

def prep(hist):
    latest=hist[-1]['draw_no']; windows=(10,20,50,100)
    cnts={w:Counter() for w in windows}; allc=Counter(); last={n:0 for n in range(1,46)}; pairs=Counter(); triples=Counter()
    for d in hist:
        allc.update(d['numbers'])
        for n in d['numbers']: last[n]=d['draw_no']
    for w in windows:
        for d in hist[-w:]: cnts[w].update(d['numbers'])
    for d in hist[-150:]:
        ns=d['numbers']
        for i in range(6):
            for j in range(i+1,6): pairs[(ns[i],ns[j])]+=1
    # pattern distributions from recent history
    pat=Counter()
    sums=[]
    for d in hist[-300:]:
        ns=d['numbers']; sums.append(sum(ns)); odd=sum(n%2 for n in ns); low=sum(n<=22 for n in ns); con=sum(ns[i]==ns[i-1]+1 for i in range(1,6)); dec=len(set((n-1)//10 for n in ns))
        pat[(odd,low,con,dec)] += 1
    gap={n:latest-last[n] for n in range(1,46)}
    A=mm({n:allc[n] for n in range(1,46)}); G=mm(gap); W={w:mm({n:cnts[w][n] for n in range(1,46)}) for w in windows}
    nscore={}
    for n in range(1,46):
        nscore[n]=.10*A[n]+.18*W[10][n]+.20*W[20][n]+.22*W[50][n]+.15*W[100][n]+.15*G[n]
    return latest,nscore,pairs,pat,pct(sums,.08),pct(sums,.92),set(hist[-1]['numbers'])

def wpick(rng,nscore):
    items=list(range(1,46)); out=[]
    for _ in range(6):
        ws=[.18+nscore[n] for n in items]; tot=sum(ws); x=rng.random()*tot; s=0
        for i,w in enumerate(ws):
            s+=w
            if s>=x:
                out.append(items.pop(i)); break
    return tuple(sorted(out))

def score(ns,ctx):
    latest,nscore,pairs,pat,p10,p90,lastset=ctx
    odd=sum(n%2 for n in ns); low=sum(n<=22 for n in ns); sm=sum(ns); con=sum(ns[i]==ns[i-1]+1 for i in range(1,6)); dec=len(set((n-1)//10 for n in ns)); ov=len(set(ns)&lastset)
    s=sum(nscore[n] for n in ns)*1.15
    pv=[]
    for i in range(6):
        for j in range(i+1,6): pv.append(pairs[(ns[i],ns[j])])
    s += (sum(pv)/15.0)*0.055
    s += math.log1p(pat[(odd,low,con,dec)])*.22
    s += .55 if p10<=sm<=p90 else -.45
    s += .25 if ov<=2 else -.25*(ov-2)
    # soft diversity preference
    s += .18*dec
    return s

def one(args):
    draws,i,cands,topk=args; hist=draws[:i]; actual=tuple(draws[i]['numbers']); aset=set(actual); ctx=prep(hist); rng=R((ctx[0]+1)*1000003+645)
    pool={}; actual_in=False
    for _ in range(cands):
        ns=wpick(rng,ctx[1]);
        if ns==actual: actual_in=True
        if ns not in pool: pool[ns]=score(ns,ctx)
    ranked=sorted(pool.items(),key=lambda x:x[1],reverse=True)
    chosen=[]
    for ns,sc in ranked:
        if all(len(set(ns)&set(c))<=4 for c in chosen): chosen.append(ns)
        if len(chosen)>=topk: break
    hits=[len(set(x)&aset) for x in chosen]; best=max(hits)
    exact=actual in chosen
    return {'draw':draws[i]['draw_no'],'best':best,'exact':exact,'pool_exact':actual_in,'actual':list(actual),'pick':list(chosen[hits.index(best)])}

def main():
    req=urllib.request.Request(DATA,headers={'User-Agent':'Mozilla/5.0'}); draws=json.load(urllib.request.urlopen(req,timeout=30)); draws=sorted(draws,key=lambda d:d['draw_no'])
    start=100; cands=80000; topk=20
    tasks=[(draws,i,cands,topk) for i in range(start,len(draws))]
    workers=max(2,min(8,(os.cpu_count() or 4)))
    with ProcessPoolExecutor(max_workers=workers) as ex: rows=list(ex.map(one,tasks,chunksize=1))
    dist=Counter(r['best'] for r in rows); exact=[r for r in rows if r['exact']]; pool=[r for r in rows if r['pool_exact']]
    out={'version':'V2-deep','tested_draws':len(rows),'start_draw':draws[start]['draw_no'],'end_draw':draws[-1]['draw_no'],'candidates_per_draw':cands,'top_games_per_draw':topk,'candidate_pool_exact_count':len(pool),'top20_first_prize_count':len(exact),'best_match_distribution':{str(k):dist[k] for k in range(7)},'first_prize_cases':exact,'pool_exact_draws':[r['draw'] for r in pool],'four_plus_cases':[r for r in rows if r['best']>=4],'method':'Strict walk-forward. Target draw excluded. Rich recent-window, gap, pair and pattern scoring. 80k weighted candidates; top 20 diversified.'}
    with open('backtest-v2-result.json','w',encoding='utf-8') as f: json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:out[k] for k in ['tested_draws','candidate_pool_exact_count','top20_first_prize_count','best_match_distribution']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
