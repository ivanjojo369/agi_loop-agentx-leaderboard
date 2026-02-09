import json
from pathlib import Path

p = Path(r"C:\Users\PC\Documents\AGI-Prototipo\agi_loop-agentx-leaderboard\results\ivanjojo369-20260209-141503.json")
d = json.loads(p.read_text(encoding="utf-8"))

outer = d.get("results", []) or []
flat = []
for x in outer:
    if isinstance(x, dict) and isinstance(x.get("results"), list):
        flat.extend(x["results"])
    elif isinstance(x, dict):
        flat.append(x)

d["results"] = flat
p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

print("Wrote:", p)
print("Flattened results.len =", len(flat))
print("Bytes =", p.stat().st_size)
