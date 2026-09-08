# Writing a case

A case is one "patient": a clock setting, a set of sound layers with sources,
a case card, quiz rationales, and provenance. Cases live in
`site/data/cases.json`. Nothing about a case is in the code.

Learner-facing text names **findings**, never diagnoses. The clinical label
lives in the `id` and in the card's provenance for authors and reviewers only.

## Workflow

1. Copy an existing case object (`as-ejection` is the fullest example).
2. Change `id` (kebab-case, unique, never reused), `title`, `findings`,
   `answer_key`, layers, card, rationales, `tiers`.
3. For each synthesized layer give the stem a new `file` path and `params`.
4. Run:
   ```
   python tools/synth_stems.py
   python tools/validate_cases.py
   python -m http.server -d site 8000
   ```
5. Listen with headphones. Tune spreads and intensities by ear. Note what
   you changed and why in `docs/tuning-notes.md`.
6. Hand to the reviewer. On sign-off, set `reviewed_by` and `review_date`.

## Coordinates

Millimetres. Origin at the suprasternal notch; x positive toward the
patient's left (viewer's right); y positive inferior. The head can reach
x −150…150, y −60…240.

| Landmark | (x, y) |
|---|---|
| Aortic | (−20, 45) |
| Pulmonic | (20, 45) |
| Erb's point | (25, 70) |
| Tricuspid | (28, 110) |
| Mitral (apex) | (85, 125) |

## Fields

### Top level

| Field | Meaning |
|---|---|
| `id` | Unique, stable. Bump with `-v2` rather than editing a reviewed case. |
| `title` | Finding language, shown in the case picker. |
| `findings` | Subset of `normal, s3, s4, split_s2, systolic_murmur, diastolic_murmur, click, rub`. |
| `answer_key.primary_finding` | One of `findings`. |
| `answer_key.loudest_at` | `{x, y, radius_mm}`. Full marks inside the radius, partial to twice it. |
| `answer_key.best_head` | `bell`, `diaphragm`, or `either`. |
| `answer_key.timing` | `systolic`, `diastolic`, or `null`. |
| `answer_key.radiates_to` | Subset of `carotids`, `axilla`. The validator checks the murmur field is strong there and weak at the other. |
| `clock` | `bpm` 50–130, `systole_ms` (300 unless you have a reason). |
| `habitus` | 1.0 for now. |
| `real_thing` | `null`, or `{file, dataset, record, licence}` for a "hear the real thing" clip. |
| `tiers` | Which quiz tiers may draw this case, subset of 1–4. |
| `reviewed_by`, `review_date` | `null` until sign-off. |

### Layers

Every layer: `type`, `stem`, `provenance`, and either `source` (heart layers)
or `sources` (boundary layers).

| `type` | Extra fields |
|---|---|
| `s1`, `s2` | `intensity` faint / moderate / pronounced. `s2` also `split_ms` 0–80. |
| `s3` | `intensity`; `offset_from_s2_ms` (default 150). |
| `s4` | `intensity`; `offset_before_s1_ms` (default 80). |
| `murmur` | `phase` systolic / diastolic; `timing` early / mid / late / holo (suffixes like `midsystolic` are fine); `shape` crescendo / decrescendo / diamond / plateau; `pitch` low / medium / high; `quality` blowing / harsh / musical; `grade` 1–6 (1–4 diastolic). |
| `boundary_breath`, `boundary_bowel` | `intensity`; `sources` list, each with a `label` shown as the region caption. |

**Source**: `{x, y, spread: {l, r, u, d}}`. Strength at head position is
`exp(-(dx²/sx² + dy²/sy²))` with `sx` = `l` if the head is to the patient's
right of the source, else `r`; `sy` = `u` if above, else `d`. Radiation is a
big spread in one direction: a large `u` sends an aortic murmur to the
carotids; a large `r` sends a mitral murmur to the axilla. A displaced apex is
just a moved source point.

**Stem**: `{kind: "synth", file, params}` or
`{kind: "recorded", file, stretch}`. Synth params: `f0` and `decay_ms` for
S1–S4 (optional `attack_ms`); murmurs take their parameters from the layer;
boundary textures take `texture`.

**Provenance**: `class` one of `synthesized`, `recorded_annotated`,
`recorded_clinician_labelled`; `basis` citation (or `n/a - boundary cue`);
recorded stems add `dataset`, `record`, `licence`, `annotation`.

### Card

`summary` (what you hear, one or two sentences), `why` (the mechanism, plain
language), `why_squared` (the discriminating detail, with cites in square
brackets), `sources` (list of full citations).

### Quiz rationales

One short paragraph each, keyed by template: `identify`,
`present_absent_<finding>`, `localize`, `which_head`, `timing`, `radiation`,
`what_changed`. Write only the ones whose template applies to the case. Every
rationale is shown after the learner answers, right or wrong, so write it for
the person who got it wrong.

## Review checklist

- [ ] Findings only in learner-facing text; no diagnosis names.
- [ ] Every layer has a citation or `n/a`, and every `[verify]` in it is resolved.
- [ ] Loudest point matches teaching; `answer_key.loudest_at` sits on it.
- [ ] Radiation direction matches teaching and the validator agrees.
- [ ] Bell vs diaphragm behaves as the card claims (S3 nearly vanishes on the diaphragm, split S2 the reverse).
- [ ] Sounds right at 60, 72, 90, and 110 bpm.
- [ ] Boundary regions still register when the head walks off the heart.
- [ ] Rationales read cleanly to someone who answered wrong.
- [ ] `validate_cases.py` passes; `reviewed_by` and `review_date` set.
