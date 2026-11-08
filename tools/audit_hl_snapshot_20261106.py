import json,os,collections,datetime as dt
p=os.path.expanduser('~/institutional-flow/history/market.jsonl')
n=bad=0;first=last=prev=None;gaps=[]
st=collections.defaultdict(lambda:{'r':0,'f':0,'o':0,'v':0,'fv':collections.Counter()})
for line in open(p):
    try:d=json.loads(line)
    except Exception:bad+=1;continue
    n+=1;t=d.get('timestamp')
    if t is None:continue
    t=t/1000 if t>1e11 else t
    first=first or t
    if prev is not None:gaps.append(t-prev)
    prev=last=t
    for c,v in (d.get('coins') or {}).items():
        s=st[c];s['r']+=1;f=v.get('funding')
        if f is not None:s['f']+=1;s['fv'][round(f,8)]+=1
        if v.get('open_interest'):s['o']+=1
        if (v.get('trades') or {}).get('data_valid'):s['v']+=1
fmt=lambda x:dt.datetime.utcfromtimestamp(x).strftime('%Y-%m-%d %H:%M')
print('rows',n,'bad',bad,'from',fmt(first),'to',fmt(last))
g=sorted(gaps);print('median gap sec',g[len(g)//2],'gaps>1h',sum(1 for x in g if x>3600))
for c,s in st.items():
    top=s['fv'].most_common(1)[0] if s['fv'] else None
    print(c,'rows',s['r'],'funding%',round(100*s['f']/s['r'],1),'oi%',round(100*s['o']/s['r'],1),'distinct_funding',len(s['fv']),'top',top,'valid_trades%',round(100*s['v']/s['r'],1))
