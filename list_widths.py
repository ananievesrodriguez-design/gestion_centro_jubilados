import glob
import re

pat = re.compile(r"max-width:[^;]*;")
seen = {}
for f in sorted(glob.glob("templates/*.html")):
    with open(f, encoding="utf-8") as fh:
        txt = fh.read()
    for m in pat.finditer(txt):
        v = m.group(0)
        seen[v] = seen.get(v, 0) + 1

for k, c in sorted(seen.items()):
    print(c, "|", k)
