# Gallop — Phase 1 acceptance test script

Phase 1 is the engine prototype (handover §15). This script is the pass/fail
gate. Each numbered test maps to one acceptance criterion in the handover.
A criterion passes only when it passes on every platform in the matrix.

## Platform matrix

| Platform | Browser | Result |
|---|---|---|
| Desktop | Chrome (current) | |
| Desktop | Firefox (current) | |
| Desktop | Safari (current, macOS) | |
| iPhone | Safari | |
| Android | Chrome | |

Headphones on for every listening test. Phone tests must include one run on
the phone speaker for test 2 ("No" path).

## Setup

```
python tools/synth_stems.py        # regenerates site/audio/**
python tools/validate_cases.py     # must print OK
python -m http.server -d site 8000
```

Open `http://localhost:8000` (or the phone's LAN address). The page exposes
the engine as `window.gallop` for the console checks below.

## Automated checks (run once, any platform)

| # | Check | Command | Expected |
|---|---|---|---|
| A1 | Validator passes | `python tools/validate_cases.py` | exit 0, prints `OK` |
| A2 | Page weight | `python tools/validate_cases.py --weight` | total of `site/**` under 2 000 000 bytes |
| A3 | Never-silent field | included in A1 | validator reports minimum field ≥ 0.10 at every point on the silhouette grid |
| A4 | Radiation geometry | included in A1 | for `as-ejection`, murmur field at carotid point > field at apex > field at axilla |
| A6 | Engine generalisation (ROADMAP §1) | included in A5 | an in-test lung case on the posterior view: view bar and mirroring, respiratory clock at the set rate with changes landing on the breath boundary, discrete crackle events, Poisson bowel events, per-view sources silent on the other view, local attenuation lowers the muffle corner, habitus scales gain by 1 − 1/h, per-module quiz ladder and finding options |
| A5 | Engine smoke test | `node tools/smoke_engine.js` (header explains the two prerequisite processes) | 34/34 checks pass: fixed master gain, clock rate and look-ahead, field blend at A/M/axilla/carotids, boundary captions, 30 ms head crossfade, rate change, compare hold/release, keyboard, reset, no console errors |

## Listening tests

### T1 — Calibration and fixed master gain (criterion 1)

1. Load the page. Nothing should play before a tap.
2. Tap **Start**. A normal heart at 72 bpm plays at the reference level.
3. Adjust device volume until comfortably audible. Tap **Next**.
4. Console: `gallop.master.gain.value` → note the value (expected `0.7`).
5. Complete the rest of the session (change case, rate, head, intensity, compare). Re-check `gallop.master.gain.value` at the end.

**Pass:** audio starts only after the tap; the value in step 4 and step 5 is identical.

### T2 — Headphone check and the "No" path (criterion 2)

1. At the headphone step a 40 Hz tone plays with "Can you hear this?".
2. With headphones: tap **Yes**. Practice screen opens with bell and diaphragm both available.
3. Reload and repeat on a phone speaker (or unplug headphones): tap **No**.

**Pass:** on "No" a plain-language note explains that bell-range sounds are inaudible on this device, offers to continue on the diaphragm, and the practice screen opens without any blocking step. The bell button is disabled with a visible reason. "Start again with headphones" re-runs the check.

### T3 — Continuous drag, no clicks, phase lock (criterion 3)

1. Select `normal-72`. Drag the head slowly from the apex to the aortic area and back. Repeat with a fast drag.
2. Switch to `as-ejection` and repeat.
3. Hold the head still for 60 s on each case; watch the S1 marker flash in the UI against the sound.
4. Console: `gallop.cycleCount` increments once per beat; `gallop.nextCycle - gallop.ctx.currentTime` stays between 0 and one cycle length.

**Pass:** the balance of S1/S2 (and the murmur) changes smoothly with position; no clicks, pops, gaps, or stutter during drag; no timing drift over 60 s; switching case does not change the beat phase.

### T4 — Gapless bell/diaphragm toggle (criterion 4)

1. On `normal-72`, head at the apex. Press **Bell**, then **Diaphragm**, ten times at roughly one per second. Also use keys `B` and `D`.
2. On `as-ejection`, head at the aortic area, repeat.

**Pass:** no click or dropout on any toggle; on the bell S1 is fuller and lower, on the diaphragm S1/S2 are crisper and the murmur is clearer. Head icon changes.

### T5 — Heart rate slider (criterion 5)

1. On `normal-72`, move the rate slider from 50 to 130 and back in steps.
2. Console at 50 and at 130: `gallop.systole` → `0.3` both times.
3. Move the slider mid-cycle several times.

**Pass:** S1→S2 gap sounds the same at every rate; only the S2→S1 gap changes; no rate change ever produces a partial or doubled beat (changes land on the next cycle boundary).

### T6 — Boundary sources, never silent (criterion 6)

Drag the head to each of these and hold 5 s:

| Region | Where | Expect |
|---|---|---|
| Inferior | below the apex, over the epigastrium | bowel gurgles rise; heart is a distant thump |
| Lateral | past the anterior axillary line on the patient's left | breath sounds rise |
| Superior | above the clavicles, over the neck | breath sounds; on `as-ejection` the murmur is still there |
| Right chest | patient's right, off the sternum | breath sounds; distant heart |
| Every corner of the silhouette | four extreme corners | something is audible |

**Pass:** all five rows as expected; caption names the region; nothing is ever silent.

### T7 — Radiation on `as-ejection` (criterion 7)

1. Head at the aortic area (A). Confirm the murmur is loudest here.
2. Drag to the apex (M): murmur present but softer.
3. Continue to the axilla: murmur fades to nothing; breath sounds take over.
4. Return to A and drag up to the carotids (above the right clavicle): murmur remains clearly audible.

**Pass:** steps 3 and 4 as described. A4 confirms the geometry numerically.

### T8 — Compare to normal (criterion 8)

1. On `as-ejection`, head at A, rate 90, diaphragm. Press and hold **Compare to normal** (mouse, touch, and key `N`).
2. Release.

**Pass:** while held, the murmur disappears and a normal heart is heard at the same rate, position, and head with no beat skipped; on release the murmur returns with no click and no skipped beat.

### T9 — Keyboard operation (criterion 9)

With focus on the page (not in a form control):

| Key | Expect |
|---|---|
| ← → ↑ ↓ | head moves 5 mm per press; readout updates; mix changes |
| `B` / `D` | bell / diaphragm |
| `N` (hold) | compare to normal while held |
| Tab | reaches every control: case select, rate slider, head buttons, layer intensity controls, compare, reset, case card |

**Pass:** every row; every control has a visible label or `aria-label`.

### T10 — Validator (criterion 10)

A1 above.

### T11 — Page weight (criterion 11)

A2 above.

## Phase 3 — quiz mode (handover §15 "done when")

Beta note: `QUIZ_ALLOWS_DRAFTS` in `site/index.html` is `true`, so unreviewed
cases enter the quiz behind a visible beta label. Set it to `false` once a
reviewer has signed off, then re-run these.

| # | Check | How | Expected |
|---|---|---|---|
| Q1 | Tier 1 to Tier 2 in one sitting | Open Quiz, answer 8 in a row correctly | Ladder shows "Tier 2 unlocked"; Tier 2 button enabled; streak dots reset |
| Q2 | Missed question returns at 3, 10, 30 | Miss one question, note its template; keep answering | The same question (same case, template, rate, position) comes back as the 3rd, 10th and 30th question after the miss. Console: `gallopQuiz.state.queue` shows the dues. |
| Q3 | Replay by seed reproduces the question | Progress data → "Replay a missed question" | Same prompt, rate, head, start position, and clips; hint says it is not scored |
| Q4 | No case + template repeat within 15 | Console: `gallopQuiz.state.recent` | No duplicates when the pool allows; with two cases the generator falls back to the least-recent combination (documented ceiling) |
| Q5 | Drop rule | At Tier 2, miss 4 of 10 | "Back to Tier 1 for a bit. That's the point of the ladder." |
| Q6 | Rationale every time | Answer right and wrong | Short rationale shown both ways; "Why squared" expandable; case card revealed only after answering |
| Q7 | What-changed | Reach Tier 3, get a what-changed question | Hear A / Hear B swap one parameter only; head marker and head buttons hidden until answered |
| Q8 | Export / import | Export, reset progress, import the file | Ladder state restored |
| Q9 | No competition | Read the ladder | Tier, streak dots, recently missed findings only; no totals, percentages, or comparisons |

`node tools/smoke_engine.js` covers Q1, Q2 (the +3 return), Q3, Q5, Q6, Q7
and Q9 automatically.

## Reporting

Fill the matrix at the top, then list each criterion 1–11 as **pass** or **fail** with the platform(s) that failed and what was observed.
