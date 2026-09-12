#!/usr/bin/env python3
"""Summarise collected reviews per case. Stdlib only.

    python tools/reviews_report.py reviews.jsonl            # from the collector (curl ... > reviews.jsonl)
    python tools/reviews_report.py gallop-reviews.json      # from a reviewer's "Export all reviews"
    python tools/reviews_report.py a.jsonl b.json ...       # several files, deduplicated by reviewer+case+date

Prints, per case: number of reviews, mean R1 realism (1-5), sign-off tally,
the answers that were not "Yes", and every "what would you change".
"""
import json
import sys
from collections import defaultdict


def load(path):
    text = open(path, encoding="utf-8").read().strip()
    if not text:
        return []
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main(paths):
    seen, rows = set(), []
    for p in paths:
        for r in load(p):
            key = (r.get("reviewer"), r.get("case_id"), r.get("date"))
            if key in seen:
                continue
            seen.add(key)
            rows.append(r)
    by_case = defaultdict(list)
    for r in rows:
        by_case[r.get("case_id", "?")].append(r)
    print(f"{len(rows)} reviews, {len(by_case)} cases, {len({r.get('reviewer') for r in rows})} reviewers\n")
    for cid in sorted(by_case):
        rs = by_case[cid]
        r1 = [int(str(r["answers"].get("R1", ""))[:1]) for r in rs if str(r["answers"].get("R1", ""))[:1].isdigit()]
        signoff = defaultdict(int)
        for r in rs:
            signoff[r["answers"].get("R10") or "no answer"] += 1
        print(f"== {cid}  ({len(rs)} review{'s' if len(rs) != 1 else ''}; realism {sum(r1) / len(r1):.1f}/5 over {len(r1)})" if r1 else f"== {cid}  ({len(rs)} reviews)")
        print("   sign-off: " + ", ".join(f"{k} x{v}" for k, v in sorted(signoff.items())))
        for r in rs:
            flags = [f"{q}={a}" for q, a in r["answers"].items() if a and not q.endswith("_note") and a not in ("Yes", "About right", "Not applicable", "Sign off as is") and not q == "R1"]
            notes = [f"{q}: {a}" for q, a in r["answers"].items() if q.endswith("_note") and a]
            who = f"{r.get('reviewer') or 'anonymous'}{' (' + r['role'] + ')' if r.get('role') else ''}, {str(r.get('date', ''))[:10]}"
            if flags or notes or r.get("change"):
                print(f"   - {who}")
                if flags:
                    print("       flags: " + "; ".join(flags))
                for n in notes:
                    print("       " + n)
                if r.get("change"):
                    print("       change: " + r["change"])
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
