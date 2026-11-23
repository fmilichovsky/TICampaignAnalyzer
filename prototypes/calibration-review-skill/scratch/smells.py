from theme import prep, THEME_NARR, LEVELS
import collections, statistics
from datetime import date
def d(s): return date(int(s[:4]),int(s[5:7]),int(s[8:10]))
for c in ['protectorate','resist-long']:
    ev,byid,cb=prep(c)
    top=[e for e in ev if e['tier']=='narrative' and e['ptier']=='top']
    print("=====",c)
    # flood: per year per level, one type >=50% and level>=6 (top-level narrative)
    for y in sorted(set(e['year'] for e in top)):
        for l in LEVELS[:3]:
            rows=[e for e in top if e['year']==y and e['level']==l]
            if len(rows)<6: continue
            t,n=collections.Counter(e['type'] for e in rows).most_common(1)[0]
            if n*2>=len(rows) and t in THEME_NARR: print(f"FLOOD {y} {l}: {t} {n}/{len(rows)}")
    # inverted pyramid (all types, top-level)
    for y in sorted(set(e['year'] for e in top)):
        cnt=collections.Counter(e['level'] for e in top if e['year']==y)
        for hi,lo in [("campaign_defining","major"),("major","minor")]:
            if cnt[hi]>cnt[lo] and cnt[hi]>=6: print(f"INVERTED {y} {hi} {cnt[hi]} > {lo} {cnt[lo]}")
    # repeats: theme types, same type, same entity set, major+, within 24 months
    for t in THEME_NARR:
        rows=[e for e in top if e['type']==t and e['level'] in LEVELS[:2]]
        groups=collections.defaultdict(list)
        for e in rows:
            for en in e['entities']:
                if en['id'].startswith('nation') or en['id'].startswith('federation'): groups[(en['name'])].append(e)
        for k,g in groups.items():
            g.sort(key=lambda e:e['interval'])
            for i in range(len(g)-2):
                if (d(g[i+2]['interval'])-d(g[i]['interval'])).days<=730:
                    print(f"REPEATS {t} on {k}: {len(g)} events, e.g. {[x['interval'][:7] for x in g]}"); break
    # flat scores per theme kind
    for t in THEME_NARR:
        s=sorted(e['score'] for e in ev if e['type']==t)
        if len(s)>=10:
            q=statistics.quantiles(s,n=10)
            span=q[-1]-q[0]
            print(f"SCORES {t}: n={len(s)} p10={q[0]:.0f} p90={q[-1]:.0f} span={span:.0f} distinct={sorted(set(s))[:12]}{' FLAT' if span<=5 else ''}")
