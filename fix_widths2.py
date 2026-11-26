import glob
import re

pat = re.compile(r"min\((\d+), 100%\)")
changed = []

for f in sorted(glob.glob("templates/*.html")):
    with open(f, encoding="utf-8") as fh:
        txt = fh.read()
    new = pat.sub(lambda m: "min(" + m.group(1) + "px, 100%)", txt)
    if new != txt:
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(new)
        changed.append(f)

print("corregidos:", changed)

for f in sorted(glob.glob("templates/*.html")):
    with open(f, encoding="utf-8") as fh:
        txt = fh.read()
    new = txt.replace("max-width: min(150, 100%)", "max-width: 150px")
    if new != txt:
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(new)
        changed.append(f)

print("total archivos modificados:", len(changed))
