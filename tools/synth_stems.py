#!/usr/bin/env python3
"""Render every synth stem referenced by site/data/cases.json to WAV.

Stdlib only (no NumPy). 8 kHz mono 16-bit, deterministic (seeded per file).
    python tools/synth_stems.py          # render
    python tools/synth_stems.py --check  # self-check, no files written

Heart stems follow handover section 5.2: S1/S2 damped sinusoid + narrowband
noise burst, S3/S4 the same lower and softer, murmurs band-passed noise under
a shape envelope, boundary sounds looped textures. Lung and bowel stems follow
docs/ROADMAP.md sections 2 and 3. A stem's kind comes from stem.params.kind,
else from the layer type.
"""
import array
import json
import math
import os
import random
import sys
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
SR = 8000  # heart-sound content is < 1 kHz (handover section 12); lung content fits under 2 kHz

# ponytail: starting points, tuned by ear against the manikin. Listed in README "Provisional values".
PITCH_HZ = {"low": 100, "medium": 250, "high": 400}
QUALITY_Q = {"blowing": 1.4, "harsh": 0.6, "musical": 1.0}
TIMING = {"early": (0.03, 0.5), "mid": (0.12, 0.9), "late": (0.5, 0.97), "holo": (0.02, 0.98)}
ATTACK_MS = {"s1": 3, "s2": 2, "s3": 12, "s4": 12}


def _edge(u, w=0.06):
    return max(0.0, min(1.0, u / w, (1 - u) / w))


SHAPE = {
    "crescendo": lambda u: u * _edge(u),
    "decrescendo": lambda u: (1 - u) * _edge(u),
    "diamond": lambda u: math.sin(math.pi * u),
    "plateau": lambda u: _edge(u, 0.12),
}


def bandpass(x, f0, q):
    """RBJ constant-0 dB-peak band-pass biquad, direct form I."""
    w = 2 * math.pi * f0 / SR
    a = math.sin(w) / (2 * q)
    c = math.cos(w)
    a0 = 1 + a
    b0, b2, a1, a2 = a / a0, -a / a0, -2 * c / a0, (1 - a) / a0
    y = [0.0] * len(x)
    x1 = x2 = y1 = y2 = 0.0
    for i, v in enumerate(x):
        o = b0 * v + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, v, y1, o
        y[i] = o
    return y


def noise(n, rng):
    return [rng.uniform(-1, 1) for _ in range(n)]


def normalize(x, peak=0.9):
    m = max(abs(v) for v in x) or 1.0
    return [v * peak / m for v in x]


def hann(n):
    return [0.5 - 0.5 * math.cos(2 * math.pi * i / max(1, n - 1)) for i in range(n)]


# ---- heart ---------------------------------------------------------------------------

def burst(f0, decay_ms, attack_ms, rng):
    """Damped sinusoid plus narrowband noise. decay_ms = time to fall to e^-3."""
    n = int(SR * (2 * decay_ms + attack_ms) / 1000)
    tau = decay_ms / 1000 / 3
    ns = normalize(bandpass(noise(n, rng), f0, 2.0))
    out = []
    for i in range(n):
        t = i / SR
        env = min(1.0, t / (attack_ms / 1000)) * math.exp(-t / tau)
        out.append(env * (0.65 * math.sin(2 * math.pi * f0 * t) + 0.35 * ns[i]))
    return normalize(out)


def timing_window(timing):
    for k, win in TIMING.items():
        if timing.startswith(k):
            return win
    raise ValueError(f"unknown murmur timing {timing!r}")


def murmur(layer, duration_ms, rng):
    n = int(SR * duration_ms / 1000)
    a, b = timing_window(layer["timing"])
    f0 = PITCH_HZ[layer["pitch"]]
    quality = layer["quality"]
    shape = SHAPE[layer["shape"]]
    ns = normalize(bandpass(noise(n, rng), f0, QUALITY_Q[quality]))
    rough = normalize(bandpass(noise(n, rng), 12, 0.7)) if quality == "harsh" else None
    out = []
    for i in range(n):
        u = (i / n - a) / (b - a)
        if u <= 0 or u >= 1:
            out.append(0.0)
            continue
        v = ns[i]
        if rough:
            v *= 1 + 0.6 * rough[i]
        if quality == "musical":
            v += 0.3 * math.sin(2 * math.pi * f0 * i / SR)
        out.append(shape(u) * v)
    return normalize(out)


# ---- boundary loops -------------------------------------------------------------------

def breath_loop(rng):
    """4 s vesicular loop: inspiration louder, expiration softer, quiet floor so it never drops to zero."""
    n = SR * 4
    ns = normalize(bandpass(noise(n, rng), 220, 0.5))
    out = []
    for i in range(n):
        t = i / SR
        if t < 1.6:
            env = math.sin(math.pi * t / 1.6)
        elif t < 3.0:
            env = 0.5 * math.sin(math.pi * (t - 1.6) / 1.4)
        else:
            env = 0.0
        out.append((0.12 + 0.88 * env) * ns[i])
    return normalize(out)


def gurgle(rng, dur_s=None):
    """One downward-sweeping bowel gurgle."""
    dur = int((dur_s or rng.uniform(0.08, 0.25)) * SR)
    f_hi, f_lo = rng.uniform(250, 400), rng.uniform(70, 120)
    ph, out = 0.0, []
    for i in range(dur):
        u = i / dur
        ph += 2 * math.pi * (f_hi + (f_lo - f_hi) * u) / SR
        out.append(math.sin(math.pi * u) ** 2 * math.sin(ph))
    return out


def bowel_loop(rng):
    """4 s loop: five gurgles over a faint noise floor (boundary cue for chest views)."""
    n = SR * 4
    out = [0.0] * n
    for _ in range(5):
        start = int(rng.uniform(0.1, 3.5) * SR)
        for i, v in enumerate(gurgle(rng)):
            if start + i < n:
                out[start + i] += v
    floor = normalize(bandpass(noise(n, rng), 150, 0.5))
    return normalize([o + 0.08 * f for o, f in zip(out, floor)])


# ---- lung (respiratory clock; the engine cuts each stem at the phase end) ----------------

def vesicular(phase, rng):
    """Normal breath sound for one phase: inspiration 2.0 s, softer expiration 2.6 s. [verify spectrum 100-500 Hz]"""
    n = int(SR * (2.0 if phase == "in" else 2.6))
    ns = normalize(bandpass(noise(n, rng), 220 if phase == "in" else 180, 0.5))
    env = hann(n)
    scale = 1.0 if phase == "in" else 0.55
    return normalize([scale * e * v for e, v in zip(env, ns)], peak=0.9 * scale)


def bronchial(phase, rng):
    """Harsher, higher, louder on expiration: the sound of consolidation or the trachea. [verify]"""
    n = int(SR * (1.6 if phase == "in" else 2.2))
    ns = normalize(bandpass(noise(n, rng), 500, 0.8))
    env = hann(n)
    return normalize([e * v for e, v in zip(env, ns)])


def crackle(kind, rng):
    """One crackle. Fine: short, high, like hair rubbed by the ear. Coarse: longer, lower, bubbly. [verify]"""
    if kind == "fine":
        n, f0, tau = int(SR * 0.012), 650.0, 0.003
    else:
        n, f0, tau = int(SR * 0.035), 260.0, 0.010
    ns = normalize(bandpass(noise(n, rng), f0, 1.5))
    out = []
    for i in range(n):
        t = i / SR
        env = min(1.0, t / 0.001) * math.exp(-t / tau)
        out.append(env * (0.5 * math.sin(2 * math.pi * f0 * t) + 0.5 * ns[i]))
    return normalize(out)


def wheeze(rng):
    """1.5 s polyphonic expiratory wheeze: three drifting tones with vibrato under a hann envelope. [verify 400-1600 Hz]"""
    n = int(SR * 1.5)
    tones = [(rng.uniform(380, 460), 1.0), (rng.uniform(600, 700), 0.6), (rng.uniform(880, 1000), 0.35)]
    env = hann(n)
    out = []
    ph = [0.0] * len(tones)
    for i in range(n):
        t = i / SR
        v = 0.0
        for k, (f, amp) in enumerate(tones):
            ph[k] += 2 * math.pi * f * (1 + 0.04 * math.sin(2 * math.pi * 5.5 * t) - 0.06 * t / 1.5) / SR
            v += amp * math.sin(ph[k])
        out.append(env[i] * v)
    breathy = normalize(bandpass(noise(n, rng), 500, 0.6))
    return normalize([o + 0.25 * e * b for o, e, b in zip(out, env, breathy)])


def rhonchi(rng):
    """1.5 s low snoring rumble: 150 Hz band with 20 Hz amplitude flutter. [verify]"""
    n = int(SR * 1.5)
    ns = normalize(bandpass(noise(n, rng), 150, 2.0))
    env = hann(n)
    return normalize([e * v * (0.6 + 0.4 * math.sin(2 * math.pi * 20 * i / SR)) for i, (e, v) in enumerate(zip(env, ns))])


def stridor(rng):
    """1.2 s harsh inspiratory tone plus noise, loud and high: upper airway. [verify]"""
    n = int(SR * 1.2)
    ns = normalize(bandpass(noise(n, rng), 900, 1.0))
    env = hann(n)
    ph = 0.0
    out = []
    for i in range(n):
        ph += 2 * math.pi * 720 * (1 + 0.02 * math.sin(2 * math.pi * 7 * i / SR)) / SR
        out.append(env[i] * (0.6 * math.sin(ph) + 0.6 * ns[i]))
    return normalize(out)


def lung_rub(rng):
    """0.8 s pleural rub: coarse grating noise with a 25 Hz creak. [verify]"""
    n = int(SR * 0.8)
    ns = normalize(bandpass(noise(n, rng), 300, 0.4))
    env = hann(n)
    creak = [0.5 + 0.5 * math.copysign(1, math.sin(2 * math.pi * 25 * i / SR)) for i in range(n)]
    return normalize([e * v * (0.3 + 0.7 * c) for e, v, c in zip(env, ns, creak)])


# ---- bowel (stochastic clock: the engine schedules one stem per event) --------------------

def bowel_gurgle(rng):
    return normalize(gurgle(rng, dur_s=0.22))


def bowel_tinkle(rng):
    """High-pitched tinkle of a hyperactive bowel: short, near-tonal. [verify]"""
    n = int(SR * 0.09)
    ph, out = 0.0, []
    for i in range(n):
        u = i / n
        ph += 2 * math.pi * (900 - 350 * u) / SR
        out.append(math.sin(math.pi * u) * math.sin(ph))
    return normalize(out)


KINDS = {
    "breath_loop": lambda rng, p: breath_loop(rng),
    "bowel_loop": lambda rng, p: bowel_loop(rng),
    "vesicular_in": lambda rng, p: vesicular("in", rng),
    "vesicular_out": lambda rng, p: vesicular("out", rng),
    "bronchial_in": lambda rng, p: bronchial("in", rng),
    "bronchial_out": lambda rng, p: bronchial("out", rng),
    "crackle_fine": lambda rng, p: crackle("fine", rng),
    "crackle_coarse": lambda rng, p: crackle("coarse", rng),
    "wheeze": lambda rng, p: wheeze(rng),
    "rhonchi": lambda rng, p: rhonchi(rng),
    "stridor": lambda rng, p: stridor(rng),
    "lung_rub": lambda rng, p: lung_rub(rng),
    "bowel_gurgle": lambda rng, p: bowel_gurgle(rng),
    "bowel_tinkle": lambda rng, p: bowel_tinkle(rng),
    "burst": lambda rng, p: burst(p["f0"], p["decay_ms"], p.get("attack_ms", 3), rng),
}


def render(case, layer, stem):
    p = stem.get("params", {})
    kind = p.get("kind")
    ltype = layer["type"]
    rng = random.Random(stem["file"])
    if kind in KINDS:
        return KINDS[kind](rng, p)
    if ltype in ATTACK_MS:
        return burst(p["f0"], p["decay_ms"], p.get("attack_ms", ATTACK_MS[ltype]), rng)
    if ltype == "murmur":
        clock = case["clock"]
        # ponytail: diastolic murmurs render at the case's own bpm and are not stretched by the engine
        dur = clock["systole_ms"] if layer["phase"] == "systolic" else 60000 / clock["bpm"] - clock["systole_ms"]
        return murmur(layer, dur, rng)
    if ltype == "boundary_breath":
        return breath_loop(rng)
    if ltype == "boundary_bowel":
        return bowel_loop(rng)
    raise ValueError(f"no synth for layer type {ltype!r} / kind {kind!r}")


def write_wav(path, x):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pcm = array.array("h", (int(max(-1.0, min(1.0, v)) * 32767) for v in x))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def stems_of(layer):
    if layer.get("stem"):
        yield layer["stem"]
    for s in (layer.get("stems") or {}).values():
        yield s if isinstance(s, dict) else {"kind": "synth", "file": s, "params": {"kind": os.path.splitext(os.path.basename(s))[0]}}


def main():
    with open(os.path.join(SITE, "data", "cases.json"), encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    done = set()
    for case in cases:
        for layer in case["layers"]:
            for stem in stems_of(layer):
                if stem.get("kind", "synth") != "synth" or stem["file"] in done:
                    continue
                path = os.path.join(SITE, stem["file"])
                write_wav(path, render(case, layer, stem))
                done.add(stem["file"])
                print(f"{stem['file']}  {os.path.getsize(path)} B")
    print(f"{len(done)} stems")


def check():
    rng = random.Random(0)
    s1 = burst(90, 60, 3, rng)
    assert abs(max(abs(v) for v in s1) - 0.9) < 1e-9, "burst not normalised"
    assert len(s1) == int(SR * 0.123), "burst length"
    m = murmur({"timing": "midsystolic", "shape": "diamond", "pitch": "medium", "quality": "harsh"}, 300, rng)
    assert len(m) == SR * 300 // 1000
    assert all(v == 0.0 for v in m[: int(len(m) * 0.12)]), "murmur must be silent before its window"
    assert all(v == 0.0 for v in m[int(len(m) * 0.9) + 1 :]), "murmur must be silent after its window"
    assert max(abs(v) for v in m[len(m) // 2 - 200 : len(m) // 2 + 200]) > 0.5, "diamond peaks mid-window"
    b = breath_loop(rng)
    assert len(b) == SR * 4 and max(abs(v) for v in b[SR * 3 : SR * 4]) > 0.02, "breath floor keeps the loop audible"
    g = bowel_loop(rng)
    assert len(g) == SR * 4 and max(abs(v) for v in g) > 0.8
    vi, vo = vesicular("in", rng), vesicular("out", rng)
    assert len(vi) < len(vo) and max(abs(v) for v in vo) < max(abs(v) for v in vi), "expiration longer and softer than inspiration"
    assert abs(vi[0]) < 1e-6 and abs(vi[-1]) < 1e-6, "phase stems start and end at zero"
    for kind in ("crackle_fine", "crackle_coarse", "wheeze", "rhonchi", "stridor", "lung_rub", "bowel_gurgle", "bowel_tinkle"):
        x = KINDS[kind](rng, {})
        assert 0.5 < max(abs(v) for v in x) <= 0.9 and len(x) > 0, kind
    assert len(crackle("fine", rng)) < len(crackle("coarse", rng)), "fine crackles are shorter than coarse"
    print("synth_stems self-check OK")


if __name__ == "__main__":
    check() if "--check" in sys.argv else main()
