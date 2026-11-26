import glob

nums = ["680", "720", "760", "800", "820", "900", "960", "980"]
changed_files = []

for f in glob.glob("templates/*.html"):
    with open(f, encoding="utf-8") as fh:
        txt = fh.read()
    new = txt
    for num in nums:
        new = new.replace("min(" + num + ", 100);", "min(" + num + "px, 100);")
    new = new.replace("max-width: min(150, 100);", "max-width: 150px;")
    if new != txt:
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(new)
        changed_files.append(f)

print("archivos corregidos:", changed_files)
