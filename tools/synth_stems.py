#!/usr/bin/env python3
"""Render every `stem.kind == "synth"` layer in site/data/cases.json to WAV.

Stdlib only (no NumPy). 8 kHz mono 16-bit, deterministic (seeded per file).
    python tools/synth_stems.py          # render
    python tools/synth_stems.py --check  # self-check, no files written
Handover section 5.2 "Synthesis approach": S1/S2 damped sinusoid + narrowband
noise burst, S3/S4 the same lower and softer, murmurs band-passed noise under a
shape envelope, boundary sounds looped textures.
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
SR = 8000  # heart-sound content is < 1 kHz (handover section 12)

# ponytail: starting points, tuned by ear against the manikin in Phase 2. Listed in README "Provisional values".
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


def breath(rng):
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


def bowel(rng):
    """4 s loop: five downward-sweeping gurgles over a faint noise floor."""
    n = SR * 4
    out = [0.0] * n
    for _ in range(5):
        start = int(rng.uniform(0.1, 3.5) * SR)
        dur = int(rng.uniform(0.08, 0.25) * SR)
        f_hi, f_lo = rng.uniform(250, 400), rng.uniform(70, 120)
        ph = 0.0
        for i in range(dur):
            u = i / dur
            ph += 2 * math.pi * (f_hi + (f_lo - f_hi) * u) / SR
            j = start + i
            if j < n:
                out[j] += math.sin(math.pi * u) ** 2 * math.sin(ph)
    floor = normalize(bandpass(noise(n, rng), 150, 0.5))
    return normalize([o + 0.08 * f for o, f in zip(out, floor)])


def render(case, layer):
    kind = layer["type"]
    p = layer["stem"].get("params", {})
    rng = random.Random(layer["stem"]["file"])
    if kind in ATTACK_MS:
        return burst(p["f0"], p["decay_ms"], p.get("attack_ms", ATTACK_MS[kind]), rng)
    if kind == "murmur":
        clock = case["clock"]
        # ponytail: diastolic murmurs render at the case's own bpm and are not stretched by the engine; none ship in Phase 1
        dur = clock["systole_ms"] if layer["phase"] == "systolic" else 60000 / clock["bpm"] - clock["systole_ms"]
        return murmur(layer, dur, rng)
    if kind == "boundary_breath":
        return breath(rng)
    if kind == "boundary_bowel":
        return bowel(rng)
    raise ValueError(f"no synth for layer type {kind!r}")


def write_wav(path, x):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pcm = array.array("h", (int(max(-1.0, min(1.0, v)) * 32767) for v in x))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    with open(os.path.join(SITE, "data", "cases.json"), encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    done = set()
    for case in cases:
        for layer in case["layers"]:
            stem = layer["stem"]
            if stem["kind"] != "synth" or stem["file"] in done:
                continue
            path = os.path.join(SITE, stem["file"])
            write_wav(path, render(case, layer))
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
    b = breath(rng)
    assert len(b) == SR * 4 and max(abs(v) for v in b[SR * 3 : SR * 4]) > 0.02, "breath floor keeps the loop audible"
    g = bowel(rng)
    assert len(g) == SR * 4 and max(abs(v) for v in g) > 0.8
    print("synth_stems self-check OK")


if __name__ == "__main__":
    check() if "--check" in sys.argv else main()
