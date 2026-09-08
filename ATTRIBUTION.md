# Attribution

Every stem in `site/data/cases.json` carries its own `provenance` block. This
file holds the full citations those blocks point to.

## Status

As of the Phase 1 build, every shipped stem is `synthesized` (CC BY 4.0,
Brendan Hood). No PhysioNet-derived audio is shipped yet. The dataset
citations below apply as soon as a `recorded_*` stem is added; the per-stem
record ID goes in `cases.json` so the chain stays traceable.

## Datasets

**CirCor DigiScope Phonocardiogram Dataset v1.0.3** (PhysioNet). Licence:
Open Data Commons Attribution License v1.0.

- Oliveira J, Renna F, Costa P, Nogueira D, Oliveira C, Ferreira C, Jorge A,
  Mattos S, Hatem T, Tavares T, Elola A, Rad AB, Sameni R, Clifford GD,
  Coimbra MT. The CirCor DigiScope Phonocardiogram Dataset (version 1.0.3).
  PhysioNet. 2022. https://doi.org/10.13026/tshs-mw03
- Oliveira J, Renna F, Costa P, et al. The CirCor DigiScope Dataset: From
  Murmur Detection to Murmur Classification. IEEE J Biomed Health Inform.
  2022;26(6):2524-2535. https://doi.org/10.1109/JBHI.2021.3137048

**PhysioNet/Computing in Cardiology Challenge 2016 database v1.0.0**
(PhysioNet). Licence: Open Data Commons Attribution License v1.0.

- Liu C, Springer D, Li Q, Moody B, Juan RA, Chorro FJ, Castells F,
  Roig JM, Silva I, Johnson AEW, Syed Z, Schmidt SE, Papadaniil CD,
  Hadjileontiadis L, Naseri H, Moukadem A, Dieterlen A, Brandt C, Tang H,
  Samieinasab M, Samieinasab MR, Sameni R, Mark RG, Clifford GD. An open
  access database for the evaluation of heart sound algorithms. Physiol Meas.
  2016;37(12):2181-2213. https://doi.org/10.1088/0967-3334/37/12/2181

**PhysioNet platform** (cite alongside either dataset):

- Goldberger AL, Amaral LAN, Glass L, Hausdorff JM, Ivanov PCh, Mark RG,
  Mietus JE, Moody GB, Peng C-K, Stanley HE. PhysioBank, PhysioToolkit, and
  PhysioNet: Components of a New Research Resource for Complex Physiologic
  Signals. Circulation. 2000;101(23):e215-e220.

## Teaching sources cited in case cards

- Barrett MJ, Lacey CS, Sekara AE, Linden EA, Gracely EJ. Mastering cardiac
  murmurs: the power of repetition. Chest. 2004;126(2):470-475.
- Barrett MJ, Kuzma MA, Seto TC, Richards P, Mason D, Barrett DM, Gracely EJ.
  The power of repetition in mastering cardiac auscultation. Am J Med.
  2006;119(1):73-75.
- Freeman AR, Levine SA. The clinical significance of the systolic murmur: a
  study of 1000 consecutive "non-cardiac" cases. Ann Intern Med.
  1933;6:1371-1385.
- Dornbush S, Turnquest AE. Physiology, Heart Sounds. StatPearls. NBK541010.
- Healio "Learn the Heart", S3 Heart Sound topic review.
- UMedic (University of Miami) cardiology course material, third heart sound
  module.
- Bickley LS. Bates' Guide to Physical Examination and History Taking, 13th
  ed. [page numbers to verify at authoring]
- Libby P, et al. Braunwald's Heart Disease, 12th ed. [chapter to verify at
  authoring]

## Not used

The program manikin's sound library is vendor intellectual property. It is
never recorded, copied, or redistributed. It is a tuning reference only. See
PROVENANCE.md.
