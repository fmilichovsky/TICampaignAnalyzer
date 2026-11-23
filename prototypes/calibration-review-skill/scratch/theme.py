from load import load
import collections, sys
THEME_NARR = ["federation.lifecycle","nation.merger","nation.expansion","nation.claims_declared","nation.release","nation.cession","nation.breakaway"]
LEVELS=["campaign_defining","major","minor","trivial"]
def prep(c):
    ev=load(c)['events']
    byid={e['id']:e for e in ev}
    cited_by=collections.defaultdict(list)
    for e in ev:
        if e['tier']=='narrative':
            for x in e['cited']: cited_by[x].append(e['id'])
    for e in ev:
        parents=[p for p in cited_by.get(e['id'],[]) if byid[p]['tier']=='narrative']
        if e['tier']=='narrative':
            e['ptier']='member' if parents else 'top'
        else:
            e['ptier']='cited' if parents else 'below'
        e['year']=e['interval'][:4]
    return ev,byid,cited_by
if __name__=="__main__":
    for c in ['protectorate','resist-long']:
        ev,byid,cb=prep(c)
        print("=====",c)
        # theme view: per type base, counts per level x tier
        for t in THEME_NARR:
            rows=[e for e in ev if e['type']==t]
            if not rows: print(t,"none"); continue
            bases=collections.Counter(e['base'] for e in rows)
            cnt=collections.Counter((e['level'],e['ptier']) for e in rows)
            print(f"{t:28} n={len(rows):3} bases={dict(bases)} rules={dict(collections.Counter(e['rule'] for e in rows))}")
            print("    ", {f"{l[:3]}/{p}":v for (l,p),v in sorted(cnt.items())})
        # per year top-level at major+
        years=sorted(set(e['year'] for e in ev))
        print("year  theme-top major+ | all-top major+ | theme share")
        for y in years:
            th=sum(1 for e in ev if e['year']==y and e['type'] in THEME_NARR and e['ptier']=='top' and e['level'] in LEVELS[:2])
            al=sum(1 for e in ev if e['year']==y and e['tier']=='narrative' and e['ptier']=='top' and e['level'] in LEVELS[:2])
            print(y, th, al)
