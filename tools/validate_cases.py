#!/usr/bin/env python3
"""Schema check for site/data/cases.json. Stdlib only. Exit 1 on any failure.

    python tools/validate_cases.py            # schema, provenance, ranges, files, field geometry
    python tools/validate_cases.py --weight   # also total site/ bytes against the 2 MB cap

Field maths mirrors index.html (handover section 5.3) so the never-silent and
radiation checks in docs/ACCEPTANCE.md (A3, A4) run here. Views, clocks,
modules and attenuation follow docs/ROADMAP.md section 1.
"""
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
# Head clamp box per view (x0, x1, y0, y1) in mm, same as VIEWS in index.html
VIEW_BOX = {
    "chest_anterior": (-150, 150, -60, 240),
    "chest_posterior": (-150, 150, -60, 240),
    "abdomen": (-140, 140, -130, 130),
}
PROV = {"synthesized", "recorded_annotated", "recorded_clinician_labelled"}
MODULE_FINDINGS = {
    "heart": {"normal", "s3", "s4", "split_s2", "systolic_murmur", "diastolic_murmur", "click", "rub"},
    "lung": {"vesicular_normal", "diminished_breath", "absent_breath", "fine_crackles", "coarse_crackles", "wheeze", "rhonchi", "stridor", "pleural_rub"},
    "bowel": {"bowel_active", "bowel_hyperactive", "bowel_hypoactive", "bowel_absent"},
}
HEART = {"s1", "s2", "s3", "s4", "murmur", "click", "snap", "rub"}
LUNG = {"lung_vesicular", "lung_crackles", "lung_wheeze", "lung_rhonchi", "lung_stridor", "lung_rub"}
BOWEL = {"bowel"}
BOUNDARY = {"boundary_breath", "boundary_bowel", "boundary_heart"}
CLOCKS = {"cardiac", "respiratory", "stochastic", "loop"}
PROM = {"faint", "moderate", "pronounced"}
SHAPES = {"crescendo", "decrescendo", "diamond", "plateau"}
PITCH = {"low", "medium", "high"}
QUALITY = {"blowing", "harsh", "musical"}
PHASES = {"inspiratory", "expiratory", "both"}
WINDOWS = {"early", "mid", "late", "full"}
RADIATION_POINT = {"carotids": (-10, -30), "axilla": (150, 110)}  # handover section 5.5 regions, chest_anterior
WEIGHT_CAP = 2_000_000

errors = []


def err(cid, msg):
    errors.append(f"{cid}: {msg}")


def default_clock(t):
    return "loop" if t in BOUNDARY else "respiratory" if t in LUNG else "stochastic" if t in BOWEL else "cardiac"


def field(sources, x, y, view, case_view):
    best = 0.0
    for s in sources:
        if s.get("view", case_view) != view:
            continue
        dx, dy = x - s["x"], y - s["y"]
        sx = s["spread"]["l"] if dx < 0 else s["spread"]["r"]
        sy = s["spread"]["u"] if dy < 0 else s["spread"]["d"]
        best = max(best, s.get("gain", 1.0) * math.exp(-(dx * dx / (sx * sx) + dy * dy / (sy * sy))))
    return best


def sources_of(layer):
    return layer.get("sources") or ([layer["source"]] if "source" in layer else [])


def check_source(cid, s, where, case_view, views):
    for k in ("x", "y", "spread"):
        if k not in s:
            err(cid, f"{where}: source missing {k}")
            return
    view = s.get("view", case_view)
    if view not in views:
        err(cid, f"{where}: source view {view!r} is not one of the case views {sorted(views)}")
        return
    box = VIEW_BOX[view]
    if not (box[0] <= s["x"] <= box[1] and box[2] <= s["y"] <= box[3]):
        err(cid, f"{where}: source ({s['x']}, {s['y']}) outside the {view} box {box}")
    for d in "lrud":
        if not isinstance(s["spread"].get(d), (int, float)) or s["spread"][d] <= 0:
            err(cid, f"{where}: spread.{d} must be a positive number")
    if "gain" in s and not (isinstance(s["gain"], (int, float)) and 0 < s["gain"] <= 1):
        err(cid, f"{where}: source gain must be in (0, 1]")


def check_stem(cid, where, stem):
    if not isinstance(stem, dict):
        err(cid, f"{where}: stem must be an object")
        return
    if stem.get("kind", "synth") not in {"synth", "recorded"}:
        err(cid, f"{where}: stem.kind must be synth or recorded")
    if not stem.get("file"):
        err(cid, f"{where}: stem.file missing")
    elif not os.path.isfile(os.path.join(SITE, stem["file"])):
        err(cid, f"{where}: stem file not found: site/{stem['file']} (run tools/synth_stems.py)")


def check_layer(cid, i, L, case_view, views):
    t = L.get("type")
    where = f"layer {i} ({t})"
    if t not in HEART | LUNG | BOWEL | BOUNDARY:
        err(cid, f"{where}: unknown layer type")
        return
    prov = L.get("provenance") or {}
    if prov.get("class") not in PROV:
        err(cid, f"{where}: provenance.class must be one of {sorted(PROV)}")
    if not prov.get("basis") and not prov.get("dataset"):
        err(cid, f"{where}: provenance needs basis (or dataset for recorded stems)")
    clock = L.get("clock", default_clock(t))
    if clock not in CLOCKS:
        err(cid, f"{where}: clock must be one of {sorted(CLOCKS)}")
    if L.get("stems"):
        for k in ("in", "out"):
            if k not in L["stems"]:
                err(cid, f"{where}: stems needs both in and out")
            else:
                check_stem(cid, f"{where} stems.{k}", L["stems"][k])
    elif "stem" in L:
        check_stem(cid, where, L["stem"])
    else:
        err(cid, f"{where}: needs a stem (or stems for two-phase layers)")
    if L.get("intensity") not in PROM and t != "murmur":
        err(cid, f"{where}: intensity must be one of {sorted(PROM)}")
    if t in BOUNDARY:
        srcs = L.get("sources")
        if not srcs:
            err(cid, f"{where}: boundary layer needs a non-empty sources list")
            return
        for j, s in enumerate(srcs):
            if not s.get("label"):
                err(cid, f"{where}: sources[{j}] needs a label (shown as the region caption)")
            check_source(cid, s, f"{where} sources[{j}]", case_view, views)
        return
    srcs = sources_of(L)
    if not srcs:
        err(cid, f"{where}: needs a source (or sources)")
    for j, s in enumerate(srcs):
        check_source(cid, s, f"{where} source[{j}]", case_view, views)
    if clock == "respiratory":
        if L.get("phase", "both") not in PHASES:
            err(cid, f"{where}: phase must be one of {sorted(PHASES)}")
        if L.get("window", "full") not in WINDOWS:
            err(cid, f"{where}: window must be one of {sorted(WINDOWS)}")
        if "events" in L and not (isinstance(L["events"], int) and 1 <= L["events"] <= 40):
            err(cid, f"{where}: events must be an integer 1-40 (discrete sounds per phase window)")
    if clock == "stochastic":
        r = L.get("rate_per_min")
        if not isinstance(r, (int, float)) or not 0 <= r <= 120:
            err(cid, f"{where}: rate_per_min must be a number 0-120 (0 = absent)")
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
    if t == "s2":
        sp = L.get("split_ms", 0)
        if not isinstance(sp, (int, float)) or not 0 <= sp <= 80:
            err(cid, f"{where}: split_ms must be 0-80")


def check_case(c):
    cid = c.get("id", "?")
    for k in ("id", "title", "findings", "answer_key", "clock", "habitus", "layers", "card",
              "quiz_rationales", "tiers", "reviewed_by", "review_date"):
        if k not in c:
            err(cid, f"missing key {k}")
    if errors and errors[-1].startswith(cid + ": missing"):
        return
    module = c.get("module", "heart")
    if module not in MODULE_FINDINGS:
        err(cid, f"module must be one of {sorted(MODULE_FINDINGS)}")
        return
    case_view = c.get("view", "chest_anterior")
    views = set(c.get("views") or [case_view])
    if case_view not in VIEW_BOX or not views <= set(VIEW_BOX):
        err(cid, f"view/views must be among {sorted(VIEW_BOX)}")
        return
    if case_view not in views:
        err(cid, "view must be one of views")
    if not set(c["findings"]) <= MODULE_FINDINGS[module]:
        err(cid, f"findings must be a subset of the {module} findings {sorted(MODULE_FINDINGS[module])}")
    ak = c["answer_key"]
    if ak.get("primary_finding") not in c["findings"]:
        err(cid, "answer_key.primary_finding must be one of the case findings")
    la = ak.get("loudest_at") or {}
    if not all(k in la for k in ("x", "y", "radius_mm")):
        err(cid, "answer_key.loudest_at needs x, y, radius_mm")
    elif la.get("view", case_view) not in views:
        err(cid, "answer_key.loudest_at.view must be one of the case views")
    if ak.get("best_head") not in {"bell", "diaphragm", "either"}:
        err(cid, "answer_key.best_head must be bell, diaphragm or either")
    if not set(ak.get("radiates_to", [])) <= set(RADIATION_POINT):
        err(cid, f"answer_key.radiates_to entries must be in {sorted(RADIATION_POINT)}")
    if ak.get("timing") not in (None, "systolic", "diastolic", "inspiratory", "expiratory"):
        err(cid, "answer_key.timing must be systolic, diastolic, inspiratory, expiratory or null")
    clk = c["clock"]
    if not 50 <= clk.get("bpm", 72) <= 130:
        err(cid, "clock.bpm must be 50-130")
    if not 200 <= clk.get("systole_ms", 300) <= 400:
        err(cid, "clock.systole_ms out of plausible range (200-400)")
    if not 8 <= clk.get("rr", 14) <= 30:
        err(cid, "clock.rr must be 8-30")
    if not isinstance(c["habitus"], (int, float)) or not 1.0 <= c["habitus"] <= 2.0:
        err(cid, "habitus must be a number 1.0-2.0")
    for j, a in enumerate(c.get("attenuation") or []):
        check_source(cid, a, f"attenuation[{j}]", case_view, views)
        if not a.get("label"):
            err(cid, f"attenuation[{j}] needs a label")
        if not 0 < a.get("amount", 0) <= 1:
            err(cid, f"attenuation[{j}].amount must be in (0, 1]")
        if "lowpass_hz" in a and not 100 <= a["lowpass_hz"] <= 4000:
            err(cid, f"attenuation[{j}].lowpass_hz must be 100-4000")
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
    if module == "heart" and ("s1" not in types or "s2" not in types):
        err(cid, "every heart case needs s1 and s2 layers")
    if module == "lung" and "lung_vesicular" not in types:
        err(cid, "every lung case needs a lung_vesicular layer (the baseline the finding sits on)")
    if not any(t in BOUNDARY for t in types):
        err(cid, "every case needs at least one boundary layer (never-silent rule)")
    for i, L in enumerate(layers):
        check_layer(cid, i, L, case_view, views)
    if errors:
        return
    # A3: never silent anywhere on any of the case's views
    for view in sorted(views):
        box = VIEW_BOX[view]
        worst = 1.0
        for x in range(box[0], box[1] + 1, 10):
            for y in range(box[2], box[3] + 1, 10):
                worst = min(worst, max(field(sources_of(L), x, y, view, case_view) for L in layers))
        if worst < 0.10:
            err(cid, f"never-silent check on {view}: minimum field over the grid is {worst:.3f} (< 0.10)")
    # A4: primary murmur peaks at loudest_at and radiates where the answer key says, and nowhere else
    murmurs = [L for L in layers if L.get("type") == "murmur"]
    if murmurs and ak["primary_finding"].endswith("murmur"):
        m = murmurs[0]
        lv = la.get("view", case_view)
        at = field([m["source"]], la["x"], la["y"], lv, case_view)
        if at < 0.9:
            err(cid, f"murmur field at loudest_at is {at:.2f} (< 0.9)")
        for name, (px, py) in RADIATION_POINT.items():
            v = field([m["source"]], px, py, "chest_anterior", case_view)
            if name in ak["radiates_to"] and v < 0.3:
                err(cid, f"murmur should radiate to {name} but field there is {v:.2f} (< 0.3)")
            if name not in ak["radiates_to"] and v > 0.1:
                err(cid, f"murmur should not radiate to {name} but field there is {v:.2f} (> 0.1)")
    # Lung and bowel: the primary finding layer should peak near loudest_at
    prim = next((L for L in layers if L.get("primary")), None)
    if prim and module != "heart":
        at = field(sources_of(prim), la["x"], la["y"], la.get("view", case_view), case_view)
        if at < 0.8:
            err(cid, f"primary layer field at loudest_at is {at:.2f} (< 0.8)")


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
    if doc.get("schema_version") not in {"1.0", "1.1"}:
        errors.append("schema_version must be '1.0' or '1.1'")
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
    mods = {}
    for c in doc["cases"]:
        mods[c.get("module", "heart")] = mods.get(c.get("module", "heart"), 0) + 1
    print(f"OK  {len(ids)} cases ({', '.join(f'{k} {v}' for k, v in mods.items())}), {len(drafts)} draft (unreviewed): {', '.join(drafts) or 'none'}")


if __name__ == "__main__":
    main()
