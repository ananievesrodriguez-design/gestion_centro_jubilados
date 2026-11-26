f = "templates/listar_caja.html"
txt = open(f, encoding="utf-8").read()
i = txt.find("min(")
ctx = txt[i : i + 20]
needle = "min(900, 100);"
sub = txt[i : i + len(needle)]
print("sub:", repr(sub))
print("needle:", repr(needle))
print("equal:", sub == needle)
print("codes sub:", [ord(c) for c in sub])
print("codes needle:", [ord(c) for c in needle])
