#!/usr/bin/env python3
"""Validate MT5 .set files against an EA's declared inputs.

Usage:
    python set_contract_check.py <ea_mq5_path> <set_dir> [baseline_set_name]

* Parses every `input <type> NAME = ...` declaration from the MQL5 source
  (regex over the whole file, MULTILINE) and keeps identifiers containing 'Inp'.
  `input group "..."` lines have a quoted string — not an identifier — so they
  are never collected.
* For each `<set_dir>/*.set`, splits `Name=Value` lines (stopping at the first
  `||` swept-form separator) to obtain the requested names. Any requested name
  the EA does not declare is recorded as unsupported.
* Computes a strategy-affecting sha256 fingerprint over the sorted (name, value)
  pairs, excluding the ledger/account separators
  {InpMagic, InpLots, InpColdStartSec, InpSymbolOverride}.
* Flags DUPLICATE sets (a fingerprint shared by 2+ sets) and NO_EFFECTIVE_CHANGE
  when a set's fingerprint equals the baseline set's fingerprint (when given).
* Writes <set_dir>/../evidence/set_contract_check.json.

Exit code: 0 = no unsupported inputs and no duplicates; 1 = otherwise;
           2 = usage or I/O error.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

# Ledger/account separators: changing these does not change what the strategy
# actually trades, so they are excluded from the effective fingerprint.
EXCLUSION = {"InpMagic", "InpLots", "InpColdStartSec", "InpSymbolOverride"}

# `input <type> NAME =`. `input group "..."` is skipped because the position of
# the NAME is occupied by a string literal, not an identifier.
_INPUT_RE = re.compile(r"\binput\s+[A-Za-z_]\w*\s+([A-Za-z_]\w*)\s*=")


def parse_ea_inputs(text):
    """Return the set of input identifiers containing 'Inp' declared by the EA."""
    names = set()
    for match in _INPUT_RE.finditer(text):
        name = match.group(1)
        if "Inp" in name:
            names.add(name)
    return names


def parse_set(text):
    """Parse one .set body into a {name: value} dict of requested inputs."""
    requested = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        eq = line.find("=")
        if eq == -1:
            continue
        name = line[:eq].strip()
        value = line[eq + 1:]
        if "||" in value:  # swept form Name=Value||start||step||stop||Y
            value = value.split("||", 1)[0]
        if name:
            requested[name] = value.strip()
    return requested


def effective_fingerprint(requested):
    """sha256 over the sorted strategy-affecting (name, value) pairs."""
    pairs = [(n, requested[n]) for n in sorted(requested) if n not in EXCLUSION]
    payload = ";".join(f"{n}={v}" for n, v in pairs)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main(argv):
    if len(argv) < 3:
        print(
            "usage: set_contract_check.py <ea_mq5_path> <set_dir> [baseline_set_name]",
            file=sys.stderr,
        )
        return 2

    ea_path = Path(argv[1])
    set_dir = Path(argv[2])
    baseline_name = argv[3] if len(argv) > 3 else None

    supported = parse_ea_inputs(
        ea_path.read_text(encoding="utf-8-sig", errors="replace")
    )

    set_files = sorted(set_dir.glob("*.set"))
    if not set_files:
        print(f"no .set files found in {set_dir}", file=sys.stderr)
        return 2

    entries = []
    for f in set_files:
        requested = parse_set(f.read_text(encoding="utf-8-sig", errors="replace"))
        unsupported = sorted(n for n in requested if n not in supported)
        entries.append({
            "name": f.stem,
            "supported_inputs_count": len(requested) - len(unsupported),
            "unsupported": unsupported,
            "fingerprint": effective_fingerprint(requested),
        })

    # Optional baseline reference fingerprint.
    baseline_fp = None
    if baseline_name:
        for e in entries:
            if e["name"] == baseline_name:
                baseline_fp = e["fingerprint"]
                break
        if baseline_fp is None:
            print(
                f"warning: baseline set '{baseline_name}' not found in {set_dir}",
                file=sys.stderr,
            )

    # Duplicate detection: every fingerprint shared by 2+ sets marks them all.
    by_fp = {}
    for e in entries:
        by_fp.setdefault(e["fingerprint"], []).append(e)

    duplicates = {}
    for group in by_fp.values():
        if len(group) < 2:
            continue
        for e in group:
            other = next(g["name"] for g in group if g["name"] != e["name"])
            duplicates[e["name"]] = other

    has_unsupported = False
    has_duplicate = bool(duplicates)
    results = []
    for e in entries:
        if e["unsupported"]:
            has_unsupported = True
        entry = {
            "set": e["name"],
            "supported_inputs_count": e["supported_inputs_count"],
            "unsupported": e["unsupported"],
            "fingerprint": e["fingerprint"],
        }
        if e["name"] in duplicates:
            entry["duplicate_of"] = duplicates[e["name"]]
        no_op = (
            baseline_fp is not None
            and e["name"] != baseline_name
            and e["fingerprint"] == baseline_fp
        )
        if no_op:
            entry["no_op"] = True
        results.append(entry)

        flags = []
        if e["unsupported"]:
            flags.append("unsupported=" + ",".join(e["unsupported"]))
        if no_op:
            flags.append("NO_EFFECTIVE_CHANGE")
        if e["name"] in duplicates:
            flags.append("duplicate_of=" + duplicates[e["name"]])
        verdict = "FAIL " + " ".join(flags) if flags else "OK"
        print(f"{e['name']}: {verdict}")

    out_dir = set_dir.parent / "evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "set_contract_check.json"
    payload = {
        "ea": str(ea_path),
        "set_dir": str(set_dir),
        "baseline": baseline_name,
        "sets": results,
    }
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(out_path)

    return 1 if (has_unsupported or has_duplicate) else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)