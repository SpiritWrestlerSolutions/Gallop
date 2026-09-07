# Gallop — cardiac auscultation trainer

**Handover brief, v1.0 — 2 September 2026**
Author: Brendan Hood (product owner, clinical lead). Drafted with Claude for handover to a Claude Code session.

This document is the starting brief for building Gallop. It records every decision made during planning, the audio model, the data schema, the quiz design, licensing, deployment, and the acceptance criteria for the first build phase. Anything marked **[verify]** is a figure or assertion that must be checked against a source during content authoring before it is presented to a learner. Anything marked **[inference]** is a working assumption Brendan has not confirmed; build to it, flag it in the README as provisional.

---

## 1. Purpose and intent

Gallop is a browser-based practice tool for recognising heart sounds by ear. The learner moves a virtual stethoscope over a chest, switches between bell and diaphragm, hears a synthesized-and-recorded mix that changes continuously with position, and drills recognition in a quiz mode with a personal mastery ladder.

**The intent is recognition, not diagnosis.** The target skill is the sentence a paramedic writes in a chart: "S3 present; pronounced systolic murmur, loudest at the aortic area." It is not "this is critical aortic stenosis." Findings are the answer set; diagnoses are not.

**Audience.** Community Paramedics and Advanced Care Paramedics in the province-wide Mobile Integrated Healthcare (MIH) program at EHS Alberta, and anyone else who finds it useful (the tool is public and open source).

**Why it exists.** The program has a high-fidelity manikin, but province-wide access to it is scarce. Hands-on time on the manikin is the right place to learn placement and technique; Gallop is the right place to get the repetitions that build an auditory template. The two are complementary, and the tool must say so on its front page.

### Evidence for the approach

- Medical students recognise heart murmurs poorly (about 20 %) and do not improve with further years of training; 500 repetitions of four basic murmurs significantly improved auscultatory proficiency, suggesting cardiac auscultation is, in part, a technical skill. Barrett MJ, Lacey CS, Sekara AE, Linden EA, Gracely EJ. *Mastering cardiac murmurs: the power of repetition.* Chest. 2004;126(2):470-475. doi:10.1378/chest.126.2.470
- The 500 repetitions needed for mastery of each murmur can be delivered in roughly 15 minutes and works as web-delivered self-study with mastery-model testing. Barrett MJ, Kuzma MA, Seto TC, et al. *The power of repetition in mastering cardiac auscultation.* Am J Med. 2006;119(1):73-75. doi:10.1016/j.amjmed.2004.12.036
- Honest counterweight, to be stated in the rationale: training on recordings does not necessarily transfer to bedside performance (see the discussion in Barrett 2004 and the studies it cites — Clair 1992, Mangione & Nieman 1997, Mahnke 2004). Gallop builds the ear; the manikin and the patient build the hands.

---

## 2. Non-goals (v1)

- No diagnosis output. The tool never says "this patient has X."
- No lung-sound curriculum. Breath sounds exist only as a boundary cue (section 5.5).
- No user accounts, server-side storage, or analytics. Progress is stored in the browser only.
- No patient-facing use. This is a clinician education tool.
- No competitive features: no leaderboards, no comparison between learners, no public scores. The mastery ladder is personal.
- No mobile app. It is a web page that works on a phone.

---

## 3. Product decisions (settled)

| Decision | Choice | Rationale |
|---|---|---|
| Form | Standalone web app, sibling of Cairn | Independent dev cycle and release cadence; linked from Cairn |
| Name | **Gallop** — descriptor "cardiac auscultation trainer" everywhere the name appears | Clinical term (S3/S4 gallop rhythm), short, memorable; descriptive term so low trademark exposure; no product of that name found in the space (checked 2 Sept 2026; CIPO/USPTO lookup still to do before public release) |
| Licence | Code: MIT. Content and synthesized audio: CC BY 4.0. Derived recordings: inherit ODC-By 1.0 (section 11) | Open source with attribution, matching Brendan's other clinical tools |
| Hosting | Static site in `nginx:alpine` behind host Caddy on the OVH server, same pattern as Cairn | Nothing new to learn; ATLAS cannot host scripts |
| Audio source strategy | Synthesized, literature-grounded stems are the primary teaching material; PhysioNet recordings are supporting material (real-thing clips, hard mode) | Clean, adjustable, reproducible, and licence-clean; real recordings are noisy, asynchronous across sites, and mostly unlabelled at the finding level |
| Headphones | Required for full use; tool detects and degrades gracefully | Bell-range sounds (20–70 Hz) are inaudible on phone and laptop speakers |
| Persistence | `localStorage` only | Static site; no backend; learner can reset |

---

## 4. Vocabulary

- **Layer** — one sound component scheduled against the cardiac clock (S1, S2, S3, S4, a murmur, a click, a rub, a boundary sound).
- **Source** — where a layer comes through the chest wall most strongly, with a spread in four directions.
- **Case** — a complete "patient": a clock setting, a set of layers with sources and intensities, rationale text, quiz rationales, and provenance.
- **Head** — the stethoscope chest piece: bell or diaphragm.
- **Landmark** — a named auscultation point drawn on the chest. Landmarks are labels, not mechanisms.
- **Finding** — what a learner can name: S3, S4, split S2, systolic murmur, diastolic murmur, click, rub, normal.

---

## 5. Audio model

The engine is the Web Audio API in a single page. No audio frameworks. The chain, in order:

```
cardiac clock → layers → source-field blend (head position) → head filter → calibrated output
```

### 5.1 Cardiac clock

- One master timeline. All layers are scheduled from it, so everything stays phase-locked regardless of source (synthesized or recorded).
- **Heart rate** adjustable, integer bpm. Default 72. Practice range 50–130.
- **Systole** is held approximately fixed at ~300 ms **[verify: typical resting LV ejection time 250–330 ms]**. **Diastole** absorbs rate changes. Consequence the engine must produce: as rate rises, S3 and S4 move toward each other and, above roughly 100–110 bpm, merge into a single summation gallop. This is a deliberate teaching behaviour, not a side effect.
- **Respiratory cycle**: a slow modulator (~4 s period) is built into the clock in Phase 1 but wired to nothing. Phase 3+ uses it for physiological S2 splitting on inspiration and augmentation of right-sided sounds. Do not implement the effects in Phase 1; do leave the hook.
- Timing is scheduled ahead using `AudioContext.currentTime` with a look-ahead scheduler (the standard "tale of two clocks" pattern), not `setTimeout` alone. Rate changes take effect at the next cycle boundary, never mid-cycle.

### 5.2 Layers

Each layer is defined by: **timing** (offset from S1 or S2, duration), **band** (centre frequency and width), **envelope** (attack/decay or shaped noise), **peak intensity**, and **source** (section 5.3). Parameter ranges below are starting points from standard teaching; every one carries a citation in the case card and is tuned by ear against the manikin during Phase 2.

| Layer | Timing | Character | Notes |
|---|---|---|---|
| S1 | Cycle start | Short damped burst, ~50–150 Hz **[verify]** | Loudest at apex; audible over the whole precordium |
| S2 | End of systole | Short damped burst, higher pitch than S1 **[verify]** | Two components A2 then P2; **split** parameter 0–80 ms **[verify]**; loudest at base |
| S3 | ~120–180 ms after S2 (Wikipedia; UMedic course material gives ~150 ms) | Low, dull thud, ~25–70 Hz **[verify]** | Best on the bell at the apex; should nearly vanish on the diaphragm (Healio "Learn the Heart") |
| S4 | Just before S1 (late diastole) | Low, dull thud, similar band to S3 | Absent at fast rates by merging into summation gallop |
| Systolic murmur | Between S1 and S2 | Band-limited noise shaped by envelope | Parameters: timing (early / mid / late / holo), shape (crescendo / decrescendo / diamond / plateau), pitch (low / medium / high), quality (blowing = smoother noise, harsh = rougher, musical = tonal component), grade I–VI Levine |
| Diastolic murmur | Between S2 and next S1 | Same parameter set | Grades I–IV |
| Ejection click | Early systole, just after S1 | Short high-pitched tick | Phase 3+ |
| Opening snap | Early diastole, after S2 | Short high-pitched tick | Phase 3+ |
| Pericardial rub | Up to three components per cycle | Scratchy broadband noise | Phase 3+ |
| Boundary sounds | Independent of clock (breath, bowel) | See 5.5 | Always present at low level; rise off-heart |

The murmur descriptor taxonomy (timing, shape, pitch, quality, grade) deliberately matches the CirCor DigiScope annotation vocabulary so recorded murmurs can be described in the same terms as synthesized ones. Oliveira J, et al. *The CirCor DigiScope Phonocardiogram Dataset* (v1.0.3). PhysioNet, 2022. doi:10.13026/tshs-mw03

Murmur grading: Freeman AR, Levine SA. *The clinical significance of the systolic murmur.* Ann Intern Med. 1933;6:1371-1385. In the tool, grades I–III are the meaningful audio range; IV–VI are rendered as "loud" and the card notes that thrills (IV+) are palpable, not audible.

**Synthesis approach.** S1/S2: damped sinusoid or narrowband noise burst with a fast attack and exponential decay. S3/S4: the same at lower centre frequency with a softer attack. Murmurs: white noise through a band-pass filter, multiplied by an envelope function chosen by `shape`; `quality` sets the filter Q and adds a weak tonal component for "musical." Boundary sounds: looped noise textures. Build stems offline (Python/NumPy) into short WAV/OGG files where that is simpler than live synthesis; the engine only needs to play, time, and mix them. Live synthesis is acceptable for S1–S4 and murmurs if it proves easier to keep phase-locked.

**Recorded stems** (section 11) slot into the same layer slots: a single clean cardiac cycle is extracted from a PhysioNet record, trimmed at S1 onset, and placed on the clock. Small time-stretching to match the case's cycle length is acceptable; note the stretch factor in provenance.

### 5.3 Source-field model (the stethoscope)

Rather than a table of volumes at five named points, **each layer has a source point on the chest and a spread in four directions**. The mix at any head position is each layer's strength at that distance, summed.

Chest coordinates: a 2-D plane in millimetres on a fixed adult male silhouette (section 6). For a layer with source `(x0, y0)` and spreads `sL, sR, sU, sD`:

```
dx = x − x0 ;  dy = y − y0
sx = (dx < 0) ? sL : sR
sy = (dy < 0) ? sU : sD
strength = peak × exp( −( dx²/sx² + dy²/sy² ) )
```

Directional spreads encode **radiation**: an aortic-stenosis murmur has a large `sU` (toward the carotids); a mitral-regurgitation murmur has a large `sR` on the patient's left (toward the axilla). Spread values are authored per case and tuned by ear; they are **[inference]** until a reviewer signs them off.

What this gives for free, and must therefore work in Phase 1:

- A **displaced apex** is just a moved source point.
- **Walking off the heart** happens naturally: heart layers fade, boundary layers rise.
- **"Find where it's loudest"** is a real search on a continuous surface.
- **Body habitus** (Phase 4) is one scalar that shrinks every spread and adds a low-pass muffle.

Landmarks (A, P, Erb's, T, M) are drawn as labels. Erb's point has no source of its own; it is where the aortic and pulmonic fields overlap.

### 5.4 Head filter

- **Diaphragm**: high-pass, corner roughly 100–150 Hz **[verify against stethoscope literature]**, favours S1/S2, clicks, snaps, blowing murmurs, split S2.
- **Bell**: passes the low end, gentle low-pass above roughly 200 Hz **[verify]**, favours S3, S4, mitral-stenosis rumble.
- Implemented as a single `BiquadFilterNode` whose type and frequency change on toggle. Switching must be gapless: crossfade over ~30 ms between two parallel filter paths rather than reconfiguring one node mid-stream.
- Teaching behaviour that must be audible: an S3 clearly present on the bell nearly vanishes on the diaphragm; a split S2 does the reverse.

### 5.5 Boundary sources

Every edge of the precordium gets a sound that tells the learner where they are without a popup.

| Region | Sound | Rises when head is… | Why-squared note |
|---|---|---|---|
| Inferior (epigastrium / liver) | Bowel sounds; heart as a distant thump | Below the apex | You're over the abdomen; heart sounds transmit but do not localise here |
| Lateral (past anterior axillary line) | Breath sounds; only murmurs that radiate laterally remain | Toward the axilla | MR carries here; AS does not — a real finding, not just a boundary cue |
| Superior (above clavicles / carotids) | Breath sounds (upper lobes); carotid bruit **only if the case's aortic murmur radiates** | Over the neck | Chasing AS up the neck is rewarded; chasing MR is not |
| Right chest (off the sternum, patient's right) | Breath sounds; distant heart | Over the right lung field | The tool must never go silent; silence reads as "broken" |

Boundary sources use the same source-field maths (lung fields: two large sources; bowel: one broad inferior source). Keep peak intensity modest — they should register, not startle.

### 5.6 Calibration and output

- On launch: a **reference tone sequence** (normal S1/S2 at 72 bpm) plays at the tool's reference level. The learner sets device volume until it is comfortably audible. The tool then never changes master gain. Every intensity setting in the tool is relative to this reference.
- **Headphone check**: a 40 Hz tone at reference level with "Can you hear this?" On "No": explain that bell-range sounds are inaudible on this device and offer to continue in diaphragm-only practice. Do not block.
- Mobile browsers require a user gesture before audio starts; the calibration step is that gesture. On iOS, resume the `AudioContext` inside the tap handler.
- Output is mono, duplicated to both channels.

### 5.7 Intensity

Intensity is per layer, never a global knob.

- Murmurs: Levine grade I–VI, mapped to gain. Grade I sits just above the boundary-sound floor at the reference level — audible only if listening for it.
- S3, S4, clicks, snaps: prominence scale `faint / moderate / pronounced`.
- In practice mode the learner may adjust any layer's intensity to find their own threshold. In quiz mode intensity is drawn from the tier band (section 8) and hidden.

---

## 6. Chest coordinate system and landmarks

Fixed adult male silhouette for v1. Coordinates are stored in millimetres relative to the suprasternal notch (x = 0 at midline, positive toward the patient's left; y = 0 at the notch, positive inferior). Source points live in case files, so a future body-size parameter can move them without touching the engine.

Landmark positions (standard teaching; cite StatPearls *Physiology, Heart Sounds*, NBK541010, and Bates' Guide to Physical Examination in the case card — **[verify page/edition]**):

| Landmark | Anatomical position | Provisional (x, y) mm **[inference — set from the silhouette artwork]** |
|---|---|---|
| Aortic | 2nd intercostal space, right sternal border | (−20, 45) |
| Pulmonic | 2nd intercostal space, left sternal border | (20, 45) |
| Erb's point | 3rd intercostal space, left sternal border | (25, 70) |
| Tricuspid | 4th–5th intercostal space, left lower sternal border | (28, 110) |
| Mitral (apex) | 5th intercostal space, midclavicular line | (85, 125) |

Draw the silhouette as a clean vector (SVG) with sternum, clavicles, and rib-space hints faint enough not to clutter. Landmark labels dim except the nearest one while dragging.

---

## 7. Case schema

Cases live in `data/cases.json`. The engine reads the file at load; nothing about a case is hard-coded. Add a case by adding an object.

```json
{
  "schema_version": "1.0",
  "cases": [
    {
      "id": "mr-with-s3",
      "title": "Systolic murmur with S3",
      "findings": ["systolic_murmur", "s3"],
      "answer_key": {
        "primary_finding": "systolic_murmur",
        "loudest_at": { "x": 85, "y": 125, "radius_mm": 20 },
        "best_head": "bell",
        "timing": "systolic",
        "radiates_to": ["axilla"]
      },
      "clock": { "bpm": 72, "systole_ms": 300 },
      "habitus": 1.0,
      "layers": [
        {
          "type": "s1",
          "intensity": "pronounced",
          "source": { "x": 85, "y": 125, "spread": { "l": 110, "r": 55, "u": 80, "d": 45 } },
          "stem": { "kind": "synth", "params": { "f0": 90, "decay_ms": 60 } },
          "provenance": { "class": "synthesized", "basis": "Bates 13e p. XXX; StatPearls NBK541010" }
        },
        {
          "type": "s2",
          "intensity": "moderate",
          "split_ms": 0,
          "source": { "x": 0, "y": 45, "spread": { "l": 70, "r": 70, "u": 40, "d": 110 } },
          "stem": { "kind": "synth", "params": { "f0": 120, "decay_ms": 45 } },
          "provenance": { "class": "synthesized", "basis": "Bates 13e p. XXX" }
        },
        {
          "type": "s3",
          "intensity": "moderate",
          "offset_from_s2_ms": 150,
          "source": { "x": 85, "y": 125, "spread": { "l": 35, "r": 35, "u": 30, "d": 30 } },
          "stem": { "kind": "synth", "params": { "f0": 40, "decay_ms": 90 } },
          "provenance": { "class": "synthesized", "basis": "UMedic S3 module (~150 ms after S2); Healio Learn the Heart (bell vs diaphragm)" }
        },
        {
          "type": "murmur",
          "phase": "systolic",
          "timing": "holosystolic",
          "shape": "plateau",
          "pitch": "high",
          "quality": "blowing",
          "grade": 3,
          "source": { "x": 85, "y": 125, "spread": { "l": 45, "r": 120, "u": 40, "d": 45 } },
          "stem": { "kind": "recorded", "file": "audio/stems/circor-50123-MV-cycle1.ogg", "stretch": 1.02 },
          "provenance": {
            "class": "recorded_annotated",
            "dataset": "CirCor DigiScope v1.0.3",
            "record": "50123_MV",
            "licence": "ODC-By 1.0",
            "annotation": "Holosystolic, plateau, high, blowing, III/VI, most audible MV"
          }
        },
        {
          "type": "boundary_breath",
          "intensity": "faint",
          "stem": { "kind": "synth", "params": { "texture": "vesicular" } },
          "provenance": { "class": "synthesized", "basis": "n/a — boundary cue" }
        },
        {
          "type": "boundary_bowel",
          "intensity": "faint",
          "stem": { "kind": "synth", "params": { "texture": "bowel" } },
          "provenance": { "class": "synthesized", "basis": "n/a — boundary cue" }
        }
      ],
      "real_thing": {
        "file": "audio/real/circor-50123-MV.ogg",
        "dataset": "CirCor DigiScope v1.0.3",
        "record": "50123_MV",
        "licence": "ODC-By 1.0"
      },
      "card": {
        "summary": "A holosystolic blowing murmur loudest at the apex, carrying toward the axilla, with a low-pitched third heart sound just after S2.",
        "why": "The murmur fills systole because the regurgitant flow runs the whole time the ventricle is contracting; it radiates laterally along the direction of the jet. The S3 is the sound of a volume-loaded ventricle filling rapidly.",
        "why_squared": "Holosystolic timing distinguishes regurgitant from ejection murmurs, which are crescendo-decrescendo and stop before S2. The S3 here is a marker of volume load rather than a primary finding. [cite Bates 13e; Braunwald ch. XX]",
        "sources": [
          "Bates' Guide to Physical Examination and History Taking, 13th ed. [page]",
          "Braunwald's Heart Disease, 12th ed. [chapter]",
          "Healio Learn the Heart — S3 topic review"
        ]
      },
      "quiz_rationales": {
        "identify": "You should hear two things: a murmur that runs the full length of systole, and a soft low thud after S2. That second sound is an S3.",
        "present_absent_s3": "Switch to the bell and listen just after S2 at the apex. The S3 is there on the bell and almost gone on the diaphragm.",
        "localize": "The murmur peaks at the apex and stays loud as you move toward the axilla. It fades quickly as you move up the sternum.",
        "which_head": "The murmur is audible on both heads, but the S3 needs the bell.",
        "timing": "The murmur sits between S1 and S2, so it is systolic.",
        "radiation": "Follow it laterally: it is still there at the axilla. Up the sternum it is gone."
      },
      "tiers": [1, 2, 3, 4],
      "reviewed_by": null,
      "review_date": null
    }
  ]
}
```

Schema rules:

- `provenance.class` is one of `synthesized`, `recorded_annotated` (finding matches the dataset's own annotation), `recorded_clinician_labelled` (finding assigned by a reviewer). The UI shows the class on the case card as a small pill, in the style of Cairn's evidence pills.
- Every layer carries `provenance.basis` (a citation) or, for boundary cues, `n/a`.
- `answer_key.loudest_at.radius_mm` is the full-marks radius for the localize template.
- `reviewed_by` / `review_date` are null until a clinical reviewer signs off. Unreviewed cases are visible in practice mode with a "draft" pill and excluded from quiz mode.
- Cases are added, never edited in place once reviewed; bump `id` with a suffix (`-v2`) so a learner's stored progress still refers to the exact case they saw.

---

## 8. Practice mode — behaviour spec

Stated as learner action → tool response → what it teaches. Practice mode never scores.

| Action | Response | Teaches |
|---|---|---|
| Place or drag the head | Mix recalculates continuously from the source fields; nearest landmark label brightens, others dim; nothing else changes | Sound is a continuous field, not five buttons |
| Cross a boundary | Boundary sources rise, heart sources fade; in Tier 1 practice only, a small caption names the region ("over the liver") | Where the heart isn't |
| Switch bell / diaphragm | Gapless filter change; head icon changes; in Tier 1 a one-line note appears only when the switch materially changes what is audible ("the S3 dropped out — that's the diaphragm doing its job") | The head is a tool, not a preference |
| Change heart rate | Diastole shortens, systole roughly fixed; S3 and S4 crowd together and merge above ~100–110 bpm | Why gallops and split-S2 questions get harder in tachycardia |
| Change a layer's intensity | Per-layer slider; murmurs by grade, extra sounds by prominence | What "faint" sounds like relative to a fixed reference |
| Hold "compare to normal" | While held, plays a normal heart at the same rate, position, and head; releases back to the case | The difference, not the absolute |
| Tap a landmark label | Popover: what is normally loudest here and why, with the cite | The anatomy behind the landmarks |
| Open the case card | Layer list with provenance pills, summary, why, why-squared (expandable), sources, "hear the real thing" clip with record ID where present | Credibility through transparency |
| Fail the headphone check | Explains the low-end limitation; offers diaphragm-only practice; never blocks | The low end is real and the device is lying |
| Reset progress | Confirmation, then clears `localStorage` | Learner owns their data |

Global behaviours:

- Audio starts only after the calibration gesture and stops when the tab is hidden.
- All controls are keyboard-operable (arrow keys move the head 5 mm; `B` / `D` switch heads; `N` holds compare-to-normal).
- No modal ever interrupts playback except the reset confirmation.

---

## 9. Quiz mode

### 9.1 Difficulty tiers

Four tiers. What changes between tiers is which levers are set for the learner and which are left to them. The ladder is personal and stored locally; nothing is ever compared between learners.

| | Tier 1 · Foundations | Tier 2 · Recognition | Tier 3 · Localisation | Tier 4 · Field conditions |
|---|---|---|---|---|
| Findings | One pronounced finding, or normal | One moderate finding | Faint finding, or combined (e.g. S3 + murmur) | Faint, combined, plus real-recording clips |
| Head start position | On the correct landmark | Erb's point | Anywhere off-heart | Anywhere, including boundaries |
| Bell / diaphragm | Preset correctly, hint shown | Learner chooses | Learner chooses, no hint | Learner chooses |
| Heart rate | 70 | 60–90 | 60–110 | 60–130 |
| Intensity | Pronounced / grade III | Moderate / grade II | Faint / grade I–II | Faint, plus body-habitus muffle |
| Distractors | None | Normal cases mixed in | Normal cases + lookalikes (split S2 vs S3) | Real-world noise from PhysioNet clips |

### 9.2 Mastery ladder

- Advance from a tier after **8 consecutive correct** answers at that tier **[inference — Brendan to confirm the number]**.
- Drop back one tier after **4 misses within the last 10** questions; the tool says so plainly ("Back to Tier 2 for a bit — that's the point of the ladder").
- The learner can choose any unlocked tier at any time; the ladder is a recommendation, not a gate on practice mode.
- Progress display is a personal ladder graphic: current tier, streak, and a short list of findings recently missed. No percentages, no totals, no comparison.

### 9.3 Question templates

Questions are generated as **templates × cases × parameter draws**, so a small case library yields an effectively unbounded bank while every question still has a hand-written rationale.

| # | Template | Prompt | Answer format | Scoring | Tiers |
|---|---|---|---|---|---|
| 1 | Identify | "What do you hear?" | Choose from the finding list (not diagnoses) | Exact match | 1–4 |
| 2 | Present or absent | "Is there an S3?" (or any single finding) | Yes / No | Exact match; the alternative is a normal or a lookalike | 1–4 |
| 3 | Localise | "Drag to where it is loudest" | Head position | Full marks within `radius_mm`; partial to 2× radius; miss beyond | 2–4 |
| 4 | Which head | "Which head makes this clearest?" | Bell / Diaphragm | Exact match | 1–4 |
| 5 | Timing | "Systolic or diastolic?" | Two options | Exact match | 2–4 |
| 6 | Radiation | "Where else can you hear this?" | Axilla / Carotids / Nowhere | Exact match | 3–4 |
| 7 | What changed | Two clips, same case, one parameter differs | Rate / Head / Intensity / Position | Exact match | 3–4 |

### 9.4 Generation and freshness rules

Per question the generator draws: case (from those tagged for the tier and `reviewed_by` not null), template (from those allowed for the tier), heart rate within the tier band, intensity within the tier band, starting head position per tier rule, habitus (Tier 4 only: 1.0 or 1.4). A **seed** is stored with each question so the learner can replay the exact question they missed.

- No repeat of the same case + template within the last **15** questions.
- Missed questions re-enter the queue at **3, 10, and 30** questions later (a simple spaced-repetition ladder). A question leaves the queue after being answered correctly twice in a row.
- Tier 2+ mixes in normal cases at roughly 1 in 5 so "there is always something to find" never becomes a learned assumption.
- Every question shows its rationale after answering, right or wrong: the short answer for everyone, and an expandable "why squared" with the cite.

### 9.5 Authoring load (realistic)

Twelve cases × roughly five applicable templates ≈ 60 rationales, one paragraph each, plus one case card each. That is Brendan's writing plus one reviewer pass. The engine cannot generate this; plan the time.

---

## 10. v1 case library

Twelve reviewed cases are the Phase 2 target. Findings only — no diagnoses in learner-facing text; the clinical label is in the case `id` and card for authors and reviewers.

| # | Case id | Learner-facing finding(s) | Head | Loudest | Radiates | Tiers |
|---|---|---|---|---|---|---|
| 1 | normal-72 | Normal S1, S2 | Either | — | — | 1–4 |
| 2 | normal-split-s2 | Physiological split S2 | Diaphragm | Pulmonic | — | 2–4 |
| 3 | s3 | S3 | Bell | Apex | — | 1–4 |
| 4 | s4 | S4 | Bell | Apex | — | 1–4 |
| 5 | summation-gallop-110 | S3 + S4 merging at 110 bpm | Bell | Apex | — | 3–4 |
| 6 | as-ejection | Systolic murmur, crescendo-decrescendo, harsh | Diaphragm | Aortic | Carotids | 1–4 |
| 7 | mr-holosystolic | Systolic murmur, holosystolic, blowing | Diaphragm | Apex | Axilla | 1–4 |
| 8 | mr-with-s3 | Systolic murmur + S3 | Both | Apex | Axilla | 2–4 |
| 9 | ar-early-diastolic | Diastolic murmur, decrescendo, blowing | Diaphragm | Erb's / left sternal border | — | 2–4 |
| 10 | ms-rumble | Diastolic murmur, low rumble (+ opening snap in Phase 3) | Bell | Apex | — | 3–4 |
| 11 | vsd-holosystolic | Systolic murmur, holosystolic, harsh | Diaphragm | Left lower sternal border | Broad | 2–4 |
| 12 | innocent-flow | Soft mid-systolic murmur, grade I–II | Diaphragm | Pulmonic / Erb's | — | 2–4 |

Later packs (not v1): pericardial rub, displaced apex (LV enlargement), obese/hyperinflated habitus variants of cases 3, 6, 7; respiratory-variation cases once the modulator is wired.

---

## 11. Audio sources, provenance, and licensing

### 11.1 Stem classes

| Class | Origin | Licence | Where used |
|---|---|---|---|
| `synthesized` | Generated offline (Python/NumPy) or live (Web Audio) from published characteristics; tuned by ear against the program manikin | CC BY 4.0 (Brendan Hood) | Primary teaching material |
| `recorded_annotated` | Single cycle cut from a PhysioNet record where the finding matches the dataset's own expert annotation | ODC-By 1.0 (inherited) | Real murmur examples; "hear the real thing" clips |
| `recorded_clinician_labelled` | Single cycle cut from a PhysioNet record; finding assigned by a named reviewer | ODC-By 1.0 (inherited) | Adult examples where no annotation exists; hard mode |

The manikin's own sound library is vendor IP and is **never** recorded, copied, or redistributed. The manikin is a tuning reference only.

### 11.2 Datasets

- **CirCor DigiScope Phonocardiogram Dataset v1.0.3** (PhysioNet). 5272 recordings from four auscultation sites (AV, PV, TV, MV) in 1568 subjects; murmurs annotated for timing, shape, pitch, grade, quality, location, and most-audible location. Paediatric population; field recordings with ambient noise; site recordings are **not time-synchronous**. Licence: Open Data Commons Attribution License v1.0. Cite: Oliveira J, et al. doi:10.13026/tshs-mw03 and the JBHI paper doi:10.1109/JBHI.2021.3137048, plus the PhysioNet platform citation.
- **PhysioNet/CinC Challenge 2016 database v1.0.0** (PhysioNet). Adult-focused; patient recordings include valve disease (MVP, MR, AS, valvular surgery) but are labelled only normal/abnormal, single lead, 2 kHz, often noisy. Licence: ODC-By 1.0. Cite: Liu C, et al. Physiol Meas. 2016;37(12):2181. doi:10.1088/0967-3334/37/12/2181 and the challenge page.

### 11.3 Repo licence files

- `LICENSE` — MIT, code.
- `LICENSE-CONTENT` — CC BY 4.0, for `data/`, case text, and synthesized stems.
- `ATTRIBUTION.md` — full citations for both datasets and PhysioNet; per-stem record IDs are in `cases.json` so the chain is traceable.
- `PROVENANCE.md` — the three stem classes, the rule that the manikin library is never used, and the reviewer sign-off rule.

---

## 12. Technical approach

- **Single-page static app**: `site/index.html` with inline CSS and JS, plus `site/data/cases.json`, `site/audio/` (stems, real clips, boundary textures), and `site/img/` (silhouette SVG, logo). No framework, no build step, no bundler — matches Cairn and keeps redeploys to "replace files."
- **Web Audio API** for everything audible. One `AudioContext`, one look-ahead scheduler, one gain node per active layer, one biquad path per head with crossfade, one master gain fixed at reference level after calibration.
- **Audio formats**: OGG/Vorbis primary, with M4A/AAC fallback for Safari **[verify current Safari OGG support at build time]**. Stems are mono, 8 kHz sample rate is sufficient for heart sounds (content is < 1 kHz); keep files small. Total v1 audio target: under 5 MB.
- **Persistence**: `localStorage` for tier, streak, spaced-repetition queue, missed-question seeds, calibration-done flag. Provide export/import as a JSON file so a learner can move progress between devices (no server).
- **Rendering**: chest is an inline SVG; head position is an SVG element moved with pointer events (`setPointerCapture`), converted to chest millimetres via the SVG CTM. Works with mouse, touch, and keyboard.
- **Mobile**: phone-usable is required (the program's learners will use phones). Portrait layout stacks chest above controls. Dragging must not scroll the page (`touch-action: none` on the chest).
- **Accessibility**: all controls labelled; keyboard operation per section 8; colour never the only cue (provenance pills carry text); respects `prefers-reduced-motion`.
- **Fonts and palette**: match Cairn's family for continuity — DM Sans; deep ocean blue base (`#215a7d`, `#17435f`, `#e6eef4`, `#1e4f6e`). **[inference — Brendan may want Gallop to have its own accent; ask before finalising.]**
- **Branding**: title "Gallop", descriptor "cardiac auscultation trainer" in the header, page `<title>`, and README. Logo direction: a stethoscope bell in the same angular, flat style as Cairn's Summit mark; a galloping-horse motif is acceptable if it stays restrained. Footer: mark, "Gallop", "© 2026 Brendan Hood. Code MIT, content CC BY 4.0." Link to Cairn in the footer; Cairn gets a reciprocal link.

---

## 13. Repository layout

```
gallop/
├── README.md                  # what it is, who it's for, the Barrett rationale, how to run, how to add a case
├── LICENSE                    # MIT
├── LICENSE-CONTENT            # CC BY 4.0
├── ATTRIBUTION.md
├── PROVENANCE.md
├── docs/
│   ├── HANDOVER.md            # this document
│   ├── CASE-AUTHORING.md      # how to write a case, the schema, the review checklist
│   └── ACCEPTANCE.md          # phase acceptance criteria and test script
├── site/
│   ├── index.html
│   ├── data/
│   │   └── cases.json
│   ├── audio/
│   │   ├── stems/             # synthesized and cut stems, one cycle each
│   │   ├── real/              # "hear the real thing" clips with record IDs in the filename
│   │   └── boundary/          # breath, bowel textures
│   └── img/
│       ├── chest.svg
│       └── logo.svg
├── tools/
│   ├── synth_stems.py         # generates synthesized stems into site/audio/stems
│   ├── cut_cycle.py           # extracts one clean cycle from a PhysioNet record using its .tsv segmentation
│   └── validate_cases.py      # schema check: provenance present, sources in range, reviewed flag, file paths exist
└── deploy/
    ├── docker-compose.yml
    ├── nginx.conf
    └── DEPLOY.md
```

---

## 14. Deployment

Same pattern as Cairn: `nginx:alpine` serving `site/`, bound to localhost, reverse-proxied by the host Caddy.

`deploy/docker-compose.yml`

```yaml
services:
  gallop:
    image: nginx:alpine
    container_name: gallop
    restart: unless-stopped
    ports:
      - "127.0.0.1:3642:80"
    volumes:
      - ../site:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
```

`deploy/nginx.conf`

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    gzip on;
    gzip_types text/html text/css application/javascript application/json image/svg+xml;

    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
    location ~* \.(ogg|m4a|wav)$ {
        add_header Cache-Control "public, max-age=2592000";
        add_header Accept-Ranges bytes;
    }
    location ~* \.(svg|png|json)$ {
        add_header Cache-Control "public, max-age=86400";
    }
    location = /healthz {
        return 200 "ok";
        add_header Content-Type text/plain;
    }
}
```

Host Caddy site block (Brendan adds this himself; hostname is his call — `gallop.yeomanops.com` is the assumed sibling of Cairn **[inference]**):

```
gallop.yeomanops.com {
    reverse_proxy 127.0.0.1:3642
}
```

Update workflow: replace files under `site/`, hard-refresh. No container restart needed because `index.html` is served no-cache.

---

## 15. Phases and acceptance criteria

### Phase 0 — sourcing (about a week, mostly elapsed time)

- Download CirCor v1.0.3 and CinC 2016 training set.
- Run `cut_cycle.py` against a dozen CirCor records with `Murmur: Present` and clear annotations; shortlist candidate murmur stems by ear.
- No vendor email needed: the manikin library is out of scope by decision.

**Done when**: `ATTRIBUTION.md` exists, both datasets are on disk, and a shortlist of at least 6 candidate recorded stems with record IDs is in `docs/`.

### Phase 1 — engine prototype

Deliverables: `site/index.html`, `site/data/cases.json` with cases `normal-72` and `as-ejection` (synthesized only), `site/img/chest.svg`, `tools/synth_stems.py`.

**Acceptance criteria** (all must pass on desktop Chrome/Firefox/Safari and on one iPhone and one Android phone):

1. Calibration sequence plays after a tap; master gain never changes afterwards.
2. Headphone check at 40 Hz works; "No" path leads to diaphragm-only practice without blocking.
3. Dragging the head produces a continuous change in mix with no clicks, gaps, or drift; the two cases stay phase-locked at every position.
4. Bell/diaphragm toggle is gapless (no audible click) and audibly changes the balance.
5. Heart rate slider 50–130 changes diastole length only; rate changes apply at the next cycle boundary.
6. Boundary sources are audible inferiorly, laterally, superiorly, and on the right chest; the tool is never silent anywhere on the silhouette.
7. Moving from the apex toward the axilla on `as-ejection` makes the murmur fade; moving toward the carotids keeps it audible.
8. Compare-to-normal hold works and releases cleanly.
9. Keyboard operation per section 8.
10. `validate_cases.py` passes on the shipped `cases.json`.
11. Page weight under 2 MB for Phase 1 assets.

### Phase 2 — case library

- Author the twelve v1 cases (section 10) with cards and quiz rationales; every layer carries provenance and a citation; every **[verify]** in this document is resolved or the assertion is removed.
- Tune spreads and stems by ear against the manikin; record the tuning session notes in `docs/`.
- Clinical reviewer listens to every case and signs off (`reviewed_by`, `review_date`).

**Done when**: 12 cases reviewed; `validate_cases.py` passes; the case card for each shows correct provenance pills; "hear the real thing" clips present for at least the four murmur cases.

### Phase 3 — quiz mode

- Tiers, mastery ladder, seven templates, generation and freshness rules, spaced-repetition queue, seeds, progress export/import.
- Ejection click, opening snap, pericardial rub layers added to the engine (cases may follow in a later pack).

**Done when**: a fresh learner can run Tier 1 to unlock Tier 2 in one sitting; a missed question demonstrably returns at 3, 10, and 30; replay-by-seed reproduces the exact question; no case + template repeats within 15.

### Phase 4 — field conditions and release

- Body-habitus scalar with muffle; Tier 4 real-recording clips; respiratory modulator wired to S2 splitting.
- Accessibility pass; `prefers-reduced-motion`; final copy pass in plain language (run the Luddite Lookover skill on all learner-facing text).
- CIPO/USPTO name check recorded in the README.
- Deploy; link from Cairn; announce to the MIH program with the "ear versus hands" framing from section 1.

---

## 16. Open items for Brendan

1. Tier advancement numbers (8 consecutive to advance, 4-in-10 to drop) — confirm or change.
2. Gallop's palette: reuse Cairn's blue, or its own accent?
3. Hostname.
4. Reviewer: who listens to the twelve cases and signs off? Needs a name before Phase 2 ends.
5. Whether a galloping-horse motif is welcome in the logo or the bell alone is the mark.
6. Body-habitus scalar in Phase 4 only, or pull it into Phase 2 as a per-case field with a default of 1.0 (cheap now, harder later)? Recommendation: add the field now, wire the effect later.

---

## 17. Source list

- Barrett MJ, Lacey CS, Sekara AE, Linden EA, Gracely EJ. Mastering cardiac murmurs: the power of repetition. Chest. 2004;126(2):470-475.
- Barrett MJ, Kuzma MA, Seto TC, Richards P, Mason D, Barrett DM, Gracely EJ. The power of repetition in mastering cardiac auscultation. Am J Med. 2006;119(1):73-75.
- Oliveira J, Renna F, Costa P, et al. The CirCor DigiScope Phonocardiogram Dataset (v1.0.3). PhysioNet. 2022. doi:10.13026/tshs-mw03
- Oliveira J, Renna F, Costa P, et al. The CirCor DigiScope Dataset: From Murmur Detection to Murmur Classification. IEEE J Biomed Health Inform. 2022;26(6):2524-2535. doi:10.1109/JBHI.2021.3137048
- Liu C, Springer D, Li Q, et al. An open access database for the evaluation of heart sound algorithms. Physiol Meas. 2016;37(12):2181-2213.
- Freeman AR, Levine SA. The clinical significance of the systolic murmur: a study of 1000 consecutive "non-cardiac" cases. Ann Intern Med. 1933;6:1371-1385.
- Dornbush S, Turnquest AE. Physiology, Heart Sounds. StatPearls. NBK541010.
- Healio "Learn the Heart" — S3 Heart Sound topic review (S3 vs split S2 discrimination by head and site).
- UMedic (University of Miami) cardiology course material — third heart sound module (~150 ms after S2).
- Bickley LS. Bates' Guide to Physical Examination and History Taking, 13th ed. **[verify page numbers at authoring]**
- Libby P, et al. Braunwald's Heart Disease, 12th ed. **[verify chapter at authoring]**

---

## 18. Kickoff prompt for the Claude Code session

Paste this as the first message after `claude` starts in the empty `gallop` repo:

```
Read docs/HANDOVER.md fully before doing anything. We are starting Phase 1 (section 15).
Build only the Phase 1 deliverables: site/index.html, site/data/cases.json with the two
synthesized cases, site/img/chest.svg, tools/synth_stems.py, tools/validate_cases.py.
Follow the audio model in section 5 exactly, including the source-field maths in 5.3 and
the boundary sources in 5.5. No frameworks, no build step. Write the acceptance test
script for Phase 1 into docs/ACCEPTANCE.md before writing the app, then build to it.
Do not author any case beyond the two named. Where the handover says [verify] or
[inference], leave the value as written and add it to a "Provisional values" list in
the README. Report each acceptance criterion as pass/fail when you are done.
```

*End of handover.*
