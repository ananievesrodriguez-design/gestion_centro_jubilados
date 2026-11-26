import glob

changed = []
for f in sorted(glob.glob("templates/*.html")):
    with open(f, encoding="utf-8") as fh:
        txt = fh.read()
    new = txt.replace("max-width: min(150px, 100%);", "max-width: 150px;")
    if new != txt:
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(new)
        changed.append(f)

print("logo restaurado en:", changed)
