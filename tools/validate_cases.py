#!/usr/bin/env python3
"""Schema check for site/data/cases.json. Stdlib only. Exit 1 on any failure.

    python tools/validate_cases.py            # schema, provenance, ranges, files, field geometry
    python tools/validate_cases.py --weight   # also total site/ bytes against the 2 MB Phase 1 cap

Field maths mirrors index.html (handover section 5.3) so the never-silent and
radiation checks in docs/ACCEPTANCE.md (A3, A4) run here.
"""
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
BOX = (-150, 150, -60, 240)  # x0, x1, y0, y1: head clamp box in mm, same as index.html
PROV = {"synthesized", "recorded_annotated", "recorded_clinician_labelled"}
FINDINGS = {"normal", "s3", "s4", "split_s2", "systolic_murmur", "diastolic_murmur", "click", "rub"}
HEART = {"s1", "s2", "s3", "s4", "murmur", "click", "snap", "rub"}
BOUNDARY = {"boundary_breath", "boundary_bowel"}
PROM = {"faint", "moderate", "pronounced"}
SHAPES = {"crescendo", "decrescendo", "diamond", "plateau"}
PITCH = {"low", "medium", "high"}
QUALITY = {"blowing", "harsh", "musical"}
RADIATION_POINT = {"carotids": (-10, -30), "axilla": (150, 110)}  # handover section 5.5 regions
WEIGHT_CAP = 2_000_000

errors = []


def err(cid, msg):
    errors.append(f"{cid}: {msg}")


def field(sources, x, y):
    best = 0.0
    for s in sources:
        dx, dy = x - s["x"], y - s["y"]
        sx = s["spread"]["l"] if dx < 0 else s["spread"]["r"]
        sy = s["spread"]["u"] if dy < 0 else s["spread"]["d"]
        best = max(best, math.exp(-(dx * dx / (sx * sx) + dy * dy / (sy * sy))))
    return best


def sources_of(layer):
    return layer.get("sources") or ([layer["source"]] if "source" in layer else [])


def check_source(cid, s, where):
    for k in ("x", "y", "spread"):
        if k not in s:
            err(cid, f"{where}: source missing {k}")
            return
    if not (BOX[0] <= s["x"] <= BOX[1] and BOX[2] <= s["y"] <= BOX[3]):
        err(cid, f"{where}: source ({s['x']}, {s['y']}) outside silhouette box {BOX}")
    for d in "lrud":
        if not isinstance(s["spread"].get(d), (int, float)) or s["spread"][d] <= 0:
            err(cid, f"{where}: spread.{d} must be a positive number")


def check_layer(cid, i, L):
    t = L.get("type")
    where = f"layer {i} ({t})"
    if t not in HEART | BOUNDARY:
        err(cid, f"{where}: unknown layer type")
        return
    prov = L.get("provenance") or {}
    if prov.get("class") not in PROV:
        err(cid, f"{where}: provenance.class must be one of {sorted(PROV)}")
    if not prov.get("basis") and not prov.get("dataset"):
        err(cid, f"{where}: provenance needs basis (or dataset for recorded stems)")
    stem = L.get("stem") or {}
    if stem.get("kind") not in {"synth", "recorded"}:
        err(cid, f"{where}: stem.kind must be synth or recorded")
    if not stem.get("file"):
        err(cid, f"{where}: stem.file missing")
    elif not os.path.isfile(os.path.join(SITE, stem["file"])):
        err(cid, f"{where}: stem file not found: site/{stem['file']} (run tools/synth_stems.py)")
    if t in BOUNDARY:
        srcs = L.get("sources")
        if not srcs:
            err(cid, f"{where}: boundary layer needs a non-empty sources list")
            return
        for j, s in enumerate(srcs):
            if not s.get("label"):
                err(cid, f"{where}: sources[{j}] needs a label (shown as the region caption)")
            check_source(cid, s, f"{where} sources[{j}]")
        if L.get("intensity") not in PROM:
            err(cid, f"{where}: intensity must be one of {sorted(PROM)}")
        return
    if "source" not in L:
        err(cid, f"{where}: heart layer needs a source")
    else:
        check_source(cid, L["source"], where)
    if t == "murmur":
        if L.get("phase") not in {"systolic", "diastolic"}:
            err(cid, f"{where}: phase must be systolic or diastolic")
        if not re.match(r"^(early|mid|late|holo)", str(L.get("timing", ""))):
            err(cid, f"{where}: timing must start with early/mid/late/holo")
        if L.get("shape") not in SHAPES:
            err(cid, f"{where}: shape must be one of {sorted(SHAPES)}")
        if L.get("pitch") not in PITCH:
            err(cid, f"{where}: pitch must be one of {sorted(PITCH)}")
        if L.get("quality") not in QUALITY:
            err(cid, f"{where}: quality must be one of {sorted(QUALITY)}")
        g = L.get("grade")
        hi = 6 if L.get("phase") == "systolic" else 4
        if not isinstance(g, int) or not 1 <= g <= hi:
            err(cid, f"{where}: grade must be an integer 1-{hi}")
    else:
        if L.get("intensity") not in PROM:
            err(cid, f"{where}: intensity must be one of {sorted(PROM)}")
        if t == "s2" and not isinstance(L.get("split_ms", 0), (int, float)) or not 0 <= L.get("split_ms", 0) <= 80:
            err(cid, f"{where}: split_ms must be 0-80")


def check_case(c):
    cid = c.get("id", "?")
    for k in ("id", "title", "findings", "answer_key", "clock", "habitus", "layers", "card",
              "quiz_rationales", "tiers", "reviewed_by", "review_date"):
        if k not in c:
            err(cid, f"missing key {k}")
    if errors and errors[-1].startswith(cid + ": missing"):
        return
    if not set(c["findings"]) <= FINDINGS:
        err(cid, f"findings must be a subset of {sorted(FINDINGS)}")
    ak = c["answer_key"]
    if ak.get("primary_finding") not in c["findings"]:
        err(cid, "answer_key.primary_finding must be one of the case findings")
    la = ak.get("loudest_at") or {}
    if not all(k in la for k in ("x", "y", "radius_mm")):
        err(cid, "answer_key.loudest_at needs x, y, radius_mm")
    if ak.get("best_head") not in {"bell", "diaphragm", "either"}:
        err(cid, "answer_key.best_head must be bell, diaphragm or either")
    if not set(ak.get("radiates_to", [])) <= set(RADIATION_POINT):
        err(cid, f"answer_key.radiates_to entries must be in {sorted(RADIATION_POINT)}")
    clk = c["clock"]
    if not 50 <= clk.get("bpm", 0) <= 130:
        err(cid, "clock.bpm must be 50-130")
    if not 200 <= clk.get("systole_ms", 0) <= 400:
        err(cid, "clock.systole_ms out of plausible range (200-400)")
    if not set(c["tiers"]) <= {1, 2, 3, 4} or not c["tiers"]:
        err(cid, "tiers must be a non-empty subset of 1-4")
    if c["reviewed_by"] is not None and not c["review_date"]:
        err(cid, "review_date required when reviewed_by is set")
    for k in ("summary", "why", "why_squared", "sources"):
        if not c["card"].get(k):
            err(cid, f"card.{k} missing")
    if not c["quiz_rationales"].get("identify"):
        err(cid, "quiz_rationales.identify missing")
    layers = c["layers"]
    types = [L.get("type") for L in layers]
    if "s1" not in types or "s2" not in types:
        err(cid, "every case needs s1 and s2 layers")
    if not BOUNDARY <= set(types):
        err(cid, "every case needs boundary_breath and boundary_bowel layers (never-silent rule)")
    for i, L in enumerate(layers):
        check_layer(cid, i, L)
    if errors:
        return
    # A3: never silent anywhere on the silhouette grid
    worst = 1.0
    for x in range(BOX[0], BOX[1] + 1, 10):
        for y in range(BOX[2], BOX[3] + 1, 10):
            worst = min(worst, max(field(sources_of(L), x, y) for L in layers))
    if worst < 0.10:
        err(cid, f"never-silent check: minimum field over the grid is {worst:.3f} (< 0.10)")
    # A4: primary murmur peaks at loudest_at and radiates where the answer key says, and nowhere else
    murmurs = [L for L in layers if L.get("type") == "murmur"]
    if murmurs and ak["primary_finding"].endswith("murmur"):
        m = murmurs[0]
        at = field([m["source"]], la["x"], la["y"])
        if at < 0.9:
            err(cid, f"murmur field at loudest_at is {at:.2f} (< 0.9)")
        for name, (px, py) in RADIATION_POINT.items():
            v = field([m["source"]], px, py)
            if name in ak["radiates_to"] and v < 0.3:
                err(cid, f"murmur should radiate to {name} but field there is {v:.2f} (< 0.3)")
            if name not in ak["radiates_to"] and v > 0.1:
                err(cid, f"murmur should not radiate to {name} but field there is {v:.2f} (> 0.1)")


def weight():
    total = 0
    for d, _, files in os.walk(SITE):
        for f in files:
            total += os.path.getsize(os.path.join(d, f))
    print(f"site/ total: {total:,} bytes (cap {WEIGHT_CAP:,})")
    if total >= WEIGHT_CAP:
        errors.append(f"page weight {total:,} B exceeds cap")


def main():
    path = os.path.join(SITE, "data", "cases.json")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("schema_version") != "1.0":
        errors.append("schema_version must be '1.0'")
    ids = [c.get("id") for c in doc.get("cases", [])]
    if len(ids) != len(set(ids)):
        errors.append(f"duplicate case ids: {ids}")
    for c in doc.get("cases", []):
        check_case(c)
    if "--weight" in sys.argv:
        weight()
    for e in errors:
        print("FAIL", e)
    if errors:
        sys.exit(1)
    drafts = [c["id"] for c in doc["cases"] if c["reviewed_by"] is None]
    print(f"OK  {len(ids)} cases, {len(drafts)} draft (unreviewed): {', '.join(drafts) or 'none'}")


if __name__ == "__main__":
    main()
