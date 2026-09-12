# Gallop roadmap, v2

Agreed 12 September 2026 after colleague feedback on the beta. Build order
is engine generalisation, then bowel, then lungs, then the visual redesign.
Reviewer mode ships first because validation starts at the national
paramedic conference the week of 14 September.

## 0. Reviewer mode (shipped)

- Enabled by `?review` in the URL or the "Reviewer mode" footer link;
  remembered per browser.
- "Review this case" opens a non-modal panel (audio and dragging keep
  working) with ten fixed questions R1 to R10, a free-text "what would you
  change", reviewer name, role, optional email, and the engine state at the
  time (head, rate, position, headphone answer, user agent).
- Stored in the reviewer's browser under `gallop.reviews`. Leaves the device
  only by "Send by email" (mailto with the JSON in the body) or "Export all
  reviews" (JSON file). No backend, per the non-goals.
- Set `REVIEW_EMAIL` in `site/index.html` to the address reviews should go
  to before sending the link out. Share the link as
  `https://gallop.yeomanops.com/?review`.
- Reviews are keyed by `case_id`, and reviewed cases are never edited in
  place, so a review always refers to exactly the version heard.

## 1. Engine generalisation (shipped)

Small, mostly plumbing. Everything after this sits on it.

- **Clocks.** Each layer declares `clock`: `cardiac` (exists), `respiratory`
  (the existing hook becomes a scheduler: rate 8 to 30 per minute,
  inspiration about 40 % of the cycle, layers tagged inspiratory /
  expiratory / both with early / late windows), `stochastic` (Poisson events
  with a rate parameter, for bowel), or `loop` (boundary textures, exists).
- **Views.** A case declares `view`: `chest_anterior` (exists),
  `chest_posterior`, `abdomen`. Each view is an SVG, a landmark set, and a
  clamp box. Field maths unchanged. Lung cases offer front and back with a
  flip control.
- **Attenuation fields.** A per-case list of regions that scale every layer's
  gain down and pull a low-pass filter down as the head enters them. This is
  habitus made local: breast tissue, adipose, later pectus. The Phase 4
  habitus scalar becomes one attenuation field covering the whole view.
- Validator and `synth_stems.py` grow with the schema; `CASE-AUTHORING.md`
  documents the new fields.

## 2. Bowel module (shipped as drafts)

Smallest content load; proves the abdomen view and the stochastic clock.
Four draft cases: active, hyperactive, hypoactive, absent. Awaiting review.

- Abdomen view with four quadrants as landmarks.
- Findings: active, hyperactive, hypoactive, absent; pitch and character as
  descriptors; vascular bruit as a later layer.
- "Absent" means two minutes without a sound. The card says so; the tool
  does not pretend thirty seconds proves it.
- Quiz templates reuse identify, present/absent, localise, what changed.

## 3. Lung module (shipped as drafts)

The content-heavy one. Nine draft cases: normal, fine crackles, coarse
crackles, wheeze, rhonchi, stridor, diminished, absent, pleural rub. Every
characteristic is marked [verify] pending a reviewer. The side-to-side
compare template is not built yet; localise and present/absent cover it for
now.

- Anterior and posterior views with standard auscultation points.
- Findings in chart-note language: vesicular normal, diminished or absent
  over a region, fine crackles, coarse crackles, wheeze, rhonchi, stridor,
  pleural rub.
- Synthesis: crackles are short damped pops placed in the phase window;
  wheeze is a tonal component with slow pitch drift, expiratory; rhonchi is
  low band-limited noise with amplitude flutter; stridor is loud,
  inspiratory, with its source at the neck; rub is coarse noise on both
  phases. Absent is a negative field that suppresses the vesicular layer
  over a region.
- New quiz template: compare side to side ("Which side is diminished?").

## 4. Visual redesign (Layers and Blind shipped; illustrations open)

Can run in parallel with 2 and 3 once views are defined; touches SVGs only.
Layers and Blind are built against the placeholder silhouettes with rough
anatomy outlines; the illustrations and the overlay shapes are the open
item, and need an illustrator or a careful SVG session.

- Proper anatomical illustration for each view, replacing the placeholder
  silhouette. Worth an illustrator or a careful SVG session; it is what
  people see first.
- **Layers** toggle: ribs, lungs, and heart fade in under the skin so the
  learner sees why a sound is loud where it is. Three SVG groups and an
  opacity slider.
- **Blind** mode: landmarks and captions off; find the finding by ear, then
  reveal. A practice toggle plus a quiz variant.
- Logo, and a decision on naming: Gallop stays the product name with Heart,
  Lungs, and Belly modules inside it, unless decided otherwise before the
  illustration bakes it in.

## Standing constraints

- Findings, never diagnoses, in learner-facing text.
- No accounts, no server-side storage, no analytics, no leaderboards.
- Every layer carries provenance; every case needs a reviewer sign-off
  before it leaves draft.
- Content is the bottleneck. Each module needs a named clinical reviewer
  and time for Brendan's writing.
