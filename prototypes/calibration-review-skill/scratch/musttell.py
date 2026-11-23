from theme import prep, LEVELS
from datetime import date, timedelta
import collections
def d(s): return date(int(s[:4]),int(s[5:7]),int(s[8:10]))
CUT=date(2043,3,16)
ENTRIES=[
 (8,"Resistance takes the rump EU and the UK","2028-02-01","2029-08-31",["European Union","United Kingdom"]),
 (9,"The bloc reunifies Europe by force","2029-08-01","2035-05-31",["European Union"]),
 (10,"Türkiye is annexed into Europe","2033-08-01","2033-11-30",["Türkiye"]),
 (13,"Akhand Bharat forms","2033-08-01","2034-11-30",["Akhand Bharat","Pakistan"]),
 (15,"China and Taiwan unify under Taipei","2033-11-01","2034-01-31",["Taiwan","Republic of China"]),
 (16,"The Caliphate is born, takes Saudi Arabia, claims the Muslim world","2033-06-01","2034-11-30",["Caliphate","Saudi Arabia"]),
 (20,"Caliphate across North Africa; Pakistan and Iran merge in","2037-05-01","2039-09-30",["Caliphate","Pakistan","Iran","Egypt","Morocco"]),
 (21,"India absorbs Bangladesh, Nepal, Bhutan","2037-09-01","2039-02-28",["Bangladesh","Nepal","Bhutan"]),
 (22,"Southeast Asia federates, becomes the PAC, then one nation","2037-05-01","2044-02-28",["Southeast Asian Alliance","Pan-Asian Combine"]),
 (26,"The grand federation: Caliphate and Russia with the EU","2041-05-01","2044-06-30",["European Union","Eurasian Union"]),
 (27,"The African Union","2041-10-01","2046-10-31",["African Union"]),
 (28,"England restored and claims the Commonwealth","2041-10-01","2043-03-31",["England"]),
]
M=timedelta(days=91)
ev,byid,cb=prep('resist-long')
narr=[e for e in ev if e['tier']=='narrative']
for n,title,a,b,conc in ENTRIES:
    a,b=d(a),min(d(b),CUT)
    cands=[]
    for e in narr:
        s=d(e['interval']); t=d(e['date']) if e['date'] else s
        if s>t: s,t=t,s
        if t+M<a or s-M>b: continue
        names={x['name'] for x in e['entities']}
        lab=e['label']
        if any(c in names or c in lab for c in conc): cands.append(e)
    top=[e for e in cands if e['ptier']=='top']
    mj=[e for e in top if e['level'] in LEVELS[:2]]
    print(f"\n## {n} {title}  [{a}..{b}]  candidates: top {len(top)} (major+ {len(mj)}), member {len(cands)-len(top)}")
    print("   types (top major+):",dict(collections.Counter(e['type'] for e in mj)))
    for e in sorted(top,key=lambda e:-e['score'])[:14]:
        print(f"   {e['level'][:3]} {e['score']} {e['interval'][:7]}..{(e['date'] or '')[:7]} {e['type']}: {e['label'][:120]}")
