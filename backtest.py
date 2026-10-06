import json, math, urllib.request, os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

DATA='https://smok95.github.io/lotto/results/all.json'
DRAWS=None

def u32(x): return x & 0xffffffff
class Mulberry32:
    def __init__(self,a): self.a=u32(a)
    def random(self):
        self.a=u32(self.a+0x6D2B79F5); t=self.a
        t=u32((t ^ (t>>15)) * (t|1))
        t=u32(t ^ u32(t + u32((t ^ (t>>7)) * (t|61))))
        return u32(t ^ (t>>14)) / 4294967296.0

def normmap(m):
    vals=list(m.values()); lo=min(vals); hi=max(vals)
    return {k:(.5 if hi==lo else (v-lo)/(hi-lo)) for k,v in m.items()}

def percentile(arr,p):
    a=sorted(arr); i=(len(a)-1)*p; l=math.floor(i); h=math.ceil(i)
    return a[l] if l==h else a[l]*(h-i)+a[h]*(i-l)

def analyze(draws):
    latest=draws[-1]['draw_no']; allc={n:0 for n in range(1,46)}; r20={n:0 for n in range(1,46)}; r50={n:0 for n in range(1,46)}; last={n:0 for n in range(1,46)}
    for d in draws:
        for n in d['numbers']: allc[n]+=1; last[n]=d['draw_no']
    for d in draws[-20:]:
        for n in d['numbers']: r20[n]+=1
    for d in draws[-50:]:
        for n in d['numbers']: r50[n]+=1
    gap={n:latest-last[n] for n in range(1,46)}
    A,B,C,G=map(normmap,(allc,r20,r50,gap)); score={}
    for n in range(1,46): score[n]=.2*A[n]+.25*B[n]+.3*C[n]+.25*G[n]
    sums=[sum(d['numbers']) for d in draws]
    return {'latest':latest,'score':score,'p10':percentile(sums,.1),'p90':percentile(sums,.9),'lastSet':set(draws[-1]['numbers'])}

def weighted_pick(rng,score):
    items=list(range(1,46)); weights=[.25+score[n] for n in items]; total=sum(weights); out=[]
    for _ in range(6):
        r=rng.random()*total; acc=0; idx=0
        for i,w in enumerate(weights):
            acc+=w
            if acc>=r: idx=i; break
        out.append(items[idx]); total-=weights[idx]; items.pop(idx); weights.pop(idx)
    return tuple(sorted(out))

def combo_score(ns,info):
    odd=sum(n%2 for n in ns); low=sum(n<=22 for n in ns); sm=sum(ns); con=sum(ns[i]==ns[i-1]+1 for i in range(1,6)); dec=len(set((n-1)//10 for n in ns)); ov=sum(n in info['lastSet'] for n in ns)
    s=sum(info['score'][n] for n in ns)/6*5
    s += 1 if 2<=odd<=4 else -.8
    s += .8 if 2<=low<=4 else -.6
    s += 1 if info['p10']<=sm<=info['p90'] else -1
    s += .5 if con<=1 else -.7*con
    s += .6 if dec>=4 else -.5
    s += .4 if ov<=2 else -.6*(ov-2)
    return s

def recommend(draws,candidates=35000,sets=5):
    info=analyze(draws); rng=Mulberry32((info['latest']+1)*1000003+645); pool={}
    for _ in range(candidates):
        ns=weighted_pick(rng,info['score'])
        if ns not in pool: pool[ns]=combo_score(ns,info)
    ranked=sorted(pool.items(), key=lambda x:x[1], reverse=True); chosen=[]
    chosen_sets=[]
    for ns,_ in ranked:
        s=set(ns)
        if all(len(s & cs)<=3 for cs in chosen_sets):
            chosen.append(ns); chosen_sets.append(s)
        if len(chosen)>=sets: break
    return chosen

def init_worker(draws):
    global DRAWS; DRAWS=draws

def test_one(i):
    hist=DRAWS[:i]; actual=set(DRAWS[i]['numbers']); bonus=DRAWS[i].get('bonus_no')
    picks=recommend(hist); hits=[len(set(p)&actual) for p in picks]; best=max(hits)
    row={'draw':DRAWS[i]['draw_no'],'best':best}
    if best>=4: row.update({'actual':sorted(actual),'picks':[list(p) for p in picks if len(set(p)&actual)==best]})
    seconds=[]
    for p in picks:
        if len(set(p)&actual)==5 and bonus in p: seconds.append({'draw':DRAWS[i]['draw_no'],'actual':sorted(actual),'bonus':bonus,'pick':list(p)})
    first=None
    if best==6: first={'draw':DRAWS[i]['draw_no'],'actual':sorted(actual),'picks':[list(p) for p in picks]}
    return row,first,seconds

def main():
    req=urllib.request.Request(DATA,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=30) as r: draws=json.load(r)
    draws=sorted(draws,key=lambda d:d['draw_no'])
    indices=list(range(50,len(draws)))
    workers=max(2,min(4,os.cpu_count() or 2))
    with ProcessPoolExecutor(max_workers=workers,initializer=init_worker,initargs=(draws,)) as ex:
        rows=list(ex.map(test_one,indices,chunksize=8))
    dist=Counter(); first=[]; second=[]; best_rows=[]
    for row,f,s2 in rows:
        dist[row['best']]+=1
        if row['best']>=4: best_rows.append(row)
        if f: first.append(f)
        second.extend(s2)
    result={
      'data_latest_draw':draws[-1]['draw_no'], 'tested_draws':len(indices), 'start_draw':draws[50]['draw_no'], 'end_draw':draws[-1]['draw_no'],
      'games_per_draw':5,'total_games':len(indices)*5,'best_match_distribution':{str(k):dist[k] for k in range(7)},
      'first_prize_count':len(first),'first_prize_cases':first,'second_prize_count':len(second),'second_prize_cases':second,
      'cases_best_4plus':best_rows,
      'method':'Strict walk-forward: each target draw used only earlier draws. Exact recommendation logic, deterministic Mulberry32 seed, 35,000 candidates, 5 sets. Parallelized only across independent target draws.'
    }
    with open('backtest-result.json','w',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:result[k] for k in ['data_latest_draw','tested_draws','total_games','best_match_distribution','first_prize_count','second_prize_count']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
