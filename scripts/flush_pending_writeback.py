#!/usr/bin/env python3
"""Flush pending writeback records into the self-healing brain SQLite DB.

Reads brain/pending_writeback.json and inserts BRAIN_WRITEBACK_PENDING records
into the `learnings` table (dedup on experiment_id == record_id). Flips each
flushed record's status to FLUSHED and rewrites the JSON atomically (write temp
then replace). Idempotent: running twice never inserts duplicate rows.
"""
import json
import sqlite3
import sys
from pathlib import Path

WRITEBACK_JSON = Path(r"C:\Trading\DE40-Research\brain\pending_writeback.json")
DB_PATH = Path(r"C:\Trading\Knowledge-Graph\database\self_healing_brain.db")

PENDING = "BRAIN_WRITEBACK_PENDING"
FLUSHED = "FLUSHED"

_INSERT_SQL = """
INSERT INTO learnings
    (timestamp, symbol, family, trigger, verdict, lesson, next_exp,
     author, tags, status, scope, category, experiment_id)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def build_params(rec):
    """Map one writeback record to the learnings column values."""
    rec_type = rec.get("type", "")
    family = rec.get("family", "")
    confidence = rec.get("confidence", "")
    title = rec.get("title", "")

    lesson = (
        f"{title} | confidence={confidence} "
        f"| DEV={rec.get('dev_evidence')} | VAL={rec.get('val_evidence')}"
    )
    hypotheses = rec.get("hypotheses") or []
    next_exp = "; ".join(str(h) for h in hypotheses)
    tags = ",".join([str(family), str(rec_type), str(confidence)])

    if rec_type == "failure_family":
        category = "FAILURE_FAMILY"
    elif rec_type == "hypothesis":
        category = "HYPOTHESIS"
    else:
        category = "LESSON"

    return (
        str(rec.get("generated_utc", "")),   # timestamp
        str(rec.get("symbol", "")),          # symbol
        str(family),                         # family
        rec_type.upper(),                    # trigger
        "BRAIN_WRITEBACK",                   # verdict
        lesson,                              # lesson
        next_exp,                            # next_exp
        "de40-campaign",                     # author
        tags,                                # tags
        "BRAIN_WRITEBACK",                   # status
        "SELF_HEALING",                      # scope
        category,                            # category
        str(rec.get("record_id", "")),       # experiment_id
    )


def flush(json_path, db_path):
    """Flush pending records; returns a list of (record_id, action) tuples."""
    data = json.loads(json_path.read_text(encoding="utf-8-sig"))
    records = data.get("records", [])

    actions = []
    changed = False
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        for rec in records:
            record_id = rec.get("record_id")
            if rec.get("status") != PENDING:
                actions.append((record_id, "SKIPPED"))
                continue

            existing = cur.execute(
                "SELECT id FROM learnings WHERE experiment_id = ?", (record_id,)
            ).fetchone()
            if existing:
                rec["status"] = FLUSHED
                changed = True
                actions.append((record_id, "ALREADY_PRESENT"))
                continue

            cur.execute(_INSERT_SQL, build_params(rec))
            rec["status"] = FLUSHED
            changed = True
            actions.append((record_id, "INSERTED"))
        conn.commit()
    finally:
        conn.close()

    if changed:
        tmp = json_path.with_name(json_path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(json_path)

    return actions


def main():
    for record_id, action in flush(WRITEBACK_JSON, DB_PATH):
        print(f"{record_id} -> {action}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (FileNotFoundError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)