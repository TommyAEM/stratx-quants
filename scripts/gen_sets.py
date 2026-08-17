#!/usr/bin/env python3
"""Generate MT5 .set files from a JSON grid spec.

Usage: gen_sets.py <spec.json> <out_dir> <prefix>

spec.json format:
{
  "fixed": {"InpServerUTC": 3},
  "params": {
     "InpSlAtrMult": {"type": "double", "values": [1.5, 2.0, 2.5, 3.0]},
     "InpLookback":  {"type": "int",    "values": [40, 60, 80]},
     "InpUseTrendGate": {"type": "bool", "values": [true, false]}
  },
  "mode": "grid" | "sobol" | "lhs",
  "sobol_n": 32
}

grid = full cartesian; sobol/lhs = sampled combos over the value lists
(interpreted as bounds [min..max] with n samples; numeric params only,
bools fixed in 'fixed').
Writes <out_dir>/<prefix>_NNN.set with fixed + sampled params, one per line
'name=value'. Prints the manifest JSON (config_id -> params) to stdout.
"""
import json
import sys
from itertools import product
from pathlib import Path


def _fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v)
    return str(v)


def sobol_samples(bounds, n, seed=7):
    try:
        from scipy.stats import qmc
        s = qmc.Sobol(d=len(bounds), scramble=True, seed=seed)
        u = s.random(n)
    except Exception:
        import random
        random.seed(seed)
        u = [[random.random() for _ in bounds] for _ in range(n)]
    out = []
    for row in u:
        pt = {}
        for (name, lo, hi, typ), x in zip(bounds, row):
            v = lo + (hi - lo) * x
            pt[name] = int(round(v)) if typ == "int" else round(v, 6)
        out.append(pt)
    return out


def main(argv):
    spec = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    out_dir = Path(argv[2])
    prefix = argv[3]
    out_dir.mkdir(parents=True, exist_ok=True)
    fixed = spec.get("fixed", {})
    params = spec.get("params", {})
    mode = spec.get("mode", "grid")

    combos = []
    if mode == "grid":
        names = list(params)
        for vals in product(*[params[k]["values"] for k in names]):
            combos.append(dict(zip(names, vals)))
    else:
        bounds = []
        for k, d in params.items():
            vs = d["values"]
            bounds.append((k, min(vs), max(vs), d.get("type", "double")))
        combos = sobol_samples(bounds, spec.get("sobol_n", 32))

    manifest = {}
    for i, combo in enumerate(combos, 1):
        cid = f"{prefix}_{i:03d}"
        lines = [f"{k}={_fmt(v)}" for k, v in fixed.items()]
        lines += [f"{k}={_fmt(v)}" for k, v in combo.items()]
        (out_dir / f"{cid}.set").write_text("\n".join(lines) + "\n", encoding="utf-8")
        manifest[cid] = {**fixed, **combo}
    print(json.dumps({"mode": mode, "count": len(manifest), "manifest": manifest}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
