import json, math, urllib.request
from collections import Counter

DATA='https://smok95.github.io/lotto/results/all.json'

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
    items=list(range(1,46)); out=[]
    for _ in range(6):
        ws=[.25+score[n] for n in items]; total=sum(ws); r=rng.random()*total; acc=0; idx=0
        for i,w in enumerate(ws):
            acc+=w
            if acc>=r: idx=i; break
        out.append(items.pop(idx))
    return sorted(out)

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
        ns=tuple(weighted_pick(rng,info['score']))
        if ns not in pool: pool[ns]=combo_score(ns,info)
    ranked=sorted(pool.items(), key=lambda x:x[1], reverse=True); chosen=[]
    for ns,_ in ranked:
        if all(len(set(ns)&set(c))<=3 for c in chosen): chosen.append(ns)
        if len(chosen)>=sets: break
    return chosen

def main():
    req=urllib.request.Request(DATA,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=30) as r: draws=json.load(r)
    draws=sorted(draws,key=lambda d:d['draw_no'])
    # 최소 50회 학습 후 51회부터 최신까지 완전 워크포워드
    dist=Counter(); first=[]; second=[]; best_rows=[]
    for i in range(50,len(draws)):
        hist=draws[:i]; actual=set(draws[i]['numbers']); bonus=draws[i].get('bonus_no')
        picks=recommend(hist)
        hits=[len(set(p)&actual) for p in picks]; best=max(hits); dist[best]+=1
        if best==6: first.append({'draw':draws[i]['draw_no'],'actual':sorted(actual),'picks':[list(p) for p in picks]})
        for p in picks:
            if len(set(p)&actual)==5 and bonus in p: second.append({'draw':draws[i]['draw_no'],'actual':sorted(actual),'bonus':bonus,'pick':list(p)})
        if best>=4: best_rows.append({'draw':draws[i]['draw_no'],'best_match':best,'actual':sorted(actual),'picks':[list(p) for p in picks if len(set(p)&actual)==best]})
    result={
      'data_latest_draw':draws[-1]['draw_no'], 'tested_draws':len(draws)-50, 'start_draw':draws[50]['draw_no'], 'end_draw':draws[-1]['draw_no'],
      'games_per_draw':5,'total_games':(len(draws)-50)*5,'best_match_distribution':{str(k):dist[k] for k in range(7)},
      'first_prize_count':len(first),'first_prize_cases':first,'second_prize_count':len(second),'second_prize_cases':second,
      'cases_best_4plus':best_rows,
      'method':'For each target draw, only earlier draws were used. Exact current recommendation algorithm, deterministic Mulberry32 seed, 35,000 candidates, 5 sets.'
    }
    with open('backtest-result.json','w',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:result[k] for k in ['data_latest_draw','tested_draws','total_games','best_match_distribution','first_prize_count','second_prize_count']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
