import json,sys,collections
def load(c):
    s=open(f"build/calibration/tables/{c}.js").read()
    i=s.index("= ")+2
    return json.loads(s[i:].rstrip().rstrip(";"))
