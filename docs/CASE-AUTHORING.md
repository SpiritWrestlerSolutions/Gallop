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

## Modules and views

A case declares `module`: `heart` (default), `lung`, or `bowel`. The module
decides the finding vocabulary, the quiz ladder it counts toward, the
identify-question options, and the reviewer questions.

A case declares `view`: `chest_anterior` (default), `chest_posterior`, or
`abdomen`, and optionally `views` (a list) when it can be examined from more
than one surface; the page shows a flip control. Every source belongs to a
view: sources without a `view` field sit on the case's primary view, and a
source with `"view": "chest_anterior"` on a posterior case is heard only from
the front. `answer_key.loudest_at` can carry a `view` too.

## Clocks

Each layer runs on one clock. The default follows the type; set `clock` to
override.

| Clock | Default for | Fields |
|---|---|---|
| `cardiac` | `s1` … `murmur`, `boundary_heart` | `clock.bpm`, `clock.systole_ms` on the case |
| `respiratory` | `lung_*` | `clock.rr` on the case (8–30); on the layer `phase` inspiratory / expiratory / both, `window` early / mid / late / full, optional `events` (discrete sounds per window, e.g. crackles) |
| `stochastic` | `bowel` | `rate_per_min` on the layer (0 = absent); gaps are Poisson |
| `loop` | `boundary_breath`, `boundary_bowel` | a looped texture, independent of every clock |

Two-phase layers (`lung_vesicular`) carry `stems: {in, out}` instead of one
`stem`; the engine cuts each stem at the phase end with a short fade. A
single-stem respiratory layer starts at its window and is cut at the window
end.

Mark the layer that carries the finding with `"primary": true`. The quiz
scales that layer's intensity by tier, and the validator checks it peaks at
`loudest_at`.

## Attenuation

Optional `attenuation` list on the case: regions where tissue scales every
layer down and muffles it. Each entry is a source (`label`, `x`, `y`,
`spread`, optional `view`) plus `amount` (0–1, the gain reduction at the
centre) and `lowpass_hz` (the filter corner at the centre, default 400).
`habitus` above 1.0 is the same effect over the whole body: a habitus of 1.4
attenuates by 1 − 1/1.4.

## Coordinates

Millimetres. x positive toward the patient's left; y positive inferior.

| View | Origin | Head can reach | Screen |
|---|---|---|---|
| `chest_anterior` | suprasternal notch | x −150…150, y −60…240 | patient's left on the viewer's right |
| `chest_posterior` | spinous process of C7 | x −150…150, y −60…240 | mirrored: patient's left on the viewer's left |
| `abdomen` | umbilicus | x −140…140, y −130…130 | patient's left on the viewer's right |

Posterior landmarks: RU (−45, 30), LU (45, 30), RM (−50, 95), LM (50, 95),
RB (−75, 175), LB (75, 175). Abdomen: RUQ (−60, −50), LUQ (60, −50),
RLQ (−60, 60), LLQ (60, 60). All provisional until the illustration work.

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
| `module`, `view`, `views` | See Modules and views above. |
| `findings` | Subset of the module's vocabulary. Heart: `normal, s3, s4, split_s2, systolic_murmur, diastolic_murmur, click, rub`. Lung: `vesicular_normal, diminished_breath, absent_breath, fine_crackles, coarse_crackles, wheeze, rhonchi, stridor, pleural_rub`. Bowel: `bowel_active, bowel_hyperactive, bowel_hypoactive, bowel_absent`. |
| `answer_key.primary_finding` | One of `findings`. |
| `answer_key.loudest_at` | `{x, y, radius_mm}`. Full marks inside the radius, partial to twice it. |
| `answer_key.best_head` | `bell`, `diaphragm`, or `either`. |
| `answer_key.timing` | `systolic`, `diastolic`, `inspiratory`, `expiratory`, or `null`. |
| `answer_key.radiates_to` | Subset of `carotids`, `axilla`. The validator checks the murmur field is strong there and weak at the other. |
| `clock` | `bpm` 50–130, `systole_ms` (300 unless you have a reason), `rr` 8–30 (default 14). |
| `habitus` | 1.0 = none; up to 2.0. See Attenuation. |
| `attenuation` | Optional list of tissue regions. See Attenuation. |
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
| `boundary_heart` | The distant heart on views where it is a boundary cue (abdomen, back). `intensity`; `sources` with labels; runs on the cardiac clock; `stem` for S1, optional `stems.out` for S2. |
| `lung_vesicular` | Baseline breath sounds. `intensity`; `stems: {in, out}`; `sources` over the lung fields. Every lung case needs one. |
| `lung_crackles` | `intensity`; `phase` (usually inspiratory); `window` (fine crackles late, coarse early); `events` per window; `stem` one crackle. |
| `lung_wheeze`, `lung_rhonchi`, `lung_stridor`, `lung_rub` | `intensity`; `phase`; `window`; `stem` (cut at the phase end). |
| `bowel` | `intensity`; `rate_per_min` (active 5–30, hyperactive above 30, hypoactive under 5, absent 0); `stem` one gurgle or tinkle. |

**Source**: `{x, y, spread: {l, r, u, d}}`. Strength at head position is
`exp(-(dx²/sx² + dy²/sy²))` with `sx` = `l` if the head is to the patient's
right of the source, else `r`; `sy` = `u` if above, else `d`. Radiation is a
big spread in one direction: a large `u` sends an aortic murmur to the
carotids; a large `r` sends a mitral murmur to the axilla. A displaced apex is
just a moved source point.

**Stem**: `{kind: "synth", file, params}` (set `params.kind` to pick a stem generator: `vesicular_in`, `vesicular_out`, `bronchial_in`, `bronchial_out`, `crackle_fine`, `crackle_coarse`, `wheeze`, `rhonchi`, `stridor`, `lung_rub`, `bowel_gurgle`, `bowel_tinkle`, `burst`) or
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
