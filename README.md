# Gallop — cardiac auscultation trainer

A browser page for learning to recognise heart sounds by ear. Move a virtual
stethoscope over a chest, switch between bell and diaphragm, and hear a mix
that changes continuously with position. Findings, not diagnoses: the target
skill is the sentence in a chart note, "systolic murmur, loudest at the aortic
area, radiates to the carotids".

Built for Community Paramedics and Advanced Care Paramedics in the EHS Alberta
Mobile Integrated Healthcare program. Public and open source; use it if it
helps.

**Why it exists.** Barrett et al. showed that clinicians recognise murmurs
poorly and do not improve with years of training, but that about 500
repetitions of a sound builds recognition, and that this works as web-delivered
self-study (Chest 2004;126:470; Am J Med 2006;119:73). Recordings do not
replace hands-on time: Gallop builds the ear, the program's manikin and real
patients build the hands.

Status: **beta.** Engine (Phase 1) and quiz mode (Phase 3) are built. Two
synthesized cases so far, both unreviewed drafts; the quiz lets drafts in
behind a beta label until a reviewer signs off (`QUIZ_ALLOWS_DRAFTS` in
`site/index.html`). The remaining ten v1 cases are the next job; see
[docs/CASE-AUTHORING.md](docs/CASE-AUTHORING.md). The full brief is in
[GALLOP-HANDOVER.md](GALLOP-HANDOVER.md); the Phase 1 test script is in
[docs/ACCEPTANCE.md](docs/ACCEPTANCE.md).

## Run it

Static files, no build step. Browsers block `fetch` from `file://`, so serve the
folder:

```
python -m http.server -d site 8000
```

Open http://localhost:8000. Headphones are required for the bell (20–70 Hz
content is inaudible on phone and laptop speakers); the page checks and
degrades to diaphragm-only if you say you cannot hear the 40 Hz tone.

Regenerate the audio stems and check the case file:

```
python tools/synth_stems.py          # writes site/audio/** (stdlib only, deterministic)
python tools/validate_cases.py       # schema, provenance, geometry; add --weight for the 2 MB cap
```

## Add a case

Add an object to `site/data/cases.json`. Nothing about a case is in the code.
Each layer has a type, an intensity (`faint` / `moderate` / `pronounced`, or a
Levine grade for murmurs), a source point on the chest in millimetres with a
spread in four directions, a stem file, and a provenance citation. Synth stems
carry a `file` path that `tools/synth_stems.py` renders from `params`. Boundary
layers carry a `sources` list with a `label` shown as the region caption.
Run the validator; it also checks that nowhere on the chest is silent and that
a murmur radiates where the answer key says and nowhere else.

Coordinates: origin at the suprasternal notch, x positive toward the patient's
left, y positive inferior. Head clamp box x −150…150, y −60…240.

Cases with `reviewed_by: null` show a draft pill and will be excluded from quiz
mode.

## Provisional values

Everything below is marked **[verify]** or **[inference]** in the handover, or
was chosen during Phase 1 without a source. Each must be checked or tuned by ear
against the manikin before a learner sees it, per handover §15 Phase 2.

From the handover, left as written:

- Systole held at 300 ms. [verify: typical resting LV ejection time 250–330 ms]
- S1 band 50–150 Hz; engine stem uses f0 90 Hz, 60 ms decay. [verify]
- S2 higher pitch than S1; engine stem uses f0 120 Hz, 45 ms decay. [verify]
- S2 split parameter range 0–80 ms. [verify]
- S3 band 25–70 Hz, ~150 ms after S2. [verify]
- Diaphragm high-pass corner 100–150 Hz; engine uses 125 Hz. [verify against stethoscope literature]
- Bell low-pass above roughly 200 Hz; engine uses 200 Hz. [verify]
- Every spread value in `cases.json`. [inference until a reviewer signs off]
- Landmark coordinates A (−20,45), P (20,45), Erb's (25,70), T (28,110), M (85,125). [inference, set from the silhouette artwork]
- Bates 13e page numbers and Braunwald 12e chapter in every citation. [verify at authoring]
- Palette reuses Cairn's blues. [inference: Brendan may want Gallop's own accent]
- Hostname `gallop.yeomanops.com`, and the footer link to Cairn at `cairn.yeomanops.com`. [inference]
- Tier advancement 8 consecutive to advance, 4-in-10 to drop. [inference, not used in Phase 1]
- Safari OGG support. [verify] Sidestepped in Phase 1: stems are WAV (8 kHz mono, 148 KB total).

Chosen in Phase 1 without a source, tune by ear:

- Reference master gain 0.7; intensity to gain map: faint 0.35, moderate 0.6, pronounced 1.0; grades I/II/III 0.12/0.25/0.45, IV–VI 0.7 ("loud"); boundary faint 0.1.
- Murmur pitch centres: low 100 Hz, medium 250 Hz, high 400 Hz. Filter Q: blowing 1.4, harsh 0.6, musical 1.0.
- Murmur timing windows as fractions of the phase: early 3–50 %, mid 12–90 %, late 50–97 %, holo 2–98 %.
- S4 placed 80 ms before the next S1.
- Boundary geometry: three breath sources (right lung field, left lung field toward the axilla, upper lobes over the neck) rather than the two named in handover §5.5, because two lung sources did not reach the neck region; one bowel source at (20, 205).
- Head crossfade 30 ms; compare-to-normal crossfade 20 ms; per-layer gain smoothing time constant 20 ms.

## Quiz mode

Four tiers, a personal mastery ladder (8 in a row to advance, 4 misses in 10
to drop back), seven question templates, spaced repetition of misses at 3, 10
and 30 questions, replay by seed, export and import of progress as JSON.
Everything is stored in the browser only. With two cases the "no repeat within
15 questions" rule cannot be met; the generator takes the least-recent
combination instead until the case library grows.

## Reviewer mode

Open the site with `?review` on the URL, or use the "Reviewer mode" link in
the footer. A "Review this case" button appears in practice mode and opens a
panel with ten fixed questions and a free-text box. Audio and the head keep
working while it is open. Reviews are stored in the reviewer's browser and
reach you only by "Send by email" or "Export all reviews"; a learner reset
does not delete them. Set `REVIEW_EMAIL` in `site/index.html` before sharing
the link. The plan for what comes next is in [docs/ROADMAP.md](docs/ROADMAP.md).

## Not built yet

Cases 3 to 12 of the v1 library, recorded PhysioNet stems, ejection click,
opening snap, rub, body habitus (Tier 4 draws no habitus yet), respiratory
modulation (the clock has the hook, wired to nothing), Tier 3 lookalike
distractors (needs the split-S2 and S3 cases), the Tier 1 "the S3 dropped out"
head-switch note (no case has an S3 yet), logo, by-ear tuning against the
manikin, clinical review.

## Licence

Code MIT (`LICENSE`). Content and synthesized audio CC BY 4.0, Brendan Hood
(`LICENSE-CONTENT`). Dataset citations in `ATTRIBUTION.md`; stem classes and
the reviewer rule in `PROVENANCE.md`. Deployment in `deploy/DEPLOY.md`.
How to write a case in `docs/CASE-AUTHORING.md`.
