#!/usr/bin/env python3
"""Procedural audio generator for Veleho.

Synthesises every sound effect and ambient music loop used by the game from
scratch (oscillators, noise, filters, envelopes, FM, additive synthesis,
synthetic convolution reverb).  No samples are used.  Output is deterministic:
every sound draws its randomness from its own fixed seed.

    python tools/audio/gen_audio.py              # write everything + analysis
    python tools/audio/gen_audio.py --only jump land
    python tools/audio/gen_audio.py --no-music   # SFX only
    python tools/audio/gen_audio.py --analyze    # only analyse existing files

Format: 16-bit PCM, mono, 22050 Hz.  SFX are peak-normalised to -3 dBFS,
music to -8 dBFS.  Loops (music, levitate, portal_hum, potion_pour) are rendered on a
circular timeline (note tails, echoes and reverb wrap around into the head),
so they are exactly periodic.  Loop files store one extra trailing sample equal
to the first one plus a RIFF 'smpl' chunk (forward loop 0..N), so Godot's WAV
importer ("Detect From WAV") loops them seamlessly, with correct interpolation
across the seam.
"""

from __future__ import annotations

import argparse
import struct
import sys
import time
import wave
import zlib
from pathlib import Path

import numpy as np

SR = 22050
NYQ = SR / 2.0
TAU = 2.0 * np.pi

ROOT = Path(__file__).resolve().parents[2]
SFX_DIR = ROOT / "assets" / "sfx"
MUSIC_DIR = ROOT / "assets" / "music"

SFX_PEAK_DB = -3.0
MUSIC_PEAK_DB = -8.0


# =============================================================================
# Basic helpers
# =============================================================================

def ns(seconds: float) -> int:
    """Seconds -> sample count."""
    return int(round(seconds * SR))


def tvec(n: int) -> np.ndarray:
    return np.arange(n) / SR


def farr(v, n: int) -> np.ndarray:
    """Broadcast a scalar or array parameter to a float array of length n."""
    a = np.asarray(v, dtype=np.float64)
    if a.ndim == 0:
        return np.full(n, float(a))
    if len(a) != n:
        raise ValueError(f"parameter length {len(a)} != {n}")
    return a


def db(x: float) -> float:
    return 10.0 ** (x / 20.0)


def seed_of(name: str) -> int:
    return zlib.crc32(name.encode("utf-8")) & 0x7FFFFFFF


def rng_for(name: str) -> np.random.Generator:
    return np.random.default_rng(seed_of(name))


NOTE_OFFS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(note) -> int:
    """'C#4' / 'Db4' / int -> MIDI note number (A4 = 69)."""
    if isinstance(note, (int, np.integer)):
        return int(note)
    s = note.strip()
    base = NOTE_OFFS[s[0].upper()]
    i = 1
    while i < len(s) and s[i] in "#b":
        base += 1 if s[i] == "#" else -1
        i += 1
    octave = int(s[i:])
    return base + 12 * (octave + 1)


def hz(note) -> float:
    if isinstance(note, float):
        return note
    return 440.0 * 2.0 ** ((midi(note) - 69) / 12.0)


def place(buf: np.ndarray, start: int, sig: np.ndarray, wrap: bool = False) -> None:
    """Add sig into buf at sample offset start (clipped, or wrapped circularly)."""
    n = len(buf)
    if wrap:
        start %= n
        pos = 0
        while pos < len(sig):
            s = (start + pos) % n
            ln = min(len(sig) - pos, n - s)
            buf[s:s + ln] += sig[pos:pos + ln]
            pos += ln
        return
    if start >= n:
        return
    if start < 0:
        sig = sig[-start:]
        start = 0
    ln = min(len(sig), n - start)
    if ln > 0:
        buf[start:start + ln] += sig[:ln]


def fit(x: np.ndarray, n: int) -> np.ndarray:
    """Pad with zeros / truncate to exactly n samples."""
    if len(x) >= n:
        return x[:n].copy()
    return np.concatenate([x, np.zeros(n - len(x))])


def next_fast(n: int) -> int:
    """Smallest 2^a*3^b*5^c >= n (fast FFT length)."""
    best = 1 << int(np.ceil(np.log2(max(n, 1))))
    f5 = 1
    while f5 < best:
        f35 = f5
        while f35 < best:
            q = f35
            while q < n:
                q *= 2
            best = min(best, q)
            f35 *= 3
        f5 *= 5
    return best


# =============================================================================
# Oscillators
# =============================================================================

def phase_of(freq, n: int, phase0: float = 0.0) -> np.ndarray:
    """Running phase in cycles for a (possibly time varying) frequency in Hz."""
    f = farr(freq, n)
    ph = np.empty(n)
    ph[0] = 0.0
    np.cumsum(f[:-1] / SR, out=ph[1:])
    return ph + phase0


def _blep(t: np.ndarray, dt: np.ndarray) -> np.ndarray:
    """PolyBLEP residual for a unit step at phase 0 (t in [0,1))."""
    y = np.zeros_like(t)
    m = t < dt
    x = t[m] / dt[m]
    y[m] = x + x - x * x - 1.0
    m = t > 1.0 - dt
    x = (t[m] - 1.0) / dt[m]
    y[m] = x * x + x + x + 1.0
    return y


def sine(freq, n: int, phase0: float = 0.0) -> np.ndarray:
    return np.sin(TAU * phase_of(freq, n, phase0))


def saw(freq, n: int, phase0: float = 0.0) -> np.ndarray:
    f = farr(freq, n)
    t = phase_of(f, n, phase0) % 1.0
    dt = np.clip(np.abs(f) / SR, 1e-9, 0.5)
    return 2.0 * t - 1.0 - _blep(t, dt)


def square(freq, n: int, duty=0.5, phase0: float = 0.0) -> np.ndarray:
    f = farr(freq, n)
    d = np.clip(farr(duty, n), 0.02, 0.98)
    t = phase_of(f, n, phase0) % 1.0
    dt = np.clip(np.abs(f) / SR, 1e-9, 0.5)
    y = np.where(t < d, 1.0, -1.0)
    y += _blep(t, dt) - _blep((t - d) % 1.0, dt)
    return y - (2.0 * d - 1.0)  # remove DC of asymmetric duty


def tri(freq, n: int, phase0: float = 0.0) -> np.ndarray:
    t = (phase_of(freq, n, phase0) + 0.25) % 1.0
    return 1.0 - 4.0 * np.abs(t - 0.5)


def fm(freq, n: int, ratio: float, index, phase0: float = 0.0) -> np.ndarray:
    """Two-operator FM (phase modulation): sin(c + I(t)*sin(ratio*c))."""
    ph = phase_of(freq, n, phase0)
    return np.sin(TAU * ph + farr(index, n) * np.sin(TAU * ratio * ph))


def white(n: int, rng) -> np.ndarray:
    return rng.uniform(-1.0, 1.0, n)


def shaped_noise(n: int, rng, slope_db_oct: float = -3.0, lo: float = 20.0,
                 hi: float | None = None) -> np.ndarray:
    """Noise with a spectral slope (-3 dB/oct pink, -6 brown), circular, unit RMS."""
    x = rng.standard_normal(n)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    f[0] = f[1] if n > 1 else 1.0
    H = (f / 1000.0) ** (slope_db_oct / 6.0206)
    H *= 1.0 / np.sqrt(1.0 + (lo / f) ** 4)
    if hi:
        H *= 1.0 / np.sqrt(1.0 + (f / hi) ** 4)
    H[0] = 0.0
    y = np.fft.irfft(X * H, n)
    return y / (np.sqrt(np.mean(y ** 2)) + 1e-12)


def pink(n: int, rng, **kw) -> np.ndarray:
    return shaped_noise(n, rng, -3.0, **kw)


def brown(n: int, rng, **kw) -> np.ndarray:
    return shaped_noise(n, rng, -6.0, **kw)


def smooth_random(n: int, rng, rate: float, circular: bool = False) -> np.ndarray:
    """Band-limited random control signal (~-1..1) varying at about `rate` Hz."""
    pad = 0 if circular else ns(2.0 / max(rate, 0.1))
    m = n + pad
    X = np.fft.rfft(rng.standard_normal(m))
    f = np.fft.rfftfreq(m, 1.0 / SR)
    X *= np.exp(-0.5 * (f / rate) ** 2)
    X[0] = 0.0
    y = np.fft.irfft(X, m)[:n]
    return y / (np.max(np.abs(y)) + 1e-12)


def lfo_hz(approx: float, n: int) -> float:
    """Nearest frequency that completes an integer number of cycles in n samples."""
    k = max(1, int(round(approx * n / SR)))
    return k * SR / n


def bin_hz(f: float, n: int) -> float:
    """Round an oscillator frequency so it is exactly periodic over n samples."""
    return max(1, int(round(f * n / SR))) * SR / n


# =============================================================================
# Envelopes
# =============================================================================

def env_pts(points, n: int, curve: float = 1.0) -> np.ndarray:
    """Piecewise-linear envelope through (time, value) points; optional power curve."""
    ts = [p[0] for p in points]
    vs = [p[1] for p in points]
    e = np.interp(tvec(n), ts, vs)
    if curve != 1.0:
        e = np.sign(e) * np.abs(e) ** curve
    return e


def env_exp(n: int, tau: float, attack: float = 0.001, delay: float = 0.0) -> np.ndarray:
    """Linear attack then exponential decay with time constant tau."""
    t = tvec(n) - delay
    e = np.exp(-np.maximum(t - attack, 0.0) / tau)
    if attack > 0:
        e *= np.clip(t / attack, 0.0, 1.0)
    else:
        e *= (t >= 0)
    return e


def env_adsr(n: int, a: float, d: float, s: float, r: float, hold: float | None = None) -> np.ndarray:
    """ADSR; release starts at `hold` seconds (default: so it ends at n)."""
    total = n / SR
    if hold is None:
        hold = max(total - r, a + d)
    t = tvec(n)
    e = np.where(t < a, t / max(a, 1e-6),
                 np.where(t < a + d, 1.0 - (1.0 - s) * (t - a) / max(d, 1e-6), s))
    rel = np.clip((t - hold) / max(r, 1e-6), 0.0, 1.0)
    return e * (1.0 - rel) ** 2


def sweep_exp(n: int, f0: float, f1: float, tau: float) -> np.ndarray:
    """Exponential glide f0 -> f1 with time constant tau (seconds)."""
    return f1 + (f0 - f1) * np.exp(-tvec(n) / tau)


def sweep_log(n: int, f0: float, f1: float, shape: float = 1.0) -> np.ndarray:
    """Geometric sweep f0 -> f1 across n samples (shape > 1 = slow start)."""
    u = np.linspace(0.0, 1.0, n) ** shape
    return f0 * (f1 / f0) ** u


# =============================================================================
# Filters
# =============================================================================

def svf(x: np.ndarray, fc, q=0.707, mode: str = "lp") -> np.ndarray:
    """Topology-preserving state-variable filter (Simper); fc / q may vary per sample.

    mode: lp, bp (unity peak), hp, notch, peak (lp - hp), or a mix like "lp+bp".
    """
    n = len(x)
    fcv = np.clip(farr(fc, n), 5.0, NYQ * 0.92)
    k = 1.0 / np.maximum(farr(q, n), 0.05)
    g = np.tan(np.pi * fcv / SR)
    a1 = 1.0 / (1.0 + g * (g + k))
    a2 = g * a1
    a3 = g * a2
    xs, a1l, a2l, a3l = x.tolist(), a1.tolist(), a2.tolist(), a3.tolist()
    lp = [0.0] * n
    bp = [0.0] * n
    ic1 = ic2 = 0.0
    for i in range(n):
        v3 = xs[i] - ic2
        v1 = a1l[i] * ic1 + a2l[i] * v3
        v2 = ic2 + a2l[i] * ic1 + a3l[i] * v3
        ic1 = 2.0 * v1 - ic1
        ic2 = 2.0 * v2 - ic2
        lp[i] = v2
        bp[i] = v1
    lpa = np.array(lp)
    bpa = np.array(bp)
    if mode == "lp":
        return lpa
    if mode == "bp":
        return bpa * k
    hpa = x - k * bpa - lpa
    if mode == "hp":
        return hpa
    if mode == "notch":
        return x - k * bpa
    if mode == "peak":
        return lpa - hpa
    if mode == "lp+bp":
        return lpa + bpa * k
    raise ValueError(mode)


def _mag(f: np.ndarray, lo, hi, order: float) -> np.ndarray:
    H = np.ones_like(f)
    fz = np.maximum(f, 1e-6)
    if hi:
        H *= 1.0 / np.sqrt(1.0 + (fz / hi) ** (2 * order))
    if lo:
        H *= 1.0 / np.sqrt(1.0 + (lo / fz) ** (2 * order))
    return H


def ffilt(x: np.ndarray, lo=None, hi=None, order: float = 2.0, circular: bool = False,
          peaks=(), pad: float = 0.25) -> np.ndarray:
    """Zero-phase Butterworth-magnitude band limit (+ optional resonant peaks).

    peaks: iterable of (freq, q, gain_db).  circular=True treats x as periodic.
    """
    n = len(x)
    m = n if circular else next_fast(n + ns(pad))
    X = np.fft.rfft(x, m)
    f = np.fft.rfftfreq(m, 1.0 / SR)
    H = _mag(f, lo, hi, order)
    for pf, pq, pg in peaks:
        fz = np.maximum(f, 1e-6)
        bump = 1.0 / np.sqrt(1.0 + pq * pq * (fz / pf - pf / fz) ** 2)
        H *= 1.0 + (db(pg) - 1.0) * bump
    return np.fft.irfft(X * H, m)[:n]


def formant_bank(x: np.ndarray, formants, q: float = 8.0) -> np.ndarray:
    """Parallel band-pass bank; formants = list of (fc array/scalar, gain)."""
    out = np.zeros(len(x))
    for fc, g in formants:
        out += g * svf(x, fc, q, "bp")
    return out


def dc_block(x: np.ndarray, fc: float = 18.0) -> np.ndarray:
    return ffilt(x, lo=fc, order=1)


# =============================================================================
# Effects
# =============================================================================

def sat(x: np.ndarray, drive: float = 1.0) -> np.ndarray:
    """Soft saturation that keeps small signals at roughly unity gain."""
    if drive <= 0:
        return x
    return np.tanh(drive * x) / drive


def crush(x: np.ndarray, bits: float = 8, hold: int = 1) -> np.ndarray:
    y = x[(np.arange(len(x)) // hold) * hold] if hold > 1 else x
    q = 2.0 ** (bits - 1)
    return np.round(y * q) / q


def vdelay(x: np.ndarray, delay_samples, circular: bool = False) -> np.ndarray:
    """Variable (fractional) delay line with linear interpolation."""
    n = len(x)
    pos = np.arange(n) - farr(delay_samples, n)
    i0 = np.floor(pos).astype(np.int64)
    fr = pos - i0
    if circular:
        a = x[i0 % n]
        b = x[(i0 + 1) % n]
    else:
        xp = np.concatenate([x, [0.0]])
        ia = np.where(i0 >= 0, i0, n)
        ib = np.where(i0 + 1 >= 0, i0 + 1, n)
        a = xp[np.minimum(ia, n)]
        b = xp[np.minimum(ib, n)]
    return a * (1.0 - fr) + b * fr


def chorus(x: np.ndarray, rate: float = 0.6, depth_ms: float = 4.0, base_ms: float = 12.0,
           mix_amt: float = 0.5, circular: bool = False, voices: int = 2) -> np.ndarray:
    n = len(x)
    out = x * (1.0 - mix_amt * 0.5)
    for v in range(voices):
        r = lfo_hz(rate * (1.0 + 0.37 * v), n) if circular else rate * (1.0 + 0.37 * v)
        d = (base_ms + depth_ms * np.sin(TAU * r * tvec(n) + v * 2.1)) * SR / 1000.0
        out = out + (mix_amt / voices) * vdelay(x, d, circular)
    return out


def echo(x: np.ndarray, delay: float, feedback: float = 0.4, damp: float = 3000.0,
         wet: float = 0.35, circular: bool = False, tail: float = 0.0) -> np.ndarray:
    """Feedback delay computed exactly in the frequency domain.

    Y = X * g H e^{-iwD} / (1 - g H e^{-iwD})  (wet only), H = low-pass damping.
    """
    n = len(x)
    m = n if circular else next_fast(n + ns(tail))
    X = np.fft.rfft(x, m)
    f = np.fft.rfftfreq(m, 1.0 / SR)
    H = 1.0 / np.sqrt(1.0 + (f / damp) ** 2)
    D = delay * SR
    z = feedback * H * np.exp(-2j * np.pi * f * D / SR)
    wet_sig = np.fft.irfft(X * (H * np.exp(-2j * np.pi * f * D / SR)) / (1.0 - z), m)
    out = fit(x, m) + wet * wet_sig
    return out if circular else out[: n + ns(tail)]


def make_ir(t60: float = 1.5, length: float | None = None, predelay: float = 0.012,
            damp: float = 0.6, bright: float = 9000.0, seed: int = 7,
            early: int = 8) -> np.ndarray:
    """Synthetic room impulse response: band-wise exponentially decaying noise."""
    rng = np.random.default_rng(seed)
    L = length if length is not None else min(t60 * 1.15, 9.0)
    n = ns(L)
    t = tvec(n)
    X = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    edges = [350.0, 1400.0, 4000.0]
    t60s = [t60 * 1.15, t60, t60 * (1.0 - 0.45 * damp), t60 * (1.0 - 0.75 * damp)]
    lps = [1.0 / (1.0 + (np.maximum(f, 1e-6) / e) ** 4) for e in edges]
    masks = [lps[0], lps[1] - lps[0], lps[2] - lps[1], 1.0 - lps[2]]
    tone = 1.0 / np.sqrt(1.0 + (f / bright) ** 2)
    ir = np.zeros(n)
    for msk, tt in zip(masks, t60s):
        band = np.fft.irfft(X * msk * tone, n)
        ir += band * np.exp(-6.9078 * t / max(tt, 0.02))
    # soft diffuse onset
    ir *= np.clip(t / 0.02, 0.0, 1.0) ** 1.5
    # early reflections (sparse taps, a few times the diffuse level)
    ref = 6.0 * np.std(ir[: ns(0.08)]) + 1e-9
    for _ in range(early):
        tt = rng.uniform(0.004, 0.06)
        i = ns(tt)
        if i < n:
            ir[i] += rng.uniform(0.4, 1.0) * rng.choice([-1, 1]) * np.exp(-tt / 0.05) * ref
    ir = np.concatenate([np.zeros(ns(predelay)), ir])
    # fade the very end
    fl = min(len(ir) // 8, ns(0.3))
    ir[-fl:] *= np.linspace(1.0, 0.0, fl) ** 2
    return ir / (np.sqrt(np.sum(ir ** 2)) + 1e-12)


def convolve(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    m = len(x) + len(ir) - 1
    nf = next_fast(m)
    return np.fft.irfft(np.fft.rfft(x, nf) * np.fft.rfft(ir, nf), nf)[:m]


def circ_convolve(x: np.ndarray, ir: np.ndarray) -> np.ndarray:
    n = len(x)
    irp = np.zeros(n)
    for s in range(0, len(ir), n):  # fold long IRs
        seg = ir[s:s + n]
        irp[: len(seg)] += seg
    return np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(irp), n)


def reverb(x: np.ndarray, t60: float = 0.8, wet: float = 0.2, dry: float = 1.0,
           circular: bool = False, **kw) -> np.ndarray:
    ir = make_ir(t60, **kw)
    if circular:
        return dry * x + wet * circ_convolve(x, ir)
    y = convolve(x, ir)
    return dry * fit(x, len(y)) + wet * y


def room(x: np.ndarray, t60: float = 0.35, wet: float = 0.12, **kw) -> np.ndarray:
    """Small room ambience to give SFX some body (truncated by the caller's duration)."""
    kw.setdefault("predelay", 0.006)
    kw.setdefault("seed", 11)
    return reverb(x, t60=t60, wet=wet, **kw)


# =============================================================================
# SFX building blocks
# =============================================================================

def U(x: np.ndarray) -> np.ndarray:
    """Normalise a (stationary) layer to unit RMS so mix weights are meaningful."""
    return x / (np.sqrt(np.mean(x ** 2)) + 1e-12)


def P(x: np.ndarray) -> np.ndarray:
    """Normalise a (sparse / transient) layer to unit peak."""
    return x / (np.max(np.abs(x)) + 1e-12)


def crackle(n: int, rng, rate, decay: float = 0.0012, lo: float = 1500.0,
            hi: float = 9000.0, amp_pow: float = 2.0) -> np.ndarray:
    """Sparse random clicks/pops; rate (events per second) may vary over time."""
    r = farr(rate, n)
    hits = rng.random(n) < np.clip(r / SR, 0.0, 1.0)
    amps = rng.uniform(0.0, 1.0, n) ** amp_pow * rng.choice([-1.0, 1.0], n)
    imp = np.where(hits, amps, 0.0)
    kl = max(ns(decay * 6.0), 2)
    kern = rng.standard_normal(kl) * np.exp(-tvec(kl) / decay)
    y = convolve(imp, kern)[:n]
    return ffilt(y, lo, hi)


def partials(n: int, f0: float, ratios, amps, decays, rng=None, attack: float = 0.0015,
             beat: float = 0.0) -> np.ndarray:
    """Additive inharmonic struck tone (bells, chimes, metal, glass)."""
    t = tvec(n)
    out = np.zeros(n)
    for i, (ra, a, d) in enumerate(zip(ratios, amps, decays)):
        f = f0 * ra
        if f >= NYQ * 0.95:
            continue
        ph = rng.uniform(0.0, 1.0) if rng is not None else 0.0
        part = np.sin(TAU * (f * t + ph))
        if beat:
            part = 0.5 * part + 0.5 * np.sin(TAU * ((f + beat * (1 + 0.3 * i)) * t + ph * 1.7))
        out += a * part * np.exp(-t / d)
    if attack > 0:
        out *= np.clip(t / attack, 0.0, 1.0)
    return out


def bubble(f0: float, dur: float, rise: float = 1.0) -> np.ndarray:
    """Water bubble blip: sine whose pitch rises quickly while it decays."""
    n = ns(dur)
    t = tvec(n)
    f = f0 * 2.0 ** (rise * t / dur)
    return sine(f, n) * env_exp(n, dur * 0.33, attack=0.0015) * smooth_env(n, 0.0, dur * 0.3)


def bubbles(n: int, rng, count: int, t0: float, t1: float, flo: float, fhi: float,
            dlo: float = 0.02, dhi: float = 0.05, fall: float = 0.6) -> np.ndarray:
    out = np.zeros(n)
    for _ in range(count):
        st = rng.uniform(t0, t1)
        a = rng.uniform(0.4, 1.0) * (1.0 - fall * (st - t0) / max(t1 - t0, 1e-6))
        f0 = np.exp(rng.uniform(np.log(flo), np.log(fhi)))
        place(out, ns(st), a * bubble(f0, rng.uniform(dlo, dhi), rng.uniform(0.6, 1.3)))
    return out


def grain(rng, dur: float, fc: float, q: float) -> np.ndarray:
    """Short filtered noise burst (gravel, stone clack, sand)."""
    n = max(ns(dur), 8)
    g = white(n, rng) * env_exp(n, dur * 0.3, attack=0.0005)
    g = np.concatenate([g, np.zeros(ns(min(0.02, 2.0 * q / fc + 0.002)))])  # room to ring out
    return svf(g, fc, q, "bp") * smooth_env(len(g), 0.0, len(g) / SR * 0.3)


def grains(n: int, rng, count: int, t0: float, t1: float, flo: float, fhi: float,
           dlo: float = 0.003, dhi: float = 0.012, q: float = 2.0,
           density=None) -> np.ndarray:
    """Scatter `count` grains between t0 and t1 (density = [(t, weight), ...])."""
    out = np.zeros(n)
    ts = np.linspace(t0, t1, 64)
    if density is None:
        w = np.ones_like(ts)
    else:
        w = np.interp(ts, [p[0] for p in density], [p[1] for p in density])
    w = w / w.sum()
    for _ in range(count):
        st = rng.choice(ts, p=w) + rng.uniform(0.0, (t1 - t0) / 64.0)
        fc = np.exp(rng.uniform(np.log(flo), np.log(fhi)))
        a = rng.uniform(0.15, 1.0) ** 1.5
        place(out, ns(st), a * P(grain(rng, rng.uniform(dlo, dhi), fc, q)))
    return out


def thud(n: int, f0: float, f1: float, tau_f: float, tau_a: float, attack: float = 0.0015) -> np.ndarray:
    return U(sine(sweep_exp(n, f0, f1, tau_f), n)) * env_exp(n, tau_a, attack)


def jitter_freq(n: int, rng, lo: float, hi: float, step: float) -> np.ndarray:
    """Sample-and-hold random frequency (electric arcs)."""
    h = max(ns(step), 1)
    vals = rng.uniform(lo, hi, n // h + 2)
    return np.repeat(vals, h)[:n]


SFX: dict[str, dict] = {}


def sfx(name: str, dur: float, fade: float = 0.02, loop: bool = False):
    def deco(fn):
        SFX[name] = {"fn": fn, "dur": dur, "fade": fade, "loop": loop}
        return fn
    return deco


# =============================================================================
# SFX: weapons / spells
# =============================================================================

@sfx("shoot_spark", 0.15)
def _shoot_spark(r):
    n = ns(0.16)
    t = tvec(n)
    f = 560.0 + 2400.0 * np.exp(-t / 0.024)
    f = f * np.where(t > 0.04, 1.26, 1.0)  # sfxr-style arpeggio kick
    duty = 0.12 + 0.38 * (1.0 - np.exp(-t / 0.04))
    tone = 0.6 * U(square(f, n, duty)) + 0.4 * U(saw(f * 1.007, n))
    tone *= 0.65 + 0.35 * sine(f * 0.31 + 40.0, n)  # ring-mod buzz
    body = 0.45 * U(sine(f * 0.5, n))
    x = (tone + body) * env_exp(n, 0.05, 0.0015)
    x += 0.7 * U(ffilt(white(n, r), 3000, 10000)) * env_exp(n, 0.005, 0.0005)
    x += 0.35 * P(crackle(n, r, 700 * np.exp(-t / 0.04), decay=0.0006, lo=2500))
    x = svf(x, 8500 * np.exp(-t / 0.07) + 1800, 0.9)
    x = sat(x * 0.9, 1.2)
    return room(x, 0.25, 0.1)


@sfx("shoot_fire", 0.35)
def _shoot_fire(r):
    n = ns(0.38)
    fc = env_pts([(0, 350), (0.05, 2600), (0.16, 1500), (0.38, 600)], n)
    whoosh = U(svf(white(n, r), fc, 0.8, "bp"))
    roar = U(ffilt(pink(n, r), 80, 700)) * (1.0 + 0.6 * smooth_random(n, r, 35))
    crk = P(crackle(n, r, env_pts([(0, 0), (0.03, 260), (0.3, 50)], n), decay=0.001, lo=1200, hi=7000))
    body = thud(n, 150, 60, 0.05, 0.07, 0.004)
    amp = env_pts([(0, 0), (0.018, 1.0), (0.08, 0.8), (0.38, 0)], n, 1.6)
    x = (1.0 * whoosh + 0.45 * roar) * amp + 0.5 * body + 0.6 * crk * amp
    x = sat(x * 0.8, 1.3)
    return room(x, 0.35, 0.12)


@sfx("shoot_orb", 0.25)
def _shoot_orb(r):
    n = ns(0.26)
    t = tvec(n)
    f = 230.0 + 420.0 * (1.0 - np.exp(-t / 0.022)) + 90.0 * np.exp(-t / 0.05) * np.sin(TAU * 16.0 * t)
    f = f * (1.0 - 0.12 * np.clip((t - 0.12) / 0.14, 0.0, 1.0))
    src = U(sine(f, n)) + 0.45 * U(square(f, n, 0.3)) + 0.3 * U(tri(f * 2.0, n))
    fc = np.minimum(f * (1.5 + 5.0 * (1.0 - np.exp(-t / 0.03))), 6000.0)
    x = svf(src, fc, 2.2)
    x += 0.55 * U(sine(f * 0.5, n))
    x *= env_pts([(0, 0), (0.004, 1), (0.05, 0.85), (0.26, 0)], n, 1.8)
    x = sat(x * 0.7, 1.2)
    return room(x, 0.3, 0.1)


@sfx("shoot_ice", 0.25)
def _shoot_ice(r):
    n = ns(0.3)
    t = tvec(n)
    f0 = 1760.0
    chime = partials(n, f0, [1, 2.76, 5.40, 8.93], [1, 0.55, 0.35, 0.2],
                     [0.16, 0.09, 0.05, 0.03], rng=r, beat=4.0)
    chime2 = np.zeros(n)
    place(chime2, ns(0.02), partials(n, f0 * 1.5, [1, 2.76, 5.40], [0.7, 0.4, 0.25],
                                       [0.12, 0.07, 0.04], rng=r, beat=5.0))
    hiss = U(ffilt(white(n, r), 4500, 10000)) * env_exp(n, 0.05, 0.002)
    swish = U(svf(white(n, r), sweep_exp(n, 9000, 3500, 0.05), 3.0, "bp")) * env_exp(n, 0.07, 0.003)
    ticks = P(crackle(n, r, 400 * np.exp(-t / 0.03), decay=0.0004, lo=4000, hi=10000))
    x = 0.9 * P(chime) + 0.5 * P(chime2) + 0.3 * hiss + 0.25 * swish + 0.25 * ticks
    return room(x, 0.6, 0.2, bright=10000)


@sfx("shoot_acid", 0.3)
def _shoot_acid(r):
    n = ns(0.32)
    t = tvec(n)
    f = sweep_exp(n, 210, 105, 0.09)
    src = U(saw(f, n)) + 0.6 * U(square(f * 1.005, n, 0.4))
    blorp = U(svf(src, sweep_exp(n, 2600, 380, 0.07), 5.0))
    blorp *= env_pts([(0, 0), (0.006, 1), (0.09, 0.6), (0.3, 0)], n, 1.5)
    blorp *= 1.0 + 0.25 * np.sin(TAU * 22.0 * t)
    bub = P(bubbles(n, r, 9, 0.01, 0.24, 450, 1400, 0.025, 0.05))
    gurgle = U(ffilt(white(n, r), 150, 900)) * (0.5 + 0.5 * smooth_random(n, r, 25)) * env_exp(n, 0.1, 0.01)
    x = 0.9 * blorp + 0.6 * bub + 0.2 * gurgle
    x = sat(x * 0.8, 1.3)
    return room(x, 0.35, 0.12)


@sfx("shoot_bomb", 0.25)
def _shoot_bomb(r):
    n = ns(0.27)
    thump = thud(n, 175, 68, 0.03, 0.05)
    click = U(ffilt(white(n, r), 200, 2500)) * env_exp(n, 0.008, 0.0005)
    throw = U(svf(white(n, r), env_pts([(0, 500), (0.07, 1600), (0.12, 900)], n), 1.2, "bp"))
    throw *= env_pts([(0, 0), (0.02, 1), (0.12, 0)], n)
    fuse_env = env_pts([(0, 0), (0.05, 0), (0.08, 1), (0.27, 0.8)], n)
    fuse = U(ffilt(white(n, r), 3500, 9000)) * (0.65 + 0.35 * smooth_random(n, r, 60)) * fuse_env
    sparks = P(crackle(n, r, 220, decay=0.0007, lo=2500)) * fuse_env
    x = 1.0 * thump + 0.5 * click + 0.35 * throw + 0.22 * fuse + 0.35 * sparks
    x = sat(x, 1.2)
    return room(x, 0.3, 0.08)


@sfx("shoot_missile", 0.35)
def _shoot_missile(r):
    n = ns(0.36)
    t = tvec(n)
    f = sweep_log(n, 420, 1900, 1.4)
    vib = 1.0 + (0.004 + 0.02 * t / 0.36) * np.sin(TAU * phase_of(9.0 + 14.0 * t / 0.36, n))
    fv = f * vib
    tone = (U(sine(fv, n)) + 0.5 * U(sine(fv * 1.007, n)) + 0.35 * U(sine(fv * 1.5, n))
            + 0.2 * U(tri(fv * 2.0, n)))
    air = U(svf(white(n, r), fv * 1.1, 5.0, "bp"))
    whoosh = U(svf(white(n, r), sweep_log(n, 600, 4000), 1.0, "bp"))
    amp = env_pts([(0, 0), (0.025, 0.8), (0.28, 1.0), (0.36, 0)], n)
    x = (0.6 * tone + 0.35 * air + 0.22 * whoosh) * amp * (1.0 + 0.15 * np.sin(TAU * 31.0 * t))
    return room(x, 0.4, 0.14)


@sfx("shoot_meteor", 0.6)
def _shoot_meteor(r):
    n = ns(0.62)
    sub = thud(n, 90, 46, 0.18, 0.2, 0.012)
    rumble = U(ffilt(brown(n, r), 40, 420)) * (0.6 + 0.4 * smooth_random(n, r, 14))
    rumble *= env_pts([(0, 0), (0.03, 1), (0.25, 0.7), (0.62, 0)], n, 1.3)
    roar = U(svf(pink(n, r), env_pts([(0, 250), (0.1, 1300), (0.62, 450)], n), 0.9, "bp"))
    roar *= env_pts([(0, 0), (0.06, 1), (0.62, 0)], n, 1.5)
    body = U(svf(pink(n, r), env_log([(0, 140), (0.12, 380), (0.62, 160)], n), 1.6, "bp"))
    body *= env_pts([(0, 0), (0.02, 1), (0.3, 0.5), (0.62, 0)], n, 1.3)
    crk = P(crackle(n, r, env_pts([(0, 0), (0.05, 120), (0.6, 20)], n), decay=0.0015, lo=800, hi=5000))
    crk *= env_pts([(0, 1), (0.25, 0.6), (0.62, 0.1)], n)
    crack = U(ffilt(white(n, r), 300, 4000)) * env_exp(n, 0.012, 0.001)
    x = 0.7 * sub + 0.9 * rumble + 0.5 * roar + 0.6 * body + 0.3 * crk + 0.5 * crack
    x = sat(x * 0.8, 1.5)
    return room(x, 0.8, 0.14)


@sfx("shoot_drill", 0.3)
def _shoot_drill(r):
    n = ns(0.31)
    t = tvec(n)
    f = 95.0 + 135.0 * (1.0 - np.exp(-t / 0.05)) + 6.0 * np.sin(TAU * 13.0 * t)
    src = U(saw(f, n)) + 0.6 * U(square(f * 2.01, n, 0.3))
    grind = 0.6 + 0.4 * np.tanh(4.0 * np.sin(TAU * phase_of(42.0 + 20.0 * t, n)))
    grit = U(ffilt(white(n, r), 800, 5000)) * (0.5 + 0.5 * sine(f, n))
    x = (0.8 * src + 0.45 * grit) * grind
    x = svf(x, 2600, 1.3) + 0.5 * svf(x, 1250, 3.0, "bp")
    pk = np.max(np.abs(x)) + 1e-9
    x = 0.7 * x + 0.3 * crush(x / pk, bits=6, hold=2) * pk
    x *= env_pts([(0, 0), (0.012, 1), (0.25, 0.9), (0.31, 0)], n)
    x = sat(x * 0.6, 1.4)
    return room(x, 0.25, 0.08)


@sfx("shoot_water", 0.3)
def _shoot_water(r):
    n = ns(0.32)
    t = tvec(n)
    swoosh = U(svf(white(n, r), env_pts([(0, 700), (0.08, 3200), (0.32, 1300)], n), 1.3, "bp"))
    swoosh *= env_pts([(0, 0), (0.03, 1), (0.12, 0.7), (0.32, 0)], n, 1.4)
    splash = U(ffilt(white(n, r), 1800, 8000)) * env_exp(n, 0.035, 0.002, delay=0.01)
    bub = P(bubbles(n, r, 8, 0.02, 0.25, 1000, 2600, 0.015, 0.035))
    glug = U(sine(320.0 + 220.0 * (1.0 - np.exp(-t / 0.03)), n)) * env_exp(n, 0.03, 0.002)
    x = 0.8 * swoosh + 0.4 * splash + 0.5 * bub + 0.35 * glug
    x = ffilt(x, hi=8500)
    return room(x, 0.3, 0.1)


@sfx("shoot_quake", 0.5)
def _shoot_quake(r):
    n = ns(0.52)
    sub = thud(n, 80, 42, 0.1, 0.15, 0.003)
    harm = sat(sub * 3.0, 1.0)
    earth = U(ffilt(brown(n, r), 50, 500)) * (0.7 + 0.3 * smooth_random(n, r, 18))
    earth *= env_pts([(0, 0), (0.006, 1), (0.15, 0.5), (0.52, 0)], n, 1.4)
    rubble = P(grains(n, r, 22, 0.03, 0.42, 150, 1400, 0.006, 0.02, q=1.5,
                      density=[(0.03, 1.0), (0.42, 0.1)]))
    rubble *= env_pts([(0, 1), (0.2, 0.6), (0.5, 0.15)], n)
    crack = U(ffilt(white(n, r), 100, 2500)) * env_exp(n, 0.015, 0.0008)
    x = 0.75 * sub + 0.45 * harm + 1.0 * earth + 0.45 * rubble + 0.6 * crack
    x = sat(x * 0.8, 1.3)
    return room(x, 0.5, 0.1)


@sfx("shoot_enemy", 0.3)
def _shoot_enemy(r):
    n = ns(0.32)
    f = sweep_exp(n, 360, 105, 0.08)
    src = U(saw(f, n)) + U(saw(f * 1.013, n)) + 0.6 * U(saw(f * 0.7071, n))
    src *= 0.55 + 0.45 * sine(47.0, n)
    x = svf(src, sweep_exp(n, 3200, 380, 0.07), 3.0)
    x = U(x) * env_pts([(0, 0), (0.003, 1), (0.08, 0.6), (0.32, 0)], n, 1.6)
    x += 0.3 * U(ffilt(white(n, r), 400, 3000)) * env_exp(n, 0.02, 0.001)
    x = sat(x * 0.8, 1.5)
    return room(x, 0.6, 0.2, bright=3000)


@sfx("lightning", 0.4)
def _lightning(r):
    n = ns(0.42)
    t = tvec(n)
    snap = U(ffilt(white(n, r), 800, 10000)) * env_exp(n, 0.006, 0.0003)
    crack_tone = U(sine(sweep_exp(n, 2600, 500, 0.006), n)) * env_exp(n, 0.01, 0.0005)
    crk = P(crackle(n, r, 2500.0 * np.exp(-t / 0.07) + 40.0, decay=0.0004, lo=1500, hi=10000))
    crk *= 0.12 + 0.88 * np.exp(-t / 0.07)
    fj = jitter_freq(n, r, 70, 150, 0.008)
    gate = 0.5 + 0.5 * np.tanh(3.0 * smooth_random(n, r, 60))
    buzz = U(svf(U(square(fj, n, 0.3)), 1800, 1.5, "bp")) * env_exp(n, 0.09, 0.002) * gate
    boom = thud(n, 120, 55, 0.04, 0.08, 0.002)
    x = 1.2 * snap + 0.4 * crack_tone + 0.6 * crk + 0.4 * buzz + 0.35 * boom
    x = sat(x * 0.8, 1.5)
    return room(x, 0.7, 0.18)


def env_log(points, n: int) -> np.ndarray:
    """Geometric (log-domain) interpolation through (time, value>0) points: pitch glides."""
    ts = [p[0] for p in points]
    vs = [np.log(p[1]) for p in points]
    return np.exp(np.interp(tvec(n), ts, vs))


def ping(f: float, dur: float, bright: float = 0.3) -> np.ndarray:
    """Tiny glassy sparkle note."""
    n = ns(dur)
    t = tvec(n)
    x = np.sin(TAU * f * t)
    if 2.0 * f < NYQ * 0.9:
        x += bright * np.sin(TAU * 2.0 * f * t) * np.exp(-t / (dur * 0.12))
    return x * env_exp(n, dur * 0.3, 0.001) * smooth_env(n, 0.0, dur * 0.25)


def pings(n: int, rng, count: int, t0: float, t1: float, freqs, dlo: float = 0.05,
          dhi: float = 0.12, density=None, amp_lo: float = 0.3) -> np.ndarray:
    out = np.zeros(n)
    ts = np.linspace(t0, t1, 64)
    w = np.ones_like(ts) if density is None else np.interp(
        ts, [p[0] for p in density], [p[1] for p in density])
    w = w / w.sum()
    for _ in range(count):
        st = rng.choice(ts, p=w) + rng.uniform(0.0, (t1 - t0) / 64.0)
        f = float(rng.choice(freqs))
        place(out, ns(st), rng.uniform(amp_lo, 1.0) * ping(f, rng.uniform(dlo, dhi)))
    return out


def sample_hold(x: np.ndarray, hold) -> np.ndarray:
    """Time-varying sample-and-hold (progressive 'dissolve' / downsampling)."""
    n = len(x)
    h = np.maximum(farr(hold, n).astype(int), 1)
    out = np.empty_like(x)
    i = 0
    while i < n:
        k = int(h[i])
        out[i:i + k] = x[i]
        i += k
    return out


# =============================================================================
# SFX: staff, explosions, terrain, melee
# =============================================================================

@sfx("staff_charge", 1.2, fade=0.03)
def _staff_charge(r):
    n = ns(1.2)
    t = tvec(n)
    u = t / 1.2
    f0 = 110.0 * 2.0 ** (u ** 1.3)  # one octave, accelerating
    trem = 1.0 - 0.3 * (0.5 + 0.5 * np.sin(TAU * phase_of(4.0 + 14.0 * u ** 1.5, n)))
    src = (U(saw(f0, n)) + 0.8 * U(saw(f0 * 1.006, n)) + 0.6 * U(saw(f0 * 1.5 * 0.997, n))
           + 0.5 * U(sine(f0 * 2.0, n)))
    fc = 250.0 * 2.0 ** (4.5 * u ** 1.2)
    hum = U(svf(src, fc, 1.2 + 2.0 * u)) * trem
    energy = U(svf(white(n, r), fc * 1.5, 2.0, "bp")) * u ** 2
    notes = [hz(m) for m in ("A6", "C#7", "E7", "F#7", "A7", "B7")]
    spark = pings(n, r, 30, 0.1, 1.15, notes, 0.04, 0.09, density=[(0.1, 0.1), (1.15, 1.0)])
    amp = 0.25 + 0.75 * u ** 1.4
    x = (0.8 * hum + 0.18 * energy) * amp + 0.22 * P(spark) * (0.3 + 0.7 * u)
    x = sat(x * 0.8, 1.2)
    return room(x, 0.6, 0.15)


@sfx("staff_release", 0.5, fade=0.04)
def _staff_release(r):
    n = ns(0.52)
    boom = thud(n, 130, 42, 0.06, 0.16, 0.002)
    mid = thud(n, 240, 90, 0.04, 0.07, 0.002)
    whoosh = U(svf(white(n, r), sweep_exp(n, 6500, 220, 0.09), 0.9))
    whoosh *= env_pts([(0, 0), (0.004, 1), (0.1, 0.45), (0.52, 0)], n, 1.5)
    zap = U(svf(saw(sweep_exp(n, 950, 140, 0.04), n), 3000, 0.8)) * env_exp(n, 0.05, 0.001)
    x = 1.0 * boom + 0.5 * mid + 0.75 * whoosh + 0.4 * zap
    x = sat(x * 0.9, 2.0)
    return room(x, 0.9, 0.18)


@sfx("explosion_small", 0.6, fade=0.06)
def _explosion_small(r):
    n = ns(0.65)
    sub = thud(n, 95, 38, 0.08, 0.13, 0.001)
    body = U(svf(white(n, r), sweep_exp(n, 6000, 320, 0.07), 0.7))
    body *= env_pts([(0, 0), (0.002, 1), (0.06, 0.5), (0.3, 0.15), (0.65, 0)], n, 1.3)
    rumble = U(ffilt(brown(n, r), 30, 300)) * env_exp(n, 0.16, 0.004)
    debris = P(grains(n, r, 28, 0.04, 0.55, 300, 3500, 0.003, 0.012, q=2.0,
                      density=[(0.04, 1.0), (0.55, 0.08)]))
    debris *= env_pts([(0, 1), (0.3, 0.55), (0.65, 0.15)], n)
    click = U(ffilt(white(n, r), 1000, 9000)) * env_exp(n, 0.003, 0.0002)
    x = 1.0 * sub + 0.9 * body + 0.5 * rumble + 0.3 * debris + 0.35 * click
    x = sat(x * 0.9, 2.5)
    return room(x, 0.7, 0.12)


@sfx("explosion_big", 1.4, fade=0.15)
def _explosion_big(r):
    n = ns(1.45)
    sub = thud(n, 68, 26, 0.2, 0.38, 0.002)
    sub2 = sat(sub * 2.5, 1.0)
    blast = np.zeros(n)
    for k, (dt, a) in enumerate([(0.0, 1.0), (0.035, 0.7), (0.09, 0.5)]):
        m = n - ns(dt)
        b = U(svf(white(m, r), sweep_exp(m, 4800, 180, 0.12 + 0.03 * k), 0.7))
        b *= env_pts([(0, 0), (0.002, 1), (0.08, 0.5), (0.5, 0.12), (1.3, 0)], m, 1.4)
        place(blast, ns(dt), a * b)
    rumble = U(ffilt(brown(n, r), 25, 280)) * (0.6 + 0.4 * smooth_random(n, r, 8))
    rumble *= env_pts([(0, 0), (0.05, 1), (0.5, 0.55), (1.45, 0)], n, 1.5)
    debris = P(grains(n, r, 70, 0.12, 1.3, 250, 3000, 0.004, 0.02, q=1.8,
                      density=[(0.12, 1.0), (0.5, 0.6), (1.3, 0.05)]))
    debris *= env_pts([(0, 1), (0.5, 0.7), (1.4, 0.2)], n)
    crk = P(crackle(n, r, env_pts([(0, 0), (0.1, 150), (1.2, 10)], n), decay=0.002, lo=500, hi=4000))
    crk *= env_pts([(0, 1), (0.4, 0.6), (1.4, 0.1)], n)
    x = 1.0 * sub + 0.4 * sub2 + 0.9 * blast + 0.7 * rumble + 0.3 * debris + 0.2 * crk
    x = sat(x * 0.8, 2.5)
    return room(x, 1.4, 0.2)


@sfx("dig", 0.15, fade=0.015)
def _dig(r):
    n = ns(0.16)
    crunch = P(grains(n, r, 9, 0.0, 0.11, 700, 3800, 0.004, 0.012, q=1.6,
                      density=[(0.0, 1.0), (0.11, 0.25)]))
    first = np.zeros(n)
    place(first, 0, P(grain(r, 0.012, 1400, 1.0)))
    th = thud(n, 170, 80, 0.03, 0.035, 0.001)
    dirt = U(ffilt(white(n, r), 150, 1800)) * env_exp(n, 0.03, 0.001)
    x = 0.8 * crunch + 0.5 * first + 0.5 * th + 0.4 * dirt
    pk = np.max(np.abs(x)) + 1e-9
    x = 0.75 * x + 0.25 * crush(x / pk, bits=5, hold=2) * pk
    x = sat(x, 1.5)
    return room(x, 0.2, 0.06)


@sfx("crumble", 0.6, fade=0.06)
def _crumble(r):
    n = ns(0.62)
    dens = [(0.0, 0.2), (0.08, 1.0), (0.35, 0.8), (0.6, 0.1)]
    rocks = P(grains(n, r, 55, 0.0, 0.58, 250, 2200, 0.006, 0.025, q=4.0, density=dens))
    pebbles = P(grains(n, r, 120, 0.0, 0.58, 1500, 6000, 0.002, 0.006, q=1.5, density=dens))
    sand = U(ffilt(pink(n, r), 1800, 7500)) * (0.7 + 0.3 * smooth_random(n, r, 40))
    sand *= env_pts([(0, 0), (0.05, 1), (0.4, 0.75), (0.62, 0)], n, 1.2)
    low = U(ffilt(brown(n, r), 40, 250)) * env_pts([(0, 0), (0.05, 1), (0.62, 0)], n)
    x = 0.6 * rocks + 0.45 * pebbles + 0.25 * sand + 0.3 * low
    return room(x, 0.4, 0.1)


@sfx("sword_swing", 0.2, fade=0.02)
def _sword_swing(r):
    n = ns(0.21)
    src = pink(n, r)
    fc = env_log([(0, 450), (0.07, 2400), (0.21, 700)], n)
    air = U(svf(src, fc, 1.4, "bp"))
    whistle = U(svf(src, fc * 1.35, 14.0, "bp"))
    amp = env_pts([(0, 0), (0.06, 1), (0.21, 0)], n, 2.0)
    x = (0.85 * air + 0.25 * whistle) * amp
    x = ffilt(x, 150, 7000)
    return room(x, 0.2, 0.05)


@sfx("sword_hit", 0.25, fade=0.03)
def _sword_hit(r):
    n = ns(0.27)
    impact = U(ffilt(white(n, r), 300, 6000)) * env_exp(n, 0.01, 0.0004)
    th = thud(n, 190, 80, 0.025, 0.04, 0.001)
    metal = partials(n, 1340, [1, 1.47, 2.09, 2.56, 3.37, 4.18], [1, 0.7, 0.55, 0.45, 0.3, 0.25],
                     [0.16, 0.1, 0.08, 0.06, 0.045, 0.035], rng=r, beat=7.0)
    slc = U(svf(white(n, r), sweep_exp(n, 3000, 8000, 0.02), 2.0, "bp"))
    slc *= env_pts([(0, 0), (0.003, 1), (0.045, 0)], n)
    x = 0.7 * impact + 0.6 * th + 0.55 * P(metal) + 0.4 * slc
    x = sat(x, 1.6)
    return room(x, 0.45, 0.12)


# =============================================================================
# SFX: creatures
# =============================================================================

@sfx("hit_enemy", 0.12, fade=0.015)
def _hit_enemy(r):
    n = ns(0.13)
    thwack = U(ffilt(white(n, r), 200, 3500)) * env_exp(n, 0.012, 0.0004)
    th = thud(n, 230, 90, 0.02, 0.04, 0.001)
    squish = U(svf(white(n, r), sweep_exp(n, 1900, 330, 0.03), 5.0, "bp")) * env_exp(n, 0.04, 0.003)
    blob = U(sine(sweep_exp(n, 420, 170, 0.03), n)) * env_exp(n, 0.035, 0.002)
    x = 0.7 * thwack + 0.7 * th + 0.55 * squish + 0.35 * blob
    return sat(x, 1.8)


@sfx("enemy_die", 0.4, fade=0.04)
def _enemy_die(r):
    n = ns(0.42)
    t = tvec(n)
    f = env_log([(0, 650), (0.035, 920), (0.3, 160), (0.42, 140)], n)
    f = f * (1.0 + 0.035 * np.sin(TAU * 24.0 * t))
    voice = U(saw(f, n)) + 0.5 * U(square(f * 1.003, n, 0.35))
    f1 = env_log([(0, 850), (0.3, 420)], n)
    f2 = env_log([(0, 1500), (0.3, 850)], n)
    yelp = U(formant_bank(voice, [(f1, 1.0), (f2, 0.6)], q=6.0) + 0.15 * voice)
    yelp *= env_pts([(0, 0), (0.01, 1), (0.2, 0.6), (0.3, 0)], n, 1.3)
    poof = U(svf(white(n, r), sweep_exp(n, 3500, 450, 0.08), 0.8))
    poof *= env_pts([(0, 0), (0.17, 0), (0.19, 1), (0.42, 0)], n, 1.8)
    puff = np.zeros(n)
    place(puff, ns(0.18), thud(ns(0.2), 160, 70, 0.04, 0.06))
    x = 0.8 * yelp + 0.7 * poof + 0.35 * puff
    x = sat(x, 1.3)
    return room(x, 0.5, 0.15)


@sfx("slime_hop", 0.15, fade=0.02)
def _slime_hop(r):
    n = ns(0.16)
    t = tvec(n)
    f = 170.0 + 270.0 * (1.0 - np.exp(-t / 0.015)) + 70.0 * np.exp(-t / 0.05) * np.sin(TAU * 22.0 * t)
    src = U(sine(f, n)) + 0.4 * U(tri(f, n))
    boing = U(svf(src, f * 3.0, 2.0)) * env_pts([(0, 0), (0.003, 1), (0.06, 0.6), (0.16, 0)], n, 1.5)
    splat = U(svf(white(n, r), 1200, 2.0, "bp")) * env_exp(n, 0.012, 0.0005)
    blip = np.zeros(n)
    place(blip, ns(0.03), bubble(900, 0.03, 0.9))
    x = 0.9 * boing + 0.4 * splat + 0.35 * P(blip)
    x = sat(x, 1.2)
    return room(x, 0.2, 0.06)


@sfx("bat_screech", 0.25, fade=0.02)
def _bat_screech(r):
    n = ns(0.26)
    out = np.zeros(n)
    for st, f0, f1, f2, ln, a in [(0.0, 3000, 4300, 2700, 0.11, 1.0),
                                  (0.125, 3300, 4600, 3000, 0.11, 0.8)]:
        m = ns(ln)
        tt = tvec(m)
        f = env_log([(0, f0), (ln * 0.3, f1), (ln, f2)], m) * (1.0 + 0.06 * np.sin(TAU * 48.0 * tt))
        v = U(saw(f, m)) + 0.5 * U(square(f * 0.5, m, 0.25))
        v = svf(v, f * 1.05, 2.5, "bp") + 0.3 * svf(v, 7000, 0.7)
        v = U(v) * env_pts([(0, 0), (0.006, 1), (ln * 0.5, 0.7), (ln, 0)], m, 1.3)
        place(out, ns(st), a * v)
    x = ffilt(out, 900, 8000)
    return room(x, 0.3, 0.12)


@sfx("caster_cast", 0.5, fade=0.05)
def _caster_cast(r):
    n = ns(0.52)
    t = tvec(n)
    u = np.clip(t / 0.5, 0.0, 1.0)
    f = 110.0 * 2.0 ** (5.0 / 12.0 * u ** 1.2)
    vib = 1.0 + 0.015 * np.sin(TAU * 5.5 * t) * np.clip(t / 0.15, 0.0, 1.0)
    voices = np.zeros(n)
    for ratio, det, a in [(1.0, 0.0, 1.0), (1.0, 0.007, 0.8), (1.0, -0.006, 0.8),
                          (np.sqrt(2.0), 0.003, 0.5), (0.5, 0.0, 0.6)]:
        voices += a * U(saw(f * ratio * (1.0 + det) * vib, n))
    f1 = env_pts([(0, 450), (0.5, 760)], n)
    f2 = env_pts([(0, 850), (0.5, 1150)], n)
    f3 = env_pts([(0, 2400), (0.5, 2600)], n)
    choir = formant_bank(voices, [(f1, 1.0), (f2, 0.7), (f3, 0.35)], q=7.0)
    whisper = formant_bank(white(n, r), [(f1 * 1.2, 0.6), (f2 * 1.3, 0.8), (f3, 0.5)], q=5.0)
    amp = env_pts([(0, 0), (0.08, 0.7), (0.42, 1.0), (0.52, 0)], n, 1.2)
    x = (0.85 * U(choir) + 0.25 * U(whisper) + 0.2 * U(sine(f * 0.5, n))) * amp
    x = sat(x * 0.7, 1.2)
    return room(x, 1.0, 0.25, bright=4000)


@sfx("golem_stomp", 0.35, fade=0.04)
def _golem_stomp(r):
    n = ns(0.37)
    sub = thud(n, 95, 45, 0.04, 0.09, 0.0015)
    harm = sat(sub * 3.0, 1.0)
    stone = U(ffilt(white(n, r), 60, 1200)) * env_exp(n, 0.035, 0.001)
    knock = thud(n, 230, 120, 0.02, 0.03, 0.001)
    grit = P(grains(n, r, 18, 0.005, 0.18, 400, 2600, 0.003, 0.01, q=2.0,
                    density=[(0.0, 1.0), (0.18, 0.1)]))
    grit *= env_pts([(0, 1), (0.2, 0.4), (0.37, 0.1)], n)
    x = 0.75 * sub + 0.4 * harm + 0.9 * stone + 0.55 * knock + 0.4 * grit
    x = sat(x * 0.9, 2.0)
    return room(x, 0.5, 0.12)


@sfx("wisp_flare", 0.4, fade=0.04)
def _wisp_flare(r):
    n = ns(0.42)
    t = tvec(n)
    fc = env_log([(0, 600), (0.1, 3000), (0.42, 1100)], n)
    amp = env_pts([(0, 0), (0.025, 1), (0.15, 0.7), (0.42, 0)], n, 1.5)
    fire = U(svf(white(n, r), fc, 0.8, "bp")) * (0.7 + 0.3 * smooth_random(n, r, 35)) * amp
    f = env_log([(0, 880), (0.08, 1320), (0.42, 640)], n) * (1.0 + 0.02 * np.sin(TAU * 7.0 * t))
    ghost = (U(sine(f, n)) + 0.4 * U(sine(f * 2.003, n))) * env_pts([(0, 0), (0.04, 1), (0.42, 0)], n, 1.4)
    crk = P(crackle(n, r, env_pts([(0, 0), (0.03, 200), (0.4, 30)], n), decay=0.0008, lo=2000))
    x = 0.8 * fire + 0.3 * ghost + 0.3 * crk * amp
    return room(x, 0.6, 0.18)


# =============================================================================
# SFX: player
# =============================================================================

@sfx("player_hurt", 0.25, fade=0.03)
def _player_hurt(r):
    n = ns(0.26)
    t = tvec(n)
    impact = U(ffilt(white(n, r), 200, 4000)) * env_exp(n, 0.012, 0.0004)
    th = thud(n, 210, 95, 0.03, 0.05, 0.001)
    f = sweep_exp(n, 540, 170, 0.07) * (1.0 + 0.04 * np.sin(TAU * 38.0 * t))
    tone = U(square(f, n, 0.35)) + 0.6 * U(saw(f * 1.01, n))
    tone = formant_bank(tone, [(800, 1.0), (1300, 0.6)], q=3.0) + 0.3 * svf(tone, 2500, 0.7)
    tone = U(tone) * env_pts([(0, 0), (0.005, 1), (0.1, 0.6), (0.26, 0)], n, 1.4)
    x = 0.5 * impact + 0.5 * th + 0.75 * tone
    x = sat(x * 0.9, 1.6)
    return room(x, 0.3, 0.08)


@sfx("player_die", 1.2, fade=0.12)
def _player_die(r):
    n = ns(1.25)
    t = tvec(n)
    u = np.clip(t / 1.1, 0.0, 1.0)
    froot = 440.0 * (82.0 / 440.0) ** (u ** 1.3)
    vib = 1.0 + 0.04 * u * np.sin(TAU * 5.5 * t)
    chord = np.zeros(n)
    for ratio, a in [(1.0, 1.0), (1.189, 0.7), (1.498, 0.6), (0.5, 0.5)]:
        chord += a * U(saw(froot * ratio * vib, n))
    chord = U(svf(chord, 3500.0 * (1.0 - 0.7 * u) + 300.0, 1.0))
    tone = chord * env_pts([(0, 0), (0.01, 1), (0.5, 0.8), (1.0, 0.0)], n, 1.2)
    held = sample_hold(tone, 1.0 + 14.0 * u ** 1.5)
    pk = np.max(np.abs(held)) + 1e-9
    held = crush(held / pk, bits=7) * pk
    dissolved = (1.0 - u) * tone + u * held
    nz = U(svf(white(n, r), sweep_exp(n, 4000, 350, 0.4), 0.8))
    nz *= env_pts([(0, 0), (0.3, 0.2), (0.75, 0.7), (1.25, 0)], n, 1.3)
    th = thud(n, 160, 60, 0.04, 0.08)
    x = 0.8 * dissolved + 0.45 * nz + 0.4 * th
    return room(x, 1.2, 0.25)


@sfx("jump", 0.12, fade=0.02)
def _jump(r):
    n = ns(0.13)
    t = tvec(n)
    f = 270.0 + 380.0 * (1.0 - np.exp(-t / 0.03))
    x = U(sine(f, n)) + 0.35 * U(tri(f, n)) + 0.15 * U(sine(2.0 * f, n))
    x *= env_pts([(0, 0), (0.004, 1), (0.04, 0.7), (0.13, 0)], n, 1.6)
    x += 0.08 * U(ffilt(white(n, r), 2500, 8000)) * env_exp(n, 0.02, 0.002)
    return room(x, 0.15, 0.05)


@sfx("land", 0.08, fade=0.015)
def _land(r):
    n = ns(0.09)
    th = thud(n, 130, 55, 0.015, 0.025, 0.001)
    dust = U(ffilt(white(n, r), 80, 700)) * env_exp(n, 0.012, 0.0008)
    scuff = U(ffilt(white(n, r), 1500, 5000)) * env_exp(n, 0.008, 0.0005)
    return sat(1.0 * th + 0.6 * dust + 0.12 * scuff, 1.2)


# =============================================================================
# SFX: loops, pickups, portal, elements, UI, stings
# =============================================================================

def fm_bell(f: float, dur: float, ratio: float = 2.0, index: float = 1.5, tau: float = 0.3,
            idx_tau: float = 0.08, attack: float = 0.002) -> np.ndarray:
    """Two-operator FM bell/chime with decaying modulation index."""
    n = ns(dur)
    t = tvec(n)
    index *= min(1.0, max(0.0, (NYQ - f) / (2.0 * ratio * f)))  # keep sidebands below Nyquist
    idx = index * np.exp(-t / idx_tau) + 0.12 * index
    x = np.sin(TAU * f * t + idx * np.sin(TAU * ratio * f * t))
    return x * env_exp(n, tau, attack)


@sfx("levitate", 0.6, loop=True)
def _levitate(r):
    n = ns(0.6)  # bins of SR/n = 5/3 Hz: everything below is exactly periodic
    t = tvec(n)
    hiss = U(ffilt(white(n, r), 1000, 5000, order=2.0, circular=True, peaks=[(3000.0, 2.0, 5.0)]))
    lf = lfo_hz(1.0 / 0.6, n)
    breath = 1.0 + 0.12 * np.sin(TAU * lf * t) + 0.06 * np.sin(TAU * 2.0 * lf * t + 1.0)
    tones = np.zeros(n)
    for f, a in [(880.0, 1.0), (1320.0, 0.6), (1760.0, 0.35), (2640.0, 0.2)]:
        tones += a * (np.sin(TAU * bin_hz(f, n) * t) + np.sin(TAU * bin_hz(f + 1.7, n) * t + 0.7))
    shimmer = 0.8 + 0.2 * np.sin(TAU * 2.0 * lf * t)
    return 0.6 * hiss * breath + 0.25 * U(tones) * shimmer


@sfx("pickup_item", 0.5, fade=0.06)
def _pickup_item(r):
    n = ns(0.55)
    out = np.zeros(n)
    notes = ["A5", "C#6", "E6", "G#6", "B6"]
    for i, nm in enumerate(notes):
        st = i * 0.055
        last = i == len(notes) - 1
        f = hz(nm)
        b = fm_bell(f, 0.55 - st, ratio=2.0, index=1.6, tau=0.25 if last else 0.11, idx_tau=0.06)
        b += 0.3 * fm_bell(f * 2.0, 0.55 - st, ratio=3.0, index=0.8, tau=0.06, idx_tau=0.03)
        place(out, ns(st), (0.7 + 0.3 * i / 4.0) * b)
    sp = pings(n, r, 10, 0.12, 0.45, [hz(m) for m in ("E7", "G#7", "B7", "C#8")], 0.03, 0.08, amp_lo=0.2)
    x = out + 0.18 * P(sp)
    return room(x, 0.8, 0.22, bright=10000)


@sfx("pickup_heart", 0.5, fade=0.08)
def _pickup_heart(r):
    n = ns(0.55)
    out = np.zeros(n)
    for st, nm, a, tau in [(0.0, "F5", 0.8, 0.3), (0.0, "A5", 0.6, 0.28), (0.0, "C6", 0.5, 0.25),
                           (0.11, "F6", 0.7, 0.3)]:
        f = hz(nm)
        b = fm_bell(f, 0.55 - st, ratio=1.0, index=1.0, tau=tau, idx_tau=0.1, attack=0.004)
        b += 0.5 * fm_bell(f * 1.003, 0.55 - st, ratio=1.0, index=0.6, tau=tau, idx_tau=0.1, attack=0.004)
        place(out, ns(st), a * b)
    body = U(sine(hz("F4"), n)) * env_exp(n, 0.25, 0.01)
    x = ffilt(out + 0.25 * body, hi=6000)
    return room(x, 0.9, 0.22)


@sfx("pickup_gold", 0.2, fade=0.03)
def _pickup_gold(r):
    n = ns(0.22)
    t = tvec(n)
    out = np.zeros(n)
    for st, f0, a in [(0.0, hz("B6"), 0.8), (0.055, hz("E7"), 1.0)]:
        m = n - ns(st)
        c = partials(m, f0, [1, 2.39, 2.84, 4.17], [1, 0.5, 0.35, 0.2], [0.12, 0.05, 0.04, 0.025],
                     rng=r, attack=0.0008, beat=6.0)
        place(out, ns(st), a * c)
    f = np.where(t < 0.055, hz("B5"), hz("E6"))
    retro = U(square(f, n, 0.5)) * env_pts([(0, 0), (0.002, 1), (0.05, 0.8), (0.056, 1), (0.22, 0)], n, 1.5)
    retro = svf(retro, 4000, 0.7)
    tick = U(ffilt(white(n, r), 3000, 10000)) * env_exp(n, 0.002, 0.0002)
    x = 0.8 * P(out) + 0.22 * retro + 0.2 * tick
    return room(x, 0.3, 0.1, bright=10000)


@sfx("portal_enter", 1.2, fade=0.15)
def _portal_enter(r):
    n = ns(1.25)
    t = tvec(n)
    u = np.clip(t / 1.2, 0.0, 1.0)
    f = 150.0 * 2.0 ** (4.0 * u ** 1.15)
    src = (U(saw(f, n)) + 0.8 * U(saw(f * 1.008, n)) + 0.6 * U(saw(f * 1.5 * 0.996, n))
           + 0.5 * U(sine(f * 2.0, n)))
    src = U(svf(src, np.minimum(f * 3.0, 9000.0), 1.0))
    d = (1.0 + 5.0 * (0.5 + 0.5 * np.sin(TAU * phase_of(0.9 + 2.5 * u, n)))) * SR / 1000.0
    flanged = U(src + 0.8 * vdelay(src, d))
    shimmer = 1.0 + 0.25 * np.sin(TAU * 24.0 * t)
    whoosh = U(svf(white(n, r), np.minimum(f * 2.0, 9000.0), 2.0, "bp"))
    sp = P(pings(n, r, 28, 0.2, 1.15, [hz(m) for m in ("C7", "E7", "G7", "B7", "D8")], 0.04, 0.1,
                 density=[(0.2, 0.2), (1.15, 1.0)]))
    amp = env_pts([(0, 0), (0.25, 0.8), (0.85, 1.0), (1.2, 0)], n, 1.3)
    x = (0.6 * flanged * shimmer + 0.3 * whoosh) * amp + 0.18 * sp
    x = sat(x * 0.8, 1.5)
    return room(x, 1.2, 0.25, bright=10000)


@sfx("portal_hum", 2.0, loop=True)
def _portal_hum(r):
    n = ns(2.0)  # bins of 0.5 Hz
    t = tvec(n)
    hum = np.zeros(n)
    for f, a, ph in [(55.0, 1.0, 0.0), (55.5, 0.8, 1.1), (82.5, 0.5, 2.0), (110.0, 0.45, 0.3),
                     (111.0, 0.3, 2.5), (155.5, 0.25, 1.7), (233.0, 0.12, 0.9)]:
        hum += a * np.sin(TAU * bin_hz(f, n) * t + ph)
    hum = sat(U(hum) * 0.9, 1.0)
    fw = bin_hz(1046.5, n)
    vib = lfo_hz(3.0, n)
    whistle = (np.sin(TAU * fw * t + 2.2 * np.sin(TAU * vib * t))
               + 0.5 * np.sin(TAU * bin_hz(fw * 1.498, n) * t + 1.5 * np.sin(TAU * lfo_hz(2.0, n) * t + 1.0)))
    wamp = 0.5 + 0.5 * np.sin(TAU * lfo_hz(0.5, n) * t)
    air = U(ffilt(pink(n, r), 180, 900, circular=True))
    aamp = 0.8 + 0.2 * np.sin(TAU * lfo_hz(1.0, n) * t + 1.0)
    return 0.8 * U(hum) + 0.12 * U(whistle) * wamp + 0.25 * air * aamp


@sfx("fire_ignite", 0.3, fade=0.04)
def _fire_ignite(r):
    n = ns(0.32)
    fc = env_log([(0, 300), (0.06, 3500), (0.32, 500)], n)
    whoomp = U(svf(white(n, r), fc, 1.2)) * env_pts([(0, 0), (0.04, 1), (0.1, 0.7), (0.32, 0)], n, 1.6)
    bloom = U(sine(env_log([(0, 70), (0.05, 105), (0.32, 60)], n), n))
    bloom *= env_pts([(0, 0), (0.03, 1), (0.32, 0)], n, 2.0)
    crk = P(crackle(n, r, env_pts([(0, 0), (0.08, 0), (0.1, 120), (0.3, 60)], n), decay=0.001, lo=1500))
    crk *= env_pts([(0, 1), (0.12, 1), (0.32, 0.25)], n)
    x = 0.9 * whoomp + 0.6 * bloom + 0.3 * crk
    x = sat(x, 1.5)
    return room(x, 0.4, 0.1)


@sfx("splash", 0.3, fade=0.04)
def _splash(r):
    n = ns(0.32)
    t = tvec(n)
    body = U(svf(white(n, r), env_log([(0, 1800), (0.05, 3200), (0.32, 2200)], n), 0.7, "bp"))
    body *= env_pts([(0, 0), (0.004, 1), (0.05, 0.6), (0.32, 0)], n, 1.6)
    second = U(ffilt(white(n, r), 1200, 6000)) * env_exp(n, 0.05, 0.005, delay=0.06)
    drops = P(bubbles(n, r, 20, 0.03, 0.28, 1000, 3800, 0.012, 0.03, fall=0.7))
    plunk = U(sine(380.0 + 320.0 * (1.0 - np.exp(-t / 0.02)), n)) * env_exp(n, 0.035, 0.002)
    x = 0.8 * body + 0.35 * second + 0.45 * drops + 0.35 * plunk
    x = sat(ffilt(x, hi=9000), 1.2)
    return room(x, 0.3, 0.1)


@sfx("steam_hiss", 0.5, fade=0.06)
def _steam_hiss(r):
    n = ns(0.52)
    src = white(n, r)
    body = U(ffilt(src, 2500, 7500))
    res = U(svf(src, sweep_exp(n, 6000, 3800, 0.2), 2.0, "bp"))
    amp = env_pts([(0, 0), (0.015, 1), (0.15, 0.85), (0.52, 0)], n, 1.3) * (0.8 + 0.2 * smooth_random(n, r, 20))
    pop = U(ffilt(white(n, r), 500, 4000)) * env_exp(n, 0.004, 0.0003)
    return (0.7 * body + 0.35 * res) * amp + 0.25 * pop


@sfx("ui_click", 0.05, fade=0.01)
def _ui_click(r):
    n = ns(0.05)
    tick = U(sine(sweep_exp(n, 1900, 1200, 0.005), n)) * env_exp(n, 0.007, 0.0004)
    body = U(sine(620.0, n)) * env_exp(n, 0.012, 0.0008)
    tr = U(ffilt(white(n, r), 3000, 9000)) * env_exp(n, 0.0015, 0.0002)
    return 0.8 * tick + 0.5 * body + 0.15 * tr


@sfx("ui_hover", 0.04, fade=0.01)
def _ui_hover(r):
    n = ns(0.04)
    x = U(sine(sweep_exp(n, 1800, 1600, 0.01), n)) * env_exp(n, 0.009, 0.002)
    return x + 0.35 * U(sine(900.0, n)) * env_exp(n, 0.007, 0.002)


@sfx("perk_choose", 0.6, fade=0.08)
def _perk_choose(r):
    n = ns(0.65)
    out = np.zeros(n)
    seq = [("C5", 0.0), ("E5", 0.06), ("G5", 0.12), ("C6", 0.18)]
    for i, (nm, st) in enumerate(seq):
        last = i == len(seq) - 1
        m = n - ns(st)
        tt = tvec(m)
        f = hz(nm) * np.ones(m)
        if last:
            f *= 1.0 + 0.006 * np.sin(TAU * 6.0 * tt) * np.clip((tt - 0.15) / 0.1, 0.0, 1.0)
        src = U(saw(f, m)) + 0.7 * U(saw(f * 1.004, m)) + 0.5 * U(square(f * 0.997, m, 0.4))
        fc = 900.0 + 3500.0 * np.exp(-tt / 0.09) * np.clip(tt / 0.01, 0.0, 1.0)
        v = U(svf(src, fc, 1.2)) * env_exp(m, 0.35 if last else 0.07, 0.006)
        place(out, ns(st), (1.0 if last else 0.75) * v)
    chord = (U(sine(hz("C4"), n)) + 0.7 * U(sine(hz("G4"), n)))
    chord *= env_pts([(0, 0), (0.18, 0), (0.22, 1), (0.65, 0)], n, 1.5)
    sp = P(pings(n, r, 16, 0.18, 0.6, [hz(m) for m in ("C7", "E7", "G7", "C8")], 0.05, 0.12))
    sweep = U(svf(white(n, r), sweep_log(n, 2000, 9000), 3.0, "bp"))
    sweep *= env_pts([(0, 0), (0.15, 0), (0.3, 1), (0.65, 0)], n, 1.5)
    x = 0.8 * out + 0.3 * chord + 0.25 * sp + 0.12 * sweep
    x = sat(x * 0.8, 1.2)
    return room(x, 1.0, 0.2)


@sfx("level_start", 1.5, fade=0.25)
def _level_start(r):
    n = ns(1.55)
    t = tvec(n)
    hit = 0.55
    pad = np.zeros(n)
    for nm in ["D3", "A3", "E4", "G#4"]:
        f = hz(nm)
        pad += U(saw(f, n, r.uniform())) + 0.7 * U(saw(f * 1.005, n, r.uniform()))
    pad = U(ffilt(pad, 60, 1300))
    pad_env = np.where(t < hit, (t / hit) ** 2.2, np.exp(-(t - hit) / 0.55))
    rise = np.where(t < hit, (t / hit) ** 3, np.exp(-(t - hit) / 0.03))
    whoosh = U(svf(white(n, r), env_log([(0, 300), (hit, 3500), (1.55, 3500)], n), 2.0, "bp")) * rise
    boom = np.zeros(n)
    place(boom, ns(hit), thud(n - ns(hit), 72, 40, 0.1, 0.3, 0.002))
    bell = np.zeros(n)
    for nm, a in [("D6", 1.0), ("A6", 0.6), ("G#5", 0.5)]:
        place(bell, ns(hit), a * fm_bell(hz(nm), 1.55 - hit, ratio=3.5, index=1.2, tau=0.5, idx_tau=0.15))
    sp = P(pings(n, r, 12, hit, 1.4, [hz(m) for m in ("D7", "E7", "G#7", "A7")], 0.06, 0.15))
    x = 0.55 * pad * pad_env + 0.2 * whoosh + 0.7 * boom + 0.45 * P(bell) + 0.12 * sp
    x = sat(x * 0.8, 1.1)
    return room(x, 1.8, 0.3)


@sfx("game_over", 2.5, fade=0.35)
def _game_over(r):
    n = ns(2.6)
    out = np.zeros(n)
    mel = [("E5", 0.0, 0.34), ("D5", 0.32, 0.34), ("C5", 0.64, 0.34), ("B4", 0.96, 0.4), ("A4", 1.32, 1.25)]
    for i, (nm, st, ln) in enumerate(mel):
        last = i == len(mel) - 1
        m = ns(ln + 0.35)
        tt = tvec(m)
        f = hz(nm) * np.ones(m)
        if last:  # vibrato and a sad little droop
            f *= 1.0 + 0.006 * np.sin(TAU * 5.0 * tt) * np.clip((tt - 0.3) / 0.3, 0.0, 1.0)
            f *= 1.0 - 0.012 * np.clip((tt - 0.6) / 0.8, 0.0, 1.0)
        v = U(tri(f, m)) + 0.4 * U(square(f, m, 0.3)) + 0.3 * U(sine(f * 2.0, m))
        v = U(svf(v, 2200, 0.8)) * env_adsr(m, 0.02, 0.15, 0.6, 0.3, hold=ln)
        place(out, ns(st), (1.1 if last else 1.0) * v)
    chords = [(0.0, 0.64, ["A2", "E3", "A3", "C4"]), (0.64, 0.32, ["F2", "C3", "A3", "C4"]),
              (0.96, 0.36, ["E2", "B2", "G#3", "D4"]), (1.32, 1.28, ["A2", "E3", "A3", "C4"])]
    pad = np.zeros(n)
    for st, ln, nms in chords:
        m = ns(ln + 0.5)
        seg = np.zeros(m)
        for nm in nms:
            seg += U(saw(hz(nm), m, r.uniform())) + 0.6 * U(saw(hz(nm) * 1.004, m, r.uniform()))
        seg = ffilt(seg, 50, 900)
        place(pad, ns(st), U(seg) * env_adsr(m, 0.08, 0.2, 0.8, 0.45, hold=ln))
    low = U(sine(hz("A1"), n)) * env_pts([(0, 0), (1.32, 0), (1.4, 1), (2.6, 0)], n, 1.5)
    x = 0.7 * out + 0.45 * pad + 0.35 * low
    x = sat(x * 0.8, 1.1)
    return room(x, 1.8, 0.3)


# =============================================================================
# SFX: potions, liquids, glass
# =============================================================================

def event_times(rng, count: int, t0: float, t1: float, density=None) -> list:
    """`count` random onsets in [t0, t1], optionally weighted by density [(t, w), ...]."""
    ts = np.linspace(t0, t1, 64)
    w = np.ones_like(ts) if density is None else np.interp(
        ts, [p[0] for p in density], [p[1] for p in density])
    w = w / w.sum()
    return [float(rng.choice(ts, p=w) + rng.uniform(0.0, (t1 - t0) / 64.0)) for _ in range(count)]


def fizz(n: int, rng, count: int, t0: float, t1: float, flo: float, fhi: float,
         rise=(0.15, 0.5), density=None, wrap: bool = False, stretch: float = 2.0) -> np.ndarray:
    """Cloud of small bubbles: the texture of a liquid stream or splash.

    Ring time follows bubble size (van den Doel damping law, stretched a little so the
    bubbles stay audible as pitched blips); bigger, lower bubbles are louder.
    """
    out = np.zeros(n)
    for st in event_times(rng, count, t0, t1, density):
        f0 = float(np.exp(rng.uniform(np.log(flo), np.log(fhi))))
        tau = stretch / (0.13 * f0 + 0.0072 * f0 ** 1.5)
        dur = float(np.clip(3.0 * tau, 0.008, 0.08))
        a = rng.uniform(0.3, 1.0) * (flo / f0) ** 0.4
        place(out, ns(st), a * bubble(f0, dur, rng.uniform(*rise)), wrap=wrap)
    return out


def shards(n: int, rng, count: int, t0: float, t1: float, flo: float, fhi: float,
           dlo: float = 0.006, dhi: float = 0.04, density=None, amp_lo: float = 0.1) -> np.ndarray:
    """Shower of glass / crystal fragments: tiny inharmonic 'tinks', each with a click."""
    out = np.zeros(n)
    for st in event_times(rng, count, t0, t1, density):
        f0 = float(np.exp(rng.uniform(np.log(flo), np.log(fhi))))
        d = rng.uniform(dlo, dhi)
        m = ns(d * 4.0) + 16
        ratios = [1.0, rng.uniform(1.55, 2.3), rng.uniform(2.6, 3.5), rng.uniform(4.0, 5.4)]
        c = partials(m, f0, ratios, [1.0, 0.7, 0.5, 0.3], [d, d * 0.6, d * 0.45, d * 0.3],
                     rng=rng, attack=0.0003)
        c += 0.6 * white(m, rng) * np.exp(-tvec(m) / 0.0006)
        place(out, ns(st), rng.uniform(amp_lo, 1.0) ** 1.5 * c)
    return out


def crystal_tone(f0: float, dur: float, rng, decay: float = 0.1, glide: float = 0.0,
                 glide_tau: float = 0.08, beat: float = 3.0) -> np.ndarray:
    """Ringing crystal (free-bar partials, slightly beating), optional pitch glide (Doppler)."""
    n = ns(dur)
    t = tvec(n)
    bend = 1.0 + glide * (1.0 - np.exp(-t / glide_tau))
    out = np.zeros(n)
    for k, (ra, a) in enumerate([(1.0, 1.0), (2.756, 0.5), (5.404, 0.3), (8.933, 0.15)]):
        f = f0 * ra
        if f * max(1.0, 1.0 + glide) >= NYQ * 0.9:
            continue
        env = np.exp(-t * (1.0 + 1.2 * k) / decay)
        out += a * env * (np.sin(TAU * phase_of(f * bend, n, rng.uniform()))
                          + 0.6 * np.sin(TAU * phase_of((f + beat * (1 + k)) * bend, n, rng.uniform())))
    return out * np.clip(t / 0.0006, 0.0, 1.0)


def gulp(rng, pitch: float = 1.0) -> np.ndarray:
    """One swallow: wet throat click, the gulp itself, then air glugging into the flask."""
    n = ns(0.17)
    click = U(ffilt(white(n, rng), 1500, 6000)) * env_exp(n, 0.0018, 0.0002)
    glk = U(svf(white(n, rng), sweep_exp(n, 1500 * pitch, 600 * pitch, 0.01), 5.0, "bp"))
    glk *= env_exp(n, 0.011, 0.0005)
    f = sweep_exp(n, 430 * pitch, 150 * pitch, 0.022)
    body = U(sine(f, n) + 0.3 * tri(f, n)) * env_exp(n, 0.035, 0.002)
    wet = U(ffilt(white(n, rng), 200, 1400)) * (0.6 + 0.4 * smooth_random(n, rng, 40)) * env_exp(n, 0.03, 0.004)
    glug = np.zeros(n)
    place(glug, ns(0.04), bubble(380 * pitch, 0.065, 0.9))
    place(glug, ns(0.075), 0.45 * bubble(640 * pitch, 0.035, 0.8))
    return 0.25 * click + 0.4 * glk + 0.9 * body + 0.2 * wet + 0.7 * P(glug)


@sfx("glass_break", 0.5, fade=0.06)
def _glass_break(r):
    n = ns(0.52)
    # impact: sharp snap, the flask body knocking, its short ring as it gives way
    snap = U(ffilt(white(n, r), 1500, 10000)) * env_exp(n, 0.0035, 0.0002)
    body = thud(n, 700, 300, 0.006, 0.012, 0.0004)
    ring = partials(n, 1660.0, [1.0, 2.31, 3.9, 5.5], [1.0, 0.6, 0.4, 0.25],
                    [0.03, 0.02, 0.014, 0.01], rng=r, attack=0.0003, beat=11.0)
    # shatter: a dense burst of shards thinning out, then a few late pieces tinkling
    burst = P(shards(n, r, 70, 0.0, 0.25, 2200, 9500, 0.005, 0.035,
                     density=[(0.0, 1.0), (0.03, 0.6), (0.12, 0.15), (0.25, 0.03)]))
    tinkle = P(shards(n, r, 16, 0.08, 0.44, 3000, 8500, 0.01, 0.05, amp_lo=0.05))
    crunch = U(svf(white(n, r), sweep_exp(n, 8000, 3000, 0.04), 1.0, "bp")) * env_exp(n, 0.025, 0.0006)
    # the potion: splash body, a cloud of bubbles, low slosh and scattered droplets
    splash = U(svf(white(n, r), env_log([(0, 1000), (0.03, 2400), (0.35, 1100)], n), 0.9, "bp"))
    splash *= env_pts([(0, 0), (0.012, 0), (0.03, 1), (0.09, 0.5), (0.4, 0)], n, 1.6)
    fz = P(fizz(n, r, 90, 0.015, 0.38, 500, 3500, density=[(0.015, 1.0), (0.1, 0.8), (0.38, 0.05)]))
    slosh = U(ffilt(white(n, r), 120, 700)) * (0.6 + 0.4 * smooth_random(n, r, 25))
    slosh *= env_pts([(0, 0), (0.015, 0), (0.04, 1), (0.3, 0)], n, 1.5)
    drops = P(bubbles(n, r, 10, 0.08, 0.42, 1100, 3000, 0.012, 0.03, fall=0.8))
    x = (0.8 * snap + 0.35 * body + 0.4 * P(ring) + 1.0 * burst + 0.35 * tinkle + 0.35 * crunch
         + 0.4 * splash + 0.55 * fz + 0.25 * slosh + 0.3 * drops)
    x = sat(x * 0.9, 1.2)
    return room(x, 0.45, 0.14, bright=10000)


@sfx("potion_drink", 0.6, fade=0.06)
def _potion_drink(r):
    n = ns(0.62)
    x = np.zeros(n)
    for st, p, a in [(0.0, 1.0, 0.9), (0.2, 0.93, 1.0), (0.4, 1.06, 0.85)]:
        place(x, ns(st + r.uniform(0.0, 0.012)), a * gulp(r, p))
    return room(sat(x, 1.2), 0.3, 0.1)


@sfx("potion_pour", 0.5, loop=True)
def _potion_pour(r):
    n = ns(0.5)  # bins of 2 Hz; every event wraps around the seam, so the loop is exact
    # the stream splashing into liquid: a dense bubble cloud over fluttering filtered noise
    stream = U(ffilt(white(n, r), 400, 3200, circular=True, peaks=[(1200.0, 1.2, 5.0)]))
    flutter = 0.7 + 0.3 * smooth_random(n, r, 18.0, circular=True)
    cloud = P(fizz(n, r, 300, 0.0, 0.5, 450, 3000, rise=(0.1, 0.45), wrap=True))
    # glugs: air gulping back into the flask neck, irregular but exactly periodic
    glug = np.zeros(n)
    surge = np.zeros(n)
    for st, f0, a in [(0.015, 300.0, 1.0), (0.13, 360.0, 0.7), (0.255, 320.0, 0.9), (0.37, 390.0, 0.65)]:
        place(glug, ns(st), a * bubble(f0, 0.075, 1.0), wrap=True)
        place(glug, ns(st + 0.03), 0.4 * a * bubble(f0 * 1.9, 0.035, 0.8), wrap=True)
        m = ns(0.12)
        place(surge, ns(st - 0.01), a * env_pts([(0, 0), (0.015, 1), (0.12, 0)], m, 1.5), wrap=True)
    body = U(ffilt(white(n, r), 120, 650, circular=True)) * (0.7 + 0.3 * smooth_random(n, r, 9.0, circular=True))
    return 0.16 * stream * flutter * (0.8 + 0.6 * surge) + 0.85 * cloud + 0.75 * P(glug) + 0.18 * body


@sfx("flask_fill", 0.35, fade=0.04)
def _flask_fill(r):
    n = ns(0.37)
    # suction 'shlp' as the flask dips in
    suck = U(svf(white(n, r), sweep_exp(n, 3200, 800, 0.025), 2.0, "bp"))
    suck *= env_pts([(0, 0), (0.008, 1), (0.05, 0)], n, 1.5)
    thoop = U(sine(sweep_exp(n, 240, 110, 0.03), n)) * env_exp(n, 0.035, 0.003)
    # glugs climbing in pitch as the air pocket shrinks
    glug = np.zeros(n)
    times = [0.035, 0.075, 0.11, 0.145, 0.18, 0.21, 0.24, 0.27]
    for i, st in enumerate(times):
        u = i / (len(times) - 1)
        f0 = 300.0 * 2.0 ** (1.6 * u) * r.uniform(0.95, 1.05)
        place(glug, ns(st), (1.0 - 0.35 * u) * bubble(f0, 0.05 - 0.02 * u, 0.9))
    fz = P(fizz(n, r, 70, 0.03, 0.3, 700, 3000))
    # the resonance of the filling neck rises (the classic 'filling a bottle' sweep)
    fc = env_log([(0, 420), (0.05, 480), (0.3, 1700), (0.37, 1800)], n)
    neck = U(svf(pink(n, r) + 3.0 * fz, fc, 7.0, "bp"))
    neck *= env_pts([(0, 0), (0.03, 0.6), (0.08, 1.0), (0.28, 0.8), (0.37, 0)], n, 1.3)
    x = 0.5 * suck + 0.4 * thoop + 0.8 * P(glug) + 0.3 * fz + 0.35 * neck
    x = sat(x, 1.2)
    return room(x, 0.3, 0.1)


@sfx("heal", 0.5, fade=0.1)
def _heal(r):
    n = ns(0.53)
    t = tvec(n)
    # warm glow: a soft additive Gadd9 chord, gently detuned, swelling in
    glow = np.zeros(n)
    for nm, a in [("G4", 1.0), ("B4", 0.7), ("D5", 0.75), ("A5", 0.45)]:
        f = hz(nm)
        for det in (-0.0025, 0.0025):
            ph = phase_of(f * (1.0 + det) * (1.0 + 0.003 * np.sin(TAU * 5.0 * t)), n, r.uniform())
            glow += a * (np.sin(TAU * ph) + 0.25 * np.sin(2 * TAU * ph) + 0.08 * np.sin(3 * TAU * ph))
    glow = U(glow) * env_pts([(0, 0), (0.07, 1.0), (0.22, 0.8), (0.53, 0)], n, 1.4)
    # rising shimmer: soft bells entering upwards, with a gentle tremolo
    sh = np.zeros(n)
    for i, nm in enumerate(["D6", "G6", "B6", "D7", "G7"]):
        st = 0.03 + 0.035 * i
        place(sh, ns(st), (1.0 - 0.1 * i) * fm_bell(hz(nm), 0.5 - st, ratio=1.0, index=0.5, tau=0.22,
                                                    idx_tau=0.05, attack=0.006))
    sh *= 0.75 + 0.25 * np.sin(TAU * 11.0 * t)
    air = U(svf(white(n, r), env_log([(0, 2500), (0.2, 7000), (0.53, 5000)], n), 2.0, "bp"))
    air *= env_pts([(0, 0), (0.15, 1), (0.53, 0)], n, 1.6)
    sp = P(pings(n, r, 10, 0.1, 0.45, [hz(m) for m in ("G7", "B7", "D8")], 0.05, 0.12, amp_lo=0.2))
    x = 0.55 * glow + 0.6 * P(sh) + 0.08 * air + 0.12 * sp
    x = ffilt(x, hi=9000)
    return room(x, 1.0, 0.25)


@sfx("poison", 0.3, fade=0.05)
def _poison(r):
    n = ns(0.32)
    # sickly voice: two saws a sour semitone apart, sagging, gargled through an 'uh' vowel
    f = env_log([(0, 105), (0.08, 98), (0.32, 72)], n) * (1.0 + 0.02 * smooth_random(n, r, 12))
    src = U(saw(f, n)) + 0.8 * U(saw(f * 1.059, n)) + 0.4 * U(square(f * 0.5, n, 0.3))
    f1 = env_log([(0, 620), (0.32, 430)], n)
    f2 = env_log([(0, 1050), (0.32, 800)], n)
    voice = U(formant_bank(src, [(f1, 1.0), (f2, 0.6)], q=5.0))
    gargle = 0.5 + 0.5 * np.tanh(2.5 * np.sin(TAU * phase_of(26.0 + 8.0 * smooth_random(n, r, 6), n)))
    voice *= gargle * env_pts([(0, 0), (0.012, 1), (0.12, 0.7), (0.32, 0)], n, 1.3)
    bub = P(bubbles(n, r, 9, 0.01, 0.24, 160, 520, 0.03, 0.07, fall=0.5))
    wet = U(ffilt(white(n, r), 150, 900)) * (0.5 + 0.5 * smooth_random(n, r, 35)) * env_exp(n, 0.09, 0.008)
    x = 0.75 * voice + 0.7 * bub + 0.25 * wet
    x = sat(x * 0.8, 1.4)
    return room(x, 0.35, 0.12, bright=5000)


# =============================================================================
# SFX: spells, inventory UI
# =============================================================================

def soft_pluck(f: float, dur: float, vel: float = 0.8, tau: float = 0.12) -> np.ndarray:
    """Soft rounded UI pluck: sine with a brief FM edge on the attack."""
    n = ns(dur)
    t = tvec(n)
    idx = 0.9 * np.exp(-t / 0.02)
    x = np.sin(TAU * f * t + idx * np.sin(TAU * 2.0 * f * t))
    return vel * x * env_exp(n, tau, 0.002) * smooth_env(n, 0.0, min(0.03, dur * 0.3))


@sfx("spell_pickup", 0.6, fade=0.1)
def _spell_pickup(r):
    n = ns(0.62)
    t = tvec(n)
    # parchment: crinkly papery friction in two quick gestures (lift, unfurl)
    gest = env_pts([(0, 0), (0.012, 1.0), (0.06, 0.45), (0.085, 0.9), (0.16, 0.25), (0.24, 0)], n, 1.3)
    paper = U(ffilt(white(n, r), 1200, 8000, peaks=[(3500.0, 1.0, 4.0)]))
    paper *= (0.35 + 0.65 * np.abs(smooth_random(n, r, 90.0))) * gest
    crinkle = P(crackle(n, r, 1400.0 * gest, decay=0.0005, lo=1800, hi=9500)) * np.sqrt(gest)
    flap = U(svf(white(n, r), env_log([(0, 700), (0.09, 2400), (0.2, 1200)], n), 1.4, "bp"))
    flap *= env_pts([(0, 0), (0.05, 0.2), (0.09, 1.0), (0.2, 0)], n, 1.5)
    # chime: a quick whole-tone rise into a ringing augmented bloom that shimmers
    chime = np.zeros(n)
    for i, nm in enumerate(["C6", "D6", "E6", "F#6"]):
        place(chime, ns(0.07 + 0.032 * i), (0.55 + 0.1 * i) * crystal_tone(hz(nm), 0.4, r, decay=0.12, beat=4.0))
    bloom = np.zeros(n)
    for nm, a in [("G#6", 1.0), ("C7", 0.8), ("E7", 0.6), ("G#5", 0.5)]:
        place(bloom, ns(0.2), a * crystal_tone(hz(nm), 0.42, r, decay=0.35, beat=5.0))
    bloom *= 1.0 + 0.3 * np.sin(TAU * 9.0 * t)
    sp = P(pings(n, r, 14, 0.18, 0.55, [hz(m) for m in ("C8", "E7", "G#7", "D7")], 0.04, 0.1, amp_lo=0.2))
    x = 0.5 * paper + 0.35 * crinkle + 0.3 * flap + 0.7 * P(chime) + 0.75 * P(bloom) + 0.15 * sp
    return room(x, 0.9, 0.22, bright=10000)


@sfx("inventory_open", 0.25, fade=0.05)
def _inventory_open(r):
    n = ns(0.26)
    # leather flap lifting, a soft thup, and two plucks rising a fifth
    flap = U(svf(white(n, r), env_log([(0, 500), (0.07, 2300), (0.14, 1600)], n), 1.1, "bp"))
    flap *= env_pts([(0, 0), (0.025, 1), (0.1, 0.25), (0.16, 0)], n, 1.6)
    thup = thud(n, 170, 95, 0.02, 0.025, 0.002)
    notes = np.zeros(n)
    place(notes, ns(0.02), soft_pluck(hz("A5"), 0.22, 0.75, 0.07))
    place(notes, ns(0.075), soft_pluck(hz("E6"), 0.18, 0.9, 0.09))
    glint = np.zeros(n)
    place(glint, ns(0.08), ping(hz("A7"), 0.1, 0.2))
    x = 0.3 * flap + 0.25 * thup + 0.8 * P(notes) + 0.12 * glint
    return room(x, 0.35, 0.12)


@sfx("inventory_close", 0.2, fade=0.04)
def _inventory_close(r):
    n = ns(0.21)
    # mirror of inventory_open: flap falling, plucks falling a fifth, the bag closing
    flap = U(svf(white(n, r), env_log([(0, 2200), (0.06, 700), (0.12, 450)], n), 1.1, "bp"))
    flap *= env_pts([(0, 0), (0.015, 1), (0.07, 0.3), (0.11, 0)], n, 1.6)
    thup = np.zeros(n)
    place(thup, ns(0.055), thud(ns(0.1), 190, 85, 0.015, 0.03, 0.0015))
    notes = np.zeros(n)
    place(notes, 0, soft_pluck(hz("E6"), 0.16, 0.85, 0.06))
    place(notes, ns(0.045), soft_pluck(hz("A5"), 0.16, 0.8, 0.07))
    x = 0.3 * flap + 0.4 * thup + 0.8 * P(notes)
    return room(x, 0.3, 0.1)


@sfx("slot_place", 0.08, fade=0.015)
def _slot_place(r):
    n = ns(0.09)
    click = U(ffilt(white(n, r), 2500, 9000)) * env_exp(n, 0.0012, 0.0002)
    tok = U(svf(white(n, r), 1250, 6.0, "bp")) * env_exp(n, 0.008, 0.0004)
    thunk = thud(n, 280, 150, 0.008, 0.02, 0.0008)
    body = thud(n, 130, 85, 0.012, 0.03, 0.0015)
    wood = partials(n, 620.0, [1.0, 2.15, 3.6], [1.0, 0.5, 0.25], [0.018, 0.01, 0.006], rng=r, attack=0.0004)
    x = 0.35 * click + 0.45 * tok + 0.7 * thunk + 0.35 * body + 0.5 * P(wood)
    return room(sat(x, 1.3), 0.15, 0.05)


@sfx("ui_back", 0.06, fade=0.012)
def _ui_back(r):
    n = ns(0.06)
    out = np.zeros(n)
    for st, f0, f1, a in [(0.0, 1500.0, 1150.0, 0.85), (0.022, 1050.0, 760.0, 1.0)]:
        m = n - ns(st)
        place(out, ns(st), a * U(sine(sweep_exp(m, f0, f1, 0.006), m)) * env_exp(m, 0.008, 0.0004))
    body = U(sine(470.0, n)) * env_exp(n, 0.014, 0.0008)
    tr = U(ffilt(white(n, r), 3000, 9000)) * env_exp(n, 0.0015, 0.0002)
    return 0.8 * out + 0.4 * body + 0.12 * tr


# =============================================================================
# SFX: boss (Portinvartija, the floating stone guardian)
# =============================================================================

@sfx("boss_roar", 1.6, fade=0.2)
def _boss_roar(r):
    n = ns(1.65)
    t = tvec(n)
    # voice: a huge throat - growling saws, sub-octave, pitch jitter and vocal-fry flutter
    f = env_log([(0, 44), (0.18, 60), (0.55, 66), (1.05, 58), (1.5, 38), (1.65, 34)], n)
    f = f * (1.0 + 0.035 * smooth_random(n, r, 9.0))
    fry = 0.65 + 0.35 * np.tanh(3.0 * np.sin(TAU * phase_of(31.0 + 6.0 * smooth_random(n, r, 4.0), n)))
    src = (U(saw(f, n)) + 0.8 * U(saw(f * 1.011, n)) + 0.6 * U(square(f * 0.5, n, 0.45))
           + 0.3 * U(saw(f * 1.498, n))) * fry
    # vowel opens 'oo' -> 'aa' and closes again: rrRRAAAOOHH
    f1 = env_log([(0, 280), (0.3, 520), (0.7, 560), (1.1, 420), (1.65, 260)], n)
    f2 = env_log([(0, 620), (0.3, 950), (0.7, 1000), (1.1, 760), (1.65, 520)], n)
    f3 = env_log([(0, 1700), (0.4, 2000), (1.65, 1500)], n)
    voice = U(formant_bank(src, [(f1, 1.0), (f2, 0.7), (f3, 0.3)], q=5.5)) + 0.25 * U(svf(src, 900, 0.7))
    breath = U(formant_bank(pink(n, r), [(f1, 0.8), (f2, 1.0), (f3, 0.6)], q=3.0))
    # otherworldly: a ring-modulated ghost of the voice and a slowly flanged copy
    ghost = voice * np.sin(TAU * phase_of(env_log([(0, 70), (1.65, 110)], n), n))
    flanged = vdelay(voice, (3.0 + 2.5 * np.sin(TAU * 0.9 * t)) * SR / 1000.0)
    amp = env_pts([(0, 0), (0.1, 0.7), (0.3, 1.0), (0.6, 0.8), (0.85, 0.95), (1.2, 0.6), (1.5, 0.2),
                   (1.65, 0)], n, 1.2)
    roar = (0.8 * voice + 0.35 * flanged + 0.3 * ghost + 0.25 * breath) * amp
    # the stone body: deep rumble, grinding, falling grit
    rumble = U(ffilt(brown(n, r), 22, 240)) * (0.65 + 0.35 * smooth_random(n, r, 6.0))
    rumble *= env_pts([(0, 0), (0.1, 1.0), (1.2, 0.8), (1.65, 0)], n, 1.2)
    grind = U(svf(white(n, r), env_log([(0, 500), (0.6, 900), (1.65, 400)], n), 1.8, "bp"))
    grind *= (0.4 + 0.6 * np.abs(smooth_random(n, r, 30.0))) * env_pts([(0, 0), (0.2, 1.0), (1.3, 0.6), (1.65, 0)], n)
    grit = P(grains(n, r, 45, 0.05, 1.5, 200, 2200, 0.005, 0.02, q=2.5,
                    density=[(0.05, 1.0), (0.8, 0.7), (1.5, 0.2)]))
    x = 0.9 * roar + 0.55 * rumble + 0.18 * grind + 0.22 * grit
    x = ffilt(sat(x * 0.8, 1.6), lo=35.0)  # nothing useful lives below 35 Hz; keep the headroom
    return room(x, 1.6, 0.22, predelay=0.02, seed=29, bright=6000)


@sfx("boss_attack", 0.5, fade=0.08)
def _boss_attack(r):
    n = ns(0.52)
    # launch thump + magic zap, then a volley of crystal shards whooshing past (Doppler drop)
    launch = thud(n, 150, 55, 0.03, 0.08, 0.002)
    zap = U(svf(saw(sweep_exp(n, 1100, 160, 0.05), n), 2600, 0.8)) * env_exp(n, 0.05, 0.002)
    volley = np.zeros(n)
    for st, f0, a in [(0.0, 2350.0, 1.0), (0.045, 2790.0, 0.85), (0.085, 2090.0, 0.9),
                      (0.13, 3130.0, 0.75), (0.17, 2490.0, 0.7)]:
        m = n - ns(st)
        fc = env_log([(0, 700), (0.06, 4200), (0.3, 1600)], m)
        wh = U(svf(white(m, r), fc, 1.6, "bp")) * env_pts([(0, 0), (0.03, 1), (0.14, 0.5), (0.35, 0)], m, 1.5)
        ct = crystal_tone(f0, m / SR, r, decay=0.12, glide=-0.12, glide_tau=0.12, beat=6.0)
        place(volley, ns(st), a * (0.8 * wh + 1.6 * P(ct)))
    rush = U(svf(pink(n, r), env_log([(0, 400), (0.12, 3000), (0.45, 900)], n), 1.0, "bp"))
    rush *= env_pts([(0, 0), (0.06, 1), (0.22, 0.7), (0.5, 0)], n, 1.5)
    sp = P(shards(n, r, 22, 0.01, 0.3, 3500, 9000, 0.005, 0.02, density=[(0.0, 1.0), (0.3, 0.2)]))
    x = 0.45 * launch + 0.3 * zap + 0.9 * P(volley) + 0.25 * rush + 0.18 * sp
    x = sat(x * 0.9, 1.3)
    return room(x, 0.8, 0.18, bright=10000)


@sfx("boss_summon", 1.0, fade=0.12)
def _boss_summon(r):
    n = ns(1.05)
    t = tvec(n)
    u = np.clip(t / 1.0, 0.0, 1.0)
    # chant: a dissonant cluster of formant voices (root, tritone, minor ninth) rising a fifth
    f = 110.0 * 2.0 ** (7.0 / 12.0 * u ** 1.3)
    vib = 1.0 + (0.004 + 0.012 * u) * np.sin(TAU * phase_of(4.5 + 2.0 * u, n))
    voices = np.zeros(n)
    for ratio, det, a in [(1.0, 0.0, 1.0), (1.0, 0.008, 0.7), (2 ** (6 / 12), -0.004, 0.6),
                          (2 ** (13 / 12), 0.003, 0.45), (0.5, 0.0, 0.6)]:
        voices += a * U(saw(f * ratio * (1.0 + det) * vib, n, r.uniform()))
    f1 = env_log([(0, 320), (0.5, 560), (1.05, 700)], n)
    f2 = env_log([(0, 800), (0.5, 1000), (1.05, 1200)], n)
    f3 = env_log([(0, 2300), (1.05, 2700)], n)
    chant = U(formant_bank(voices, [(f1, 1.0), (f2, 0.7), (f3, 0.3)], q=6.0))
    # whirl: a vortex of air whose resonance spins faster and higher
    spin = np.sin(TAU * phase_of(1.5 + 10.0 * u ** 1.5, n))
    whirl = U(svf(white(n, r), (500.0 + 2500.0 * u ** 1.2) * 2.0 ** (0.8 * spin), 3.0, "bp"))
    whirl *= 0.6 + 0.4 * spin
    whirl = U(whirl + 0.7 * vdelay(whirl, (2.0 + 0.75 * (1.0 + spin)) * SR / 1000.0))
    whisper = np.zeros(n)
    place(whisper, ns(0.1), i_whisper(0.85, r))
    sub = U(sine(55.0 * 2.0 ** (7.0 / 12.0 * u ** 1.3), n))
    amp = env_pts([(0, 0), (0.25, 0.45), (0.85, 1.0), (1.05, 0)], n, 1.3)
    x = (0.7 * chant + 0.4 * whirl + 0.3 * sub) * amp + 0.25 * P(whisper)
    x = sat(x * 0.8, 1.3)
    return room(x, 1.5, 0.3, bright=6000)


@sfx("boss_hurt", 0.18, fade=0.03)
def _boss_hurt(r):
    n = ns(0.2)
    # stone cracking: a split, a second crack running on, a knock, rock ring and chips
    crack = U(ffilt(white(n, r), 700, 10000)) * env_exp(n, 0.0035, 0.0002)
    m = ns(0.05)
    crack2 = np.zeros(n)
    place(crack2, ns(0.011), U(ffilt(white(m, r), 1500, 9000)) * env_exp(m, 0.003, 0.0002))
    knock = thud(n, 210, 85, 0.02, 0.035, 0.0008)
    stone = partials(n, 540.0, [1.0, 1.73, 2.62, 3.91, 5.2], [1.0, 0.7, 0.5, 0.35, 0.2],
                     [0.045, 0.03, 0.022, 0.015, 0.01], rng=r, attack=0.0004)
    chips = P(grains(n, r, 12, 0.008, 0.13, 600, 3800, 0.003, 0.01, q=2.0, density=[(0.0, 1.0), (0.13, 0.2)]))
    whine = U(svf(U(square(sweep_exp(n, 880, 420, 0.05), n, 0.3)), 1600, 1.0))
    whine *= env_pts([(0, 0), (0.01, 1), (0.08, 0.4), (0.2, 0)], n, 1.5)
    x = 0.7 * crack + 0.4 * crack2 + 0.8 * knock + 0.4 * P(stone) + 0.3 * chips + 0.16 * whine
    x = sat(x * 0.9, 1.8)
    return room(x, 0.45, 0.12)


@sfx("boss_die", 2.8, fade=0.45)
def _boss_die(r):
    n = ns(2.85)
    # the eye shatters
    crack = U(ffilt(white(n, r), 500, 10000)) * env_exp(n, 0.006, 0.0003)
    shatter = P(shards(n, r, 110, 0.0, 0.5, 1800, 9500, 0.008, 0.06,
                       density=[(0.0, 1.0), (0.08, 0.7), (0.5, 0.05)]))
    # a dying cry: the roar voice collapsing downwards
    m = ns(0.9)
    tm = tvec(m)
    f = env_log([(0, 72), (0.12, 64), (0.9, 26)], m) * (1.0 + 0.04 * smooth_random(m, r, 10.0))
    src = U(saw(f, m)) + 0.8 * U(saw(f * 1.013, m)) + 0.5 * U(square(f * 0.5, m, 0.45))
    src *= 0.55 + 0.45 * np.tanh(3.0 * np.sin(TAU * 28.0 * tm))
    cry = U(formant_bank(src, [(env_log([(0, 450), (0.9, 280)], m), 1.0),
                               (env_log([(0, 850), (0.9, 520)], m), 0.7), (1600.0, 0.25)], q=4.5))
    cry = (cry + 0.3 * cry * np.sin(TAU * 83.0 * tm)) * env_pts([(0, 0), (0.04, 1.0), (0.4, 0.7), (0.9, 0)], m, 1.4)
    voice = np.zeros(n)
    place(voice, ns(0.02), cry)
    # the magic escaping: a falling zap and a downward whoosh
    zap = U(svf(saw(sweep_exp(n, 1600, 70, 0.12), n), 3000, 0.8)) * env_exp(n, 0.18, 0.003)
    whoosh = U(svf(white(n, r), sweep_exp(n, 7000, 250, 0.25), 0.8))
    whoosh *= env_pts([(0, 0), (0.01, 1), (0.3, 0.4), (1.0, 0)], n, 1.5)
    # the collapse: a huge boom as the body hits the ground, then aftershocks
    boom = np.zeros(n)
    for st, f0, f1, tau, a in [(0.3, 64.0, 30.0, 0.5, 1.0), (0.85, 80.0, 40.0, 0.3, 0.45),
                               (1.25, 90.0, 44.0, 0.25, 0.35)]:
        place(boom, ns(st), a * thud(n - ns(st), f0, f1, 0.12, tau, 0.003))
    mb = n - ns(0.3)
    blast = np.zeros(n)
    place(blast, ns(0.3), U(svf(white(mb, r), sweep_exp(mb, 4000, 150, 0.15), 0.7))
          * env_pts([(0, 0), (0.003, 1), (0.1, 0.45), (0.6, 0.1), (1.6, 0)], mb, 1.4))
    rumble = U(ffilt(brown(n, r), 20, 260)) * (0.6 + 0.4 * smooth_random(n, r, 5.0))
    rumble *= env_pts([(0, 0), (0.3, 0.6), (0.4, 1.0), (1.2, 0.6), (2.85, 0)], n, 1.6)
    dens = [(0.25, 0.3), (0.35, 1.0), (1.0, 0.8), (1.8, 0.3), (2.5, 0.05)]
    rocks = P(grains(n, r, 140, 0.25, 2.5, 150, 1100, 0.008, 0.035, q=3.0, density=dens))
    pebbles = P(grains(n, r, 240, 0.25, 2.6, 1000, 6000, 0.002, 0.008, q=1.5, density=dens))
    sand = U(ffilt(pink(n, r), 1500, 7000)) * (0.7 + 0.3 * smooth_random(n, r, 30.0))
    sand *= env_pts([(0, 0), (0.35, 0), (0.5, 1.0), (1.5, 0.6), (2.85, 0)], n, 1.3)
    # the magic fading: falling crystal sparks and a sagging chord dissolving into grains
    sparks = np.zeros(n)
    for k in range(22):
        u = k / 21.0
        st = 0.4 + 2.0 * u ** 1.3 + r.uniform(-0.03, 0.03)
        fk = 2400.0 * 2.0 ** (-2.2 * u) * r.uniform(0.94, 1.06)
        place(sparks, ns(st), (1.0 - 0.6 * u) * r.uniform(0.5, 1.0) * ping(fk, r.uniform(0.1, 0.25)))
    md = ns(2.2)
    um = tvec(md) / 2.2
    chord = np.zeros(md)
    for nm, a in [("D3", 1.0), ("A3", 0.7), ("D4", 0.6), ("F4", 0.5), ("Eb5", 0.25)]:
        chord += a * U(saw(hz(nm) * (1.0 - 0.06 * um ** 1.5), md, r.uniform()))
    chord = U(svf(chord, 2400.0 * (1.0 - 0.8 * um) + 200.0, 0.9))
    chord *= env_pts([(0, 0), (0.25, 1.0), (1.2, 0.6), (2.2, 0)], md, 1.3)
    dissolve = (1.0 - um) * chord + um * sample_hold(chord, 1.0 + 20.0 * um ** 1.5)
    tail = np.zeros(n)
    place(tail, ns(0.55), dissolve)
    x = (0.8 * crack + 0.55 * shatter + 0.6 * voice + 0.25 * zap + 0.35 * whoosh + 1.0 * boom
         + 0.35 * sat(boom * 2.5, 1.0) + 0.7 * blast + 0.6 * rumble + 0.3 * rocks + 0.2 * pebbles
         + 0.15 * sand + 0.15 * P(sparks) + 0.3 * tail)
    x = ffilt(sat(x * 0.8, 2.0), lo=28.0)
    return room(x, 2.0, 0.28)


@sfx("portal_unseal", 1.5, fade=0.25)
def _portal_unseal(r):
    n = ns(1.55)
    t = tvec(n)
    hit = 1.08
    u = np.clip(t / hit, 0.0, 1.0)
    cut = np.clip((hit - t) / 0.02, 0.0, 1.0)  # the build stops dead at the unlock
    # rising shimmer: an octave-climbing open chord with accelerating tremolo
    f = 196.0 * 2.0 ** (u ** 1.4)
    pad = np.zeros(n)
    for ratio, a in [(1.0, 1.0), (1.5, 0.7), (2.0, 0.6), (3.0, 0.35), (4.012, 0.25)]:
        pad += a * np.sin(TAU * phase_of(f * ratio, n, r.uniform()))
        pad += 0.6 * a * np.sin(TAU * phase_of(f * ratio * 1.004, n, r.uniform()))
    trem = 0.6 + 0.4 * np.sin(TAU * phase_of(3.0 + 17.0 * u ** 1.5, n))
    shimmer = U(pad) * trem * (0.3 + 0.7 * u ** 1.4) * cut
    air = U(svf(white(n, r), 900.0 * 2.0 ** (3.0 * u), 3.0, "bp")) * u ** 2 * cut
    sp = P(pings(n, r, 34, 0.1, hit, [hz(m) for m in ("G6", "B6", "D7", "F#7", "A7")], 0.04, 0.1,
                 density=[(0.1, 0.1), (hit, 1.0)])) * cut
    strain = U(ffilt(brown(n, r), 30, 300)) * u ** 2 * cut * (0.7 + 0.3 * smooth_random(n, r, 10.0))
    # the unlock: a latch click, then the heavy seal giving way
    ml = ns(0.08)
    lk = P(partials(ml, 2350.0, [1.0, 1.52, 2.43, 3.3], [1.0, 0.6, 0.4, 0.2],
                    [0.02, 0.015, 0.01, 0.007], rng=r, attack=0.0003))
    lk += 0.5 * U(svf(white(ml, r), 3200, 3.0, "bp")) * env_exp(ml, 0.004, 0.0003)
    latch = np.zeros(n)
    place(latch, ns(hit - 0.07), lk)
    mh = n - ns(hit)
    th = thud(mh, 105, 40, 0.05, 0.25, 0.002)
    clank = partials(mh, 98.0, [1.0, 2.32, 3.88, 5.13, 6.71], [1.0, 0.75, 0.5, 0.35, 0.2],
                     [0.4, 0.28, 0.18, 0.12, 0.08], rng=r, attack=0.001, beat=1.2)
    stone = U(ffilt(white(mh, r), 80, 2500)) * env_exp(mh, 0.03, 0.001)
    mg = ns(0.3)
    grind = U(svf(white(mg, r), 600, 2.0, "bp")) * (0.5 + 0.5 * np.abs(smooth_random(mg, r, 35)))
    grind *= env_pts([(0, 0), (0.02, 1), (0.3, 0)], mg, 1.5)
    bell = np.zeros(mh)
    for nm, a in [("G5", 1.0), ("D6", 0.7), ("G6", 0.5), ("B6", 0.4)]:
        bell += a * fm_bell(hz(nm), mh / SR, ratio=3.5, index=1.0, tau=0.4, idx_tau=0.12)
    unlock = np.zeros(n)
    place(unlock, ns(hit), 1.0 * th + 0.4 * sat(th * 3.0, 1.0) + 0.45 * P(clank) + 0.5 * stone + 0.35 * P(bell))
    place(unlock, ns(hit + 0.02), 0.2 * grind)
    x = 0.55 * shimmer + 0.12 * air + 0.14 * sp + 0.25 * strain + 0.35 * P(latch) + unlock
    x = sat(x * 0.85, 1.5)
    return room(x, 1.3, 0.24, bright=9000)


# =============================================================================
# Music engine: a circular timeline, so every loop is exactly periodic
# =============================================================================

class Loop:
    """Circular multitrack timeline of exactly n samples (events wrap around)."""

    def __init__(self, n: int):
        self.n = int(n)
        self.buses: dict[str, np.ndarray] = {}

    @classmethod
    def tempo(cls, bpm: float, beats: int) -> "Loop":
        return cls(int(round(beats * 60.0 / bpm * SR)))

    @property
    def t(self) -> np.ndarray:
        return tvec(self.n)

    @property
    def dur(self) -> float:
        return self.n / SR

    def bus(self, name: str) -> np.ndarray:
        if name not in self.buses:
            self.buses[name] = np.zeros(self.n)
        return self.buses[name]

    def add(self, name: str, t: float, sig: np.ndarray) -> None:
        place(self.bus(name), int(round(t * SR)), sig, wrap=True)


def smooth_env(n: int, attack: float, release: float) -> np.ndarray:
    """Raised-cosine attack and release (release ends at the last sample)."""
    t = tvec(n)
    a = np.clip(t / max(attack, 1e-4), 0.0, 1.0)
    rl = np.clip((n / SR - t) / max(release, 1e-4), 0.0, 1.0)
    return (0.5 - 0.5 * np.cos(np.pi * a)) * (0.5 - 0.5 * np.cos(np.pi * rl))


def i_epiano(f: float, dur: float, vel: float = 0.7) -> np.ndarray:
    """Soft FM electric piano / harp-like pluck."""
    n = ns(dur)
    t = tvec(n)
    idx = 0.2 + 1.5 * vel * np.exp(-t / 0.3)
    x = np.sin(TAU * f * t + idx * np.sin(TAU * f * t))
    if 4.0 * f < NYQ * 0.9:
        x += 0.18 * vel * np.sin(TAU * 4.0 * f * t) * np.exp(-t / 0.06)
    return vel * x * np.exp(-t / 1.4) * smooth_env(n, 0.004, 0.25)


def i_kalimba(f: float, dur: float, vel: float = 0.7) -> np.ndarray:
    n = ns(dur)
    t = tvec(n)
    x = np.sin(TAU * f * t) * np.exp(-t / 1.3)
    x += 0.12 * np.sin(TAU * 2.0 * f * t) * np.exp(-t / 0.35)
    if 5.95 * f < NYQ * 0.9:
        x += 0.2 * np.sin(TAU * 5.95 * f * t) * np.exp(-t / 0.06)
    if 11.9 * f < NYQ * 0.9:
        x += 0.08 * np.sin(TAU * 11.9 * f * t) * np.exp(-t / 0.025)
    return vel * x * smooth_env(n, 0.002, 0.3)


def i_glass(f: float, dur: float, vel: float = 0.7, decay: float = 3.0, rng=None) -> np.ndarray:
    """Glassy struck bar / bell (free-bar inharmonic ratios)."""
    n = ns(dur)
    x = partials(n, f, [1.0, 2.0, 2.756, 5.404, 8.933], [1.0, 0.12, 0.45, 0.25, 0.1],
                 [decay, decay * 0.5, decay * 0.45, decay * 0.22, decay * 0.1],
                 rng=rng, attack=0.002, beat=0.7)
    return vel * x * smooth_env(n, 0.0, 0.3)


def i_fmbell(f: float, dur: float, vel: float = 0.6, ratio: float = 3.0, index: float = 1.2,
             decay: float = 0.8, idx_tau: float = 0.05) -> np.ndarray:
    n = ns(dur)
    t = tvec(n)
    index *= min(1.0, max(0.0, (NYQ - f) / (2.0 * ratio * f)))  # keep sidebands below Nyquist
    idx = index * vel * np.exp(-t / idx_tau) + 0.08
    x = np.sin(TAU * f * t + idx * np.sin(TAU * ratio * f * t))
    return vel * x * np.exp(-t / decay) * smooth_env(n, 0.002, 0.15)


def i_pad(freqs, dur: float, attack: float = 1.5, release: float = 2.0, detune: float = 0.006,
          voices: int = 3, wave: str = "saw", rng=None, vib: float = 0.0) -> np.ndarray:
    """Detuned multi-voice pad (unfiltered; filter it on the bus)."""
    n = ns(dur)
    t = tvec(n)
    x = np.zeros(n)
    half = max((voices - 1) / 2.0, 1.0)
    for f in freqs:
        for v in range(voices):
            d = 1.0 + detune * (v - (voices - 1) / 2.0) / half
            ph0 = rng.uniform() if rng is not None else 0.0
            fv = f * d
            if vib:
                fv = fv * (1.0 + vib * np.sin(TAU * (0.23 + 0.07 * v) * t + ph0 * TAU))
            if wave == "saw":
                x += saw(fv, n, ph0)
            elif wave == "tri":
                x += tri(fv, n, ph0)
            elif wave == "sine":
                x += np.sin(TAU * phase_of(fv, n, ph0))
            else:  # "mix": warm saw + triangle
                x += 0.6 * saw(fv, n, ph0) + 0.8 * tri(fv, n, ph0)
    return x / (len(freqs) * voices) * smooth_env(n, attack, release)


def i_flute(f: float, dur: float, vel: float = 0.6, rng=None) -> np.ndarray:
    """Soft breathy ocarina/flute voice with delayed vibrato."""
    n = ns(dur)
    t = tvec(n)
    vib = 1.0 + 0.0055 * np.sin(TAU * 5.2 * t) * np.clip((t - 0.2) / 0.4, 0.0, 1.0)
    ph = phase_of(f * vib, n)
    x = np.sin(TAU * ph) + 0.18 * np.sin(2.0 * TAU * ph) + 0.05 * np.sin(3.0 * TAU * ph)
    if rng is not None:
        br = ffilt(white(n, rng), f * 1.0, f * 2.5, order=2)
        x = x + 0.07 * U(br) * (0.35 + 0.65 * np.exp(-t / 0.12))
    return vel * x * smooth_env(n, 0.09, 0.3)


def i_sub(f: float, dur: float, vel: float = 0.6, attack: float = 0.02, release: float = 0.3) -> np.ndarray:
    n = ns(dur)
    t = tvec(n)
    x = np.sin(TAU * f * t) + 0.15 * np.sin(TAU * 2.0 * f * t)
    return vel * x * smooth_env(n, attack, release)


def i_bloop(f: float, dur: float, vel: float, bright: float, q: float = 2.5) -> np.ndarray:
    """Watery 'bloop' arpeggio note: scooped pitch + resonant filter blip.

    bright (0..1) sets how far above the fundamental the filter opens (the wobble).
    """
    n = ns(dur)
    t = tvec(n)
    fr = f * (1.0 - 0.06 * np.exp(-t / 0.02))
    src = 0.7 * tri(fr, n) + 0.3 * np.sin(TAU * phase_of(fr * 2.0, n))
    fc = f * (1.4 + 3.0 * bright) * (0.7 + 0.9 * np.exp(-t / 0.08))
    y = svf(src, fc, q)
    return vel * y * env_exp(n, 0.18, 0.004) * smooth_env(n, 0.0, 0.15)


def i_drip(f0: float, vel: float = 0.5) -> np.ndarray:
    """Water drop 'plink': fast upward chirp."""
    n = ns(0.12)
    t = tvec(n)
    f = f0 * (1.0 + 1.1 * (1.0 - np.exp(-t / 0.012)))
    x = sine(f, n) * env_exp(n, 0.018, 0.0008)
    x += 0.3 * sine(f * 2.3, n) * env_exp(n, 0.008, 0.0008)
    return vel * x


def i_drum(f0: float, vel: float, rng, dur: float = 1.4) -> np.ndarray:
    """Heavy low drum (taiko-like) for the forge."""
    n = ns(dur)
    body = U(sine(sweep_exp(n, f0 * 2.0, f0, 0.035), n)) * env_exp(n, 0.42, 0.002)
    skin = U(sine(sweep_exp(n, f0 * 3.3, f0 * 2.3, 0.03), n)) * env_exp(n, 0.1, 0.001)
    thump = U(ffilt(white(n, rng), 40, 700)) * env_exp(n, 0.035, 0.001)
    slap = U(ffilt(white(n, rng), 800, 4000)) * env_exp(n, 0.006, 0.0005)
    x = 1.0 * body + 0.35 * skin + 0.45 * thump + 0.08 * slap
    return vel * sat(x * 0.7, 1.2) * smooth_env(n, 0.0, 0.2)


def i_anvil(f: float, dur: float, vel: float, rng) -> np.ndarray:
    """Struck metal / anvil resonance."""
    n = ns(dur)
    x = partials(n, f, [1.0, 2.32, 3.88, 5.13, 6.71, 8.4], [1.0, 0.7, 0.5, 0.35, 0.22, 0.15],
                 [dur * 0.45, dur * 0.3, dur * 0.22, dur * 0.15, dur * 0.1, dur * 0.07],
                 rng=rng, attack=0.001, beat=1.3)
    x += 0.3 * U(ffilt(white(n, rng), 2000, 8000)) * env_exp(n, 0.004, 0.0003)
    return vel * x * smooth_env(n, 0.0, 0.2)


def i_whisper(dur: float, rng) -> np.ndarray:
    """Unvoiced formant-filtered noise with syllable-like bursts."""
    n = ns(dur)
    t = tvec(n)
    vowels = [(300, 2300, 3000), (500, 1500, 2500), (700, 1150, 2600), (420, 850, 2400), (600, 1900, 2700)]
    a = vowels[int(rng.integers(len(vowels)))]
    b = vowels[int(rng.integers(len(vowels)))]
    u = np.clip(t / dur, 0.0, 1.0)
    fm_ = [a[i] * (b[i] / a[i]) ** u for i in range(3)]
    src = white(n, rng)
    y = formant_bank(src, [(fm_[0], 0.7), (fm_[1], 1.0), (fm_[2], 0.5)], q=7.0)
    y = U(y) + 0.25 * U(ffilt(src, 3500, 8000))
    env = np.zeros(n)
    for _ in range(int(rng.integers(3, 7))):
        c = rng.uniform(0.1, 0.9) * dur
        w = rng.uniform(0.05, 0.16)
        env += rng.uniform(0.4, 1.0) * np.exp(-0.5 * ((t - c) / w) ** 2)
    return y * env * smooth_env(n, 0.05, 0.1)


def mixdown(L: Loop, spec: dict, t60: float, ir_seed: int, damp: float = 0.5,
            bright: float = 8000.0, predelay: float = 0.02, verbose: bool = False) -> np.ndarray:
    """spec: {bus: (level_db, reverb_send, 'rms'|'peak'[, dry_gain])}.  Circular reverb.

    Buses are normalised (RMS or peak) before the level is applied, so levels are
    relative; a dry_gain < 1 pushes a bus into the distance (mostly reverb).
    """
    dry = np.zeros(L.n)
    send = np.zeros(L.n)
    for name, sp in spec.items():
        lev, snd, norm = sp[:3]
        dry_gain = sp[3] if len(sp) > 3 else 1.0
        x = L.buses[name]
        x = U(x) if norm == "rms" else P(x)
        g = db(lev)
        dry += g * dry_gain * x
        send += g * snd * x
        if verbose:
            print(f"      bus {name:8s} rms {20*np.log10(g*np.sqrt(np.mean(x**2))+1e-12):6.1f} dB"
                  f"  peak {20*np.log10(g*np.max(np.abs(x))+1e-12):6.1f} dB")
    ir = make_ir(t60, predelay=predelay, damp=damp, bright=bright, seed=ir_seed)
    out = dry + circ_convolve(send, ir)
    out -= out.mean()
    return ffilt(out, lo=28.0, order=2, circular=True)


def duck(L: Loop, spb: float, depth: float = 0.3, release: float = 0.15) -> np.ndarray:
    """Periodic 'pumping' gain: quick smooth dip at every beat, slow recovery."""
    x = L.t % spb
    return 1.0 - depth * (1.0 - np.exp(-x / 0.004)) * np.exp(-x / release)


# =============================================================================
# Music tracks
# =============================================================================

MUSIC: dict = {}  # name -> render function returning one exact loop period


def music(name: str):
    def deco(fn):
        MUSIC[name] = fn
        return fn
    return deco


@music("menu")
def music_menu(verbose: bool = False) -> np.ndarray:
    """D major/lydian, 72 BPM, 12 bars: e-piano arpeggios, soft pad, ocarina melody."""
    r = rng_for("music_menu")
    bpm = 72.0
    spb = 60.0 / bpm
    bar = 4 * spb
    L = Loop.tempo(bpm, 48)
    prog = [
        ("D2", ["F#3", "A3", "C#4", "E4"]),   # Dmaj9
        ("B1", ["F#3", "A3", "C#4", "D4"]),   # Bm9
        ("G1", ["F#3", "A3", "B3", "C#4"]),   # Gmaj7#11 (lydian colour)
        ("E2", ["F#3", "G3", "B3", "D4"]),    # Em9
        ("F#2", ["F#3", "A3", "C#4", "E4"]),  # F#m7
        ("A1", ["G3", "A3", "D4", "E4"]),     # A7sus4 -> A7
    ]
    clen = 2 * bar
    pattern = [0, 2, 1, 3, 2, 4, 3, 5, 4, 6, 5, 3, 4, 2, 3, 1]
    for ci, (bass, voicing) in enumerate(prog):
        t0 = ci * clen
        fs = [hz(v) for v in voicing]
        L.add("pad", t0 - 0.6, i_pad(fs, clen + 2.0, attack=1.6, release=2.0, detune=0.005,
                                     voices=3, wave="mix", rng=r))
        L.add("bass", t0, i_sub(hz(bass), clen + 0.3, 0.8, attack=0.25, release=0.8))
        for half in range(2):
            vc = list(voicing)
            if ci == 5 and half == 1:
                vc = ["G3", "A3", "C#4", "E4"]  # resolve sus4 -> 3rd, leads back to D
            pool = sorted([midi(bass) + 12] + [midi(v) for v in vc] + [midi(vc[1]) + 12, midi(vc[2]) + 12])
            for k in range(8):
                kk = half * 8 + k
                if kk > 0 and r.random() < 0.12:
                    continue
                vel = 0.85 if k == 0 else r.uniform(0.45, 0.7)
                L.add("arp", t0 + kk * spb / 2, i_epiano(hz(pool[pattern[kk] % len(pool)]), 1.8, vel))
    # gentle ocarina melody (bars 3-12; bars 1-2 breathe): (bar, beat, note, beats)
    melody = [
        (2, 1, "F#4", 1), (2, 2, "B4", 1), (2, 3, "C#5", 1),
        (3, 0, "D5", 3), (3, 3, "C#5", 1),
        (4, 0, "B4", 2), (4, 2, "A4", 1), (4, 3, "B4", 1),
        (5, 0, "C#5", 4),                                   # lydian #11 over G, held
        (6, 1, "E5", 1), (6, 2, "F#5", 1), (6, 3, "G5", 1),
        (7, 0, "F#5", 2), (7, 2, "E5", 1), (7, 3, "D5", 1),
        (8, 0, "C#5", 3), (8, 3, "E5", 1),
        (9, 0, "A5", 2), (9, 2, "F#5", 1), (9, 3, "E5", 1),
        (10, 0, "D5", 3), (10, 3, "E5", 1),
        (11, 0, "C#5", 4),                                  # leading tone back into D
    ]
    for b, beat, nm, beats in melody:
        vel = (0.62 + 0.05 * min(beats, 3)) * r.uniform(0.93, 1.05)
        L.add("mel", b * bar + beat * spb, i_flute(hz(nm), beats * spb + 0.35, vel, rng=r))
    for _ in range(9):
        L.add("spark", r.uniform(0, L.dur), ping(hz(str(r.choice(["A6", "C#7", "E7", "F#7"]))), 0.25) * r.uniform(0.3, 0.8))
    L.buses["pad"] = chorus(ffilt(L.bus("pad"), 80, 1400, circular=True), 0.25, 3.0, 10.0, 0.5, circular=True)
    L.buses["arp"] = echo(ffilt(L.bus("arp"), 120, 6000, circular=True), 0.75 * spb, 0.35, 2500, 0.35, circular=True)
    L.buses["mel"] = echo(L.bus("mel"), 1.5 * spb, 0.3, 2000, 0.25, circular=True)
    L.buses["spark"] = echo(L.bus("spark"), 0.75 * spb, 0.5, 5000, 0.6, circular=True)
    spec = {"pad": (-15, 0.5, "rms"), "arp": (-12, 0.45, "rms"), "mel": (-13, 0.5, "rms"),
            "bass": (-17, 0.1, "rms"), "spark": (-24, 0.8, "peak", 0.6)}
    return mixdown(L, spec, t60=3.2, ir_seed=101, verbose=verbose)


@music("caves")
def music_caves(verbose: bool = False) -> np.ndarray:
    """Hamyluolat: D drone, sparse D-minor-pentatonic kalimba with echo, water drips."""
    r = rng_for("music_caves")
    L = Loop(ns(44.0))
    n, t = L.n, L.t
    dr = np.zeros(n)
    for f, a in [(hz("D2"), 1.0), (hz("D2") * 1.0021, 0.6), (hz("A2"), 0.45), (hz("D3"), 0.3), (hz("D1"), 0.3)]:
        dr += a * np.sin(TAU * bin_hz(f, n) * t + r.uniform(0, TAU))
    sw = saw(bin_hz(hz("D2"), n), n) + 0.5 * saw(bin_hz(hz("A2") * 1.002, n), n)
    sw = ffilt(sw, 40, 380, circular=True)
    breath = (0.75 + 0.25 * np.sin(TAU * lfo_hz(1 / 22.0, n) * t)
              + 0.1 * np.sin(TAU * lfo_hz(1 / 11.0, n) * t + 1.0))
    L.buses["drone"] = (U(dr) + 0.5 * U(sw)) * breath
    L.buses["rumble"] = (U(ffilt(brown(n, r), 25, 140, circular=True))
                         * (0.7 + 0.3 * smooth_random(n, r, 0.12, circular=True)))
    penta = ["D4", "F4", "G4", "A4", "C5", "D5", "F5", "G5", "A5", "C6"]
    tt = r.uniform(0.5, 1.5)
    while tt < L.dur - 0.5:
        ts = round(tt / 0.5) * 0.5
        if r.random() < 0.25:  # little 2-3 note motif
            idx = int(r.integers(0, len(penta) - 3))
            steps = [0, int(r.choice([1, 2])), int(r.choice([2, 3]))][: int(r.integers(2, 4))]
            for j, s in enumerate(sorted(set(steps))):
                L.add("pluck", ts + j * 0.25, i_kalimba(hz(penta[min(idx + s, len(penta) - 1)]), 2.5, r.uniform(0.5, 0.8)))
        else:
            L.add("pluck", ts, i_kalimba(hz(penta[int(r.integers(len(penta)))]), 2.5, r.uniform(0.45, 0.9)))
        tt += float(r.choice([1.5, 2.0, 2.5, 3.0, 3.5]))
    for _ in range(11):
        td = r.uniform(0, L.dur)
        f0 = r.uniform(1100, 2600) if r.random() < 0.75 else r.uniform(600, 900)
        L.add("drip", td, i_drip(f0, r.uniform(0.4, 1.0)))
        if r.random() < 0.4:
            L.add("drip", td + r.uniform(0.3, 0.9), i_drip(f0 * r.uniform(0.9, 1.1), r.uniform(0.2, 0.5)))
    for c in [9.0, 31.0]:
        m = ns(7.0)
        L.add("swell", c - 3.5, U(ffilt(brown(m, r), 50, 500)) * np.sin(np.pi * np.linspace(0, 1, m)) ** 2)
    L.buses["pluck"] = echo(ffilt(L.bus("pluck"), 150, 5000, circular=True), 0.75, 0.5, 1800, 0.55, circular=True)
    L.buses["drip"] = echo(L.bus("drip"), 0.37, 0.25, 3000, 0.3, circular=True)
    spec = {"drone": (-14, 0.2, "rms"), "rumble": (-22, 0.1, "rms"), "pluck": (-12, 0.55, "rms"),
            "drip": (-17, 0.6, "peak", 0.6), "swell": (-26, 0.5, "rms")}
    return mixdown(L, spec, t60=4.5, ir_seed=202, damp=0.6, bright=4500, verbose=verbose)


@music("fungal")
def music_fungal(verbose: bool = False) -> np.ndarray:
    """Sienisyvanne: A dorian, 96 BPM, 16 bars: wobbly watery bloops, soft pulses, bubbles."""
    r = rng_for("music_fungal")
    bpm = 96.0
    spb = 60.0 / bpm
    bar = 4 * spb
    L = Loop.tempo(bpm, 64)
    n = L.n
    prog = [
        ("A1", ["A3", "C4", "E4", "G4", "B4"]),
        ("D2", ["F#3", "C4", "E4", "A4"]),
        ("A1", ["A3", "C4", "E4", "G4", "B4"]),
        ("D2", ["F#3", "C4", "E4", "A4"]),
        ("F2", ["A3", "C4", "E4", "B4"]),
        ("G2", ["B3", "D4", "E4", "G4"]),
        ("E2", ["G3", "B3", "D4", "F#4"]),
        ("E2", ["A3", "B3", "D4", "E4"]),
    ]
    clen = 2 * bar
    wob_hz = lfo_hz(0.2, n)
    for ci, (bass, voicing) in enumerate(prog):
        t0 = ci * clen
        L.add("pad", t0 - 0.4, i_pad([hz(v) for v in voicing[:4]], clen + 1.2, attack=0.8, release=1.2,
                                     detune=0.008, voices=2, wave="tri", rng=r, vib=0.003))
        for b in range(8):
            L.add("pulse", t0 + b * spb, i_sub(hz(bass), 0.5, 0.9 if b % 4 == 0 else 0.55, attack=0.03, release=0.35))
        pool = sorted(set([midi(v) for v in voicing] + [midi(v) + 12 for v in voicing[:3]]))
        pat = list(range(len(pool))) + list(range(len(pool) - 2, 0, -1))
        for k in range(16):
            if r.random() < 0.18:
                continue
            tt = t0 + k * spb / 2 + (0.02 if k % 2 else 0.0)
            bright = 0.5 + 0.5 * np.sin(TAU * wob_hz * tt)
            m = pool[pat[(k + ci) % len(pat)]]
            L.add("arp", tt, i_bloop(hz(m), 0.7, r.uniform(0.45, 0.8), bright))
    for _ in range(16):
        L.add("bub", r.uniform(0, L.dur), bubble(r.uniform(350, 1100), r.uniform(0.04, 0.09), r.uniform(0.5, 1.0)) * r.uniform(0.3, 1.0))
    pad = chorus(ffilt(L.bus("pad"), 80, 1300, circular=True), 0.35, 5.0, 14.0, 0.6, circular=True)
    L.buses["pad"] = pad * duck(L, spb, 0.3, 0.15)
    L.buses["arp"] = echo(chorus(L.bus("arp"), 0.8, 2.5, 8.0, 0.4, circular=True), 0.75 * spb, 0.4, 2200, 0.4, circular=True)
    spec = {"pad": (-15, 0.4, "rms"), "arp": (-12, 0.4, "rms"), "pulse": (-16, 0.05, "rms"),
            "bub": (-20, 0.6, "peak", 0.7)}
    return mixdown(L, spec, t60=3.0, ir_seed=303, damp=0.55, bright=7000, verbose=verbose)


@music("frost")
def music_frost(verbose: bool = False) -> np.ndarray:
    """Routaulottuvuus: E lydian glass bells, cold sine pad, wind, lots of space."""
    r = rng_for("music_frost")
    L = Loop(ns(48.0))
    n, t = L.n, L.t
    w1 = U(ffilt(pink(n, r), 500, 1600, circular=True))
    w2 = U(ffilt(pink(n, r), 1800, 4500, circular=True))
    x1 = 0.5 + 0.5 * np.sin(TAU * lfo_hz(1 / 16.0, n) * t)
    x2 = 0.5 + 0.5 * np.sin(TAU * lfo_hz(1 / 24.0, n) * t + 2.0)
    gust = 0.6 + 0.4 * smooth_random(n, r, 0.2, circular=True)
    L.buses["wind"] = (w1 * x1 + 0.6 * w2 * x2) * gust
    chords = [["E4", "B4", "D#5", "F#5"], ["C#4", "G#4", "B4", "E5"],
              ["A3", "E4", "B4", "C#5", "D#5"], ["B3", "F#4", "C#5", "E5"]]
    for ci, ch in enumerate(chords):
        L.add("pad", ci * 12.0 - 1.5, i_pad([hz(c) for c in ch], 16.0, attack=4.0, release=5.0,
                                            detune=0.004, voices=2, wave="sine", rng=r, vib=0.002))
    L.buses["floor"] = ((np.sin(TAU * bin_hz(hz("E2"), n) * t) + 0.5 * np.sin(TAU * bin_hz(hz("B2") * 1.001, n) * t))
                        * (0.6 + 0.4 * np.sin(TAU * lfo_hz(1 / 48.0, n) * t)))
    bell_notes = ["E5", "F#5", "G#5", "B5", "C#6", "D#6", "E6", "F#6", "G#6", "B6", "C#7"]
    tt = r.uniform(0.5, 2.0)
    while tt < 47.0:
        k = int(r.integers(len(bell_notes)))
        cnt = 1 if r.random() < 0.6 else int(r.integers(2, 4))
        tj = tt
        for j in range(cnt):
            nm = bell_notes[min(len(bell_notes) - 1, k)]
            L.add("bell", tj, i_glass(hz(nm), 4.5, r.uniform(0.4, 0.9), decay=r.uniform(2.5, 3.8), rng=r))
            k += int(r.choice([1, 2]))
            tj += r.uniform(0.12, 0.22)
        tt += r.uniform(2.2, 4.5)
    for _ in range(10):
        L.add("spark", r.uniform(0, 48.0), ping(hz(str(r.choice(["E7", "G#7", "B7", "D#7"]))), 0.3) * r.uniform(0.3, 1.0))
    L.buses["pad"] = ffilt(L.bus("pad"), 100, 3000, circular=True)
    L.buses["bell"] = echo(L.bus("bell"), 0.9, 0.42, 4000, 0.4, circular=True)
    spec = {"wind": (-22, 0.3, "rms"), "pad": (-16, 0.6, "rms"), "floor": (-24, 0.2, "rms"),
            "bell": (-12, 0.7, "rms"), "spark": (-24, 0.9, "peak", 0.5)}
    return mixdown(L, spec, t60=6.0, ir_seed=404, damp=0.3, bright=10000, verbose=verbose)


@music("forge")
def music_forge(verbose: bool = False) -> np.ndarray:
    """Ahjoulottuvuus: E phrygian, 60 BPM: heavy drum pulses, anvils, rumble, bowed metal."""
    r = rng_for("music_forge")
    bpm = 60.0
    spb = 60.0 / bpm
    bar = 4 * spb
    L = Loop.tempo(bpm, 40)
    n, t = L.n, L.t
    for b in range(10):
        t0 = b * bar
        L.add("drum", t0, i_drum(52.0, 1.0, r))
        L.add("drum", t0 + 2 * spb, i_drum(50.0, 0.75, r))
        if b % 2 == 1:
            L.add("drum", t0 + 3.5 * spb, i_drum(58.0, 0.35, r, dur=0.8))
        if b == 9:
            L.add("drum", t0 + 3.0 * spb, i_drum(55.0, 0.45, r, dur=0.8))
            L.add("drum", t0 + 3.75 * spb, i_drum(60.0, 0.4, r, dur=0.8))
    anv = ["E5", "B4", "F5", "E5", "D5"]
    for i, b in enumerate([0, 2, 4, 6, 8]):
        L.add("anvil", b * bar + 1.0, i_anvil(hz(anv[i]), 2.5, r.uniform(0.6, 0.9), r))
        if r.random() < 0.5:
            L.add("anvil", b * bar + 1.5, i_anvil(hz(anv[i]) * 2 ** (7 / 12), 1.5, 0.35, r))
    for i, nm in enumerate(["E2", "E2", "F2", "E2", "D2"]):
        f = hz(nm)
        L.add("bass", i * 2 * bar - 0.3, i_pad([f, f * 0.5], 2 * bar + 1.0, attack=0.6, release=1.2,
                                                detune=0.004, voices=2, wave="saw", rng=r))
    L.buses["bass"] = ffilt(L.bus("bass"), 30, 260, circular=True)
    L.buses["rumble"] = (U(ffilt(brown(n, r), 20, 110, circular=True))
                         * (0.7 + 0.3 * np.sin(TAU * lfo_hz(1 / 20.0, n) * t)))
    L.buses["roar"] = (U(ffilt(pink(n, r), 150, 600, circular=True))
                       * (0.6 + 0.4 * smooth_random(n, r, 2.5, circular=True)))
    for c, f0 in [(6.0, hz("B4")), (19.0, hz("F5")), (31.0, hz("E5"))]:
        m = ns(9.0)
        tt = tvec(m)
        bow = np.zeros(m)
        for ra, a in [(1.0, 1.0), (1.414, 0.5), (2.76, 0.35), (1.0035, 0.7)]:
            bow += a * np.sin(TAU * f0 * ra * tt + r.uniform(0, TAU))
        L.add("bowed", c - 4.5, bow * np.sin(np.pi * np.linspace(0, 1, m)) ** 2)
    m = ns(2.5)
    L.add("steam", 27.5, U(ffilt(white(m, r), 3000, 8000)) * env_pts([(0, 0), (0.1, 1), (2.5, 0)], m, 1.5))
    L.buses["anvil"] = echo(L.bus("anvil"), 0.75, 0.35, 3000, 0.35, circular=True)
    spec = {"drum": (-9, 0.3, "rms"), "anvil": (-17, 0.6, "rms"), "bass": (-15, 0.15, "rms"),
            "rumble": (-20, 0.1, "rms"), "roar": (-27, 0.2, "rms"), "bowed": (-22, 0.6, "rms"),
            "steam": (-34, 0.5, "rms")}
    return mixdown(L, spec, t60=3.5, ir_seed=505, damp=0.6, bright=6000, verbose=verbose)


@music("crystal")
def music_crystal(verbose: bool = False) -> np.ndarray:
    """Kristalliulottuvuus: E lydian/major, 90 BPM, 16 bars: sparkling 16th arps, chimes, bright pad."""
    r = rng_for("music_crystal")
    bpm = 90.0
    spb = 60.0 / bpm
    bar = 4 * spb
    L = Loop.tempo(bpm, 64)
    n, t = L.n, L.t
    prog = [
        ("E2", ["G#3", "B3", "D#4", "F#4"]),
        ("C#2", ["E3", "G#3", "B3", "D#4"]),
        ("A1", ["G#3", "B3", "C#4", "D#4"]),
        ("B1", ["F#3", "G#3", "C#4", "E4"]),
        ("G#1", ["F#3", "B3", "D#4", "G#4"]),
        ("C#2", ["E3", "G#3", "B3", "D#4"]),
        ("A1", ["G#3", "C#4", "D#4", "E4"]),
        ("B1", ["F#3", "A#3", "D#4", "E4"]),
    ]
    clen = 2 * bar
    for ci, (bass, voicing) in enumerate(prog):
        t0 = ci * clen
        fs = [hz(v) for v in voicing]
        L.add("pad", t0 - 0.5, i_pad(fs, clen + 1.5, attack=1.0, release=1.4, detune=0.007, voices=3, wave="saw", rng=r))
        L.add("shim", t0 - 0.5, i_pad([f * 2 for f in fs], clen + 1.5, attack=1.5, release=1.5, detune=0.002,
                                      voices=2, wave="sine", rng=r))
        L.add("bass", t0, i_sub(hz(bass), clen + 0.2, 0.8, attack=0.1, release=0.6))
        pool = sorted(set([midi(v) + 24 for v in voicing] + [midi(v) + 12 for v in voicing]))
        pool = [m for m in pool if hz(m) < 2600]
        pat = list(range(len(pool))) + list(range(len(pool) - 2, 0, -1))
        for k in range(32):
            if r.random() < 0.35:
                continue
            vel = (0.75 if k % 4 == 0 else 0.45) * r.uniform(0.8, 1.1)
            m = pool[pat[(k + 3 * ci) % len(pat)]]
            L.add("arp", t0 + k * spb / 4, i_fmbell(hz(m), 0.9, vel, ratio=3.0, index=1.0, decay=0.35, idx_tau=0.03))
    chime_notes = ["B6", "C#7", "D#7", "E7", "F#7", "G#7", "B7"]
    for _ in range(36):
        L.add("chime", r.uniform(0, L.dur), ping(hz(str(r.choice(chime_notes))), r.uniform(0.3, 0.8), bright=0.2) * r.uniform(0.2, 1.0))
    L.buses["shim"] = L.bus("shim") * (0.75 + 0.25 * np.sin(TAU * lfo_hz(3.0, n) * t))
    L.buses["pad"] = chorus(ffilt(L.bus("pad"), 150, 2400, circular=True), 0.3, 4.0, 12.0, 0.5, circular=True)
    L.buses["arp"] = echo(L.bus("arp"), 0.75 * spb, 0.45, 5000, 0.45, circular=True)
    L.buses["chime"] = echo(L.bus("chime"), 0.75 * spb, 0.5, 6000, 0.5, circular=True)
    spec = {"pad": (-18, 0.45, "rms"), "shim": (-23, 0.6, "rms"), "bass": (-18, 0.1, "rms"),
            "arp": (-11, 0.5, "rms"), "chime": (-19, 0.8, "peak", 0.6)}
    return mixdown(L, spec, t60=4.0, ir_seed=606, damp=0.25, bright=11000, verbose=verbose)


@music("void")
def music_void(verbose: bool = False) -> np.ndarray:
    """Tyhjyys: detuned drifting clusters, slow dissonant swells, distant whispers."""
    r = rng_for("music_void")
    L = Loop(ns(48.0))
    n, t = L.n, L.t
    pad = np.zeros(n)
    voices = [("C3", -18, 1.0), ("C3", 14, 0.9), ("Db3", 6, 0.6), ("Gb3", -12, 0.7),
              ("Gb3", 20, 0.5), ("C2", 0, 0.8), ("Bb3", -25, 0.35)]
    for i, (nm, cents, a) in enumerate(voices):
        f = bin_hz(hz(nm) * 2 ** (cents / 1200.0), n)
        lf = lfo_hz(1.0 / 48.0, n)
        beta = 0.006 * f / lf  # about +/-10 cents of slow drift, exactly periodic
        p = TAU * f * t + beta * np.sin(TAU * lf * t + i * 0.9)
        tone = np.sin(p) + 0.25 * np.sin(2 * p) + 0.12 * np.sin(3 * p)
        amp = 0.6 + 0.4 * np.sin(TAU * lfo_hz((i % 3 + 1) / 48.0, n) * t + i * 1.7)
        pad += a * tone * amp
    L.buses["pad"] = ffilt(pad, 40, 900, circular=True)
    swells = [(4.0, ["E4", "F4", "Bb4", "B4"]), (16.0, ["D4", "Eb4", "A4", "Ab4"]),
              (28.0, ["F#4", "G4", "C5", "Db5"]), (40.0, ["A3", "Bb3", "E4", "Eb5"])]
    for c, notes in swells:
        L.add("swell", c - 1.0, i_pad([hz(x) for x in notes], 11.0, attack=5.0, release=5.5,
                                      detune=0.01, voices=2, wave="mix", rng=r, vib=0.004))
    L.buses["swell"] = ffilt(L.bus("swell"), 150, 1800, circular=True)
    for _ in range(9):
        L.add("whisper", r.uniform(0, 48.0), i_whisper(r.uniform(1.2, 2.4), r) * r.uniform(0.5, 1.0))
    L.buses["sub"] = ((np.sin(TAU * bin_hz(55.0, n) * t) + 0.7 * np.sin(TAU * bin_hz(55.1, n) * t))
                      * (0.7 + 0.3 * np.sin(TAU * lfo_hz(1 / 24.0, n) * t)))
    for c in [11.0, 35.0]:
        m = ns(4.0)
        u = np.linspace(0, 1, m)
        rs = U(ffilt(white(m, r), 400, 3000)) * u ** 3 * (1.0 - np.clip((u - 0.97) / 0.03, 0.0, 1.0))
        L.add("rev", c - 4.0, rs)
    spec = {"pad": (-14, 0.5, "rms"), "swell": (-17, 0.7, "rms"), "whisper": (-15, 0.9, "peak", 0.35),
            "sub": (-20, 0.1, "rms"), "rev": (-15, 0.8, "peak", 0.5)}
    return mixdown(L, spec, t60=7.0, ir_seed=707, damp=0.5, bright=7000, verbose=verbose)


def i_wardrum(f0: float, vel: float, rng, dur: float = 0.7, decay: float = 0.2) -> np.ndarray:
    """Tight, punchy war drum (taiko / low tom) for driving patterns."""
    n = ns(dur)
    body = U(sine(sweep_exp(n, f0 * 2.2, f0, 0.022), n)) * env_exp(n, decay, 0.0015)
    skin = U(sine(sweep_exp(n, f0 * 3.4, f0 * 2.4, 0.018), n)) * env_exp(n, decay * 0.3, 0.001)
    thump = U(ffilt(white(n, rng), 40, 900)) * env_exp(n, 0.022, 0.0008)
    slap = U(ffilt(white(n, rng), 900, 5000)) * env_exp(n, 0.005, 0.0004)
    x = 1.0 * body + 0.35 * skin + 0.5 * thump + 0.12 * slap
    return vel * sat(x * 0.8, 1.4) * smooth_env(n, 0.0, 0.1)


def i_snare(vel: float, rng, dur: float = 0.22, tone: float = 190.0) -> np.ndarray:
    """Dark, dry war snare: pitched shell, wire rattle, stick crack."""
    n = ns(dur)
    shell = U(sine(sweep_exp(n, tone * 1.5, tone, 0.01), n)) * env_exp(n, 0.04, 0.001)
    wires = U(ffilt(white(n, rng), 1400, 7000, peaks=[(3300.0, 2.0, 4.0)])) * env_exp(n, 0.06, 0.0008)
    crack = U(ffilt(white(n, rng), 500, 9000)) * env_exp(n, 0.005, 0.0003)
    x = 0.8 * shell + 0.65 * wires + 0.35 * crack
    return vel * sat(x * 0.7, 1.3) * smooth_env(n, 0.0, 0.04)


def i_shaker(vel: float, rng, dur: float = 0.07) -> np.ndarray:
    n = ns(dur)
    return vel * U(ffilt(white(n, rng), 4500, 10000)) * env_pts([(0, 0), (0.004, 1), (dur, 0)], n, 2.0)


def i_gong(f0: float, dur: float, vel: float, rng) -> np.ndarray:
    """Dark tam-tam: dense inharmonic modes; the upper ones bloom in after the strike."""
    n = ns(dur)
    t = tvec(n)
    out = np.zeros(n)
    for i in range(28):
        f = f0 * (1.0 + 0.62 * i + 0.022 * i * i) * rng.uniform(0.97, 1.03)
        if f > 6000.0:
            break
        a = rng.uniform(0.5, 1.0) / (1.0 + 0.12 * i)
        dec = dur * rng.uniform(0.18, 0.4) / (1.0 + 0.06 * i)
        bloom = 1.0 - np.exp(-t / (0.004 + 0.02 * i))
        out += a * np.sin(TAU * f * t + rng.uniform(0.0, TAU)) * np.exp(-t / dec) * bloom
    strike = U(ffilt(white(n, rng), 80, 2500)) * env_exp(n, 0.015, 0.001)
    return vel * (U(out) + 0.4 * strike) * smooth_env(n, 0.002, 0.5)


def i_brass(freqs, dur: float, vel: float, rng, bright: float = 1.0, attack: float = 0.01,
            release: float = 0.08, swell: float = 0.0) -> np.ndarray:
    """Brass-like synth section: detuned saws with a pitch scoop, a filter that blooms on
    the attack (or slowly over `swell` seconds), and tanh grit."""
    n = ns(dur)
    t = tvec(n)
    scoop = 1.0 - 0.02 * np.exp(-t / 0.03)
    x = np.zeros(n)
    for f in freqs:
        for det in (-0.005, 0.0, 0.0045):
            x += saw(f * (1.0 + det) * scoop, n, rng.uniform())
    if swell > 0:
        fenv = np.clip(t / swell, 0.0, 1.0) ** 2
        amp = 0.15 + 0.85 * np.clip(t / swell, 0.0, 1.0) ** 1.5
    else:
        fenv = (1.0 - np.exp(-t / 0.012)) * (0.45 + 0.55 * np.exp(-t / 0.15))
        amp = 1.0
    y = svf(x, np.minimum(450.0 + 3200.0 * bright * fenv, 7000.0), 1.0)
    y = np.tanh(2.2 * y / (np.max(np.abs(y)) + 1e-9))
    return vel * y * amp * smooth_env(n, attack, release)


def i_horn(f: float, dur: float, vel: float, rng) -> np.ndarray:
    """Dark legato horn: two saws, a slow filter bloom, delayed vibrato."""
    n = ns(dur)
    t = tvec(n)
    vib = 1.0 + 0.005 * np.sin(TAU * 5.0 * t + rng.uniform(0.0, TAU)) * np.clip((t - 0.2) / 0.3, 0.0, 1.0)
    fv = f * vib * (1.0 - 0.015 * np.exp(-t / 0.04))
    x = saw(fv, n, rng.uniform()) + 0.8 * saw(fv * 1.0035, n, rng.uniform())
    bloom = (1.0 - np.exp(-t / 0.07)) * (0.7 + 0.3 * np.exp(-t / 0.4))
    y = svf(x, np.minimum(f * (1.5 + 4.0 * bloom), 6000.0), 0.9)
    y = np.tanh(1.8 * y / (np.max(np.abs(y)) + 1e-9))
    return vel * y * smooth_env(n, 0.035, min(0.15, dur * 0.3))


def i_bass(f: float, dur: float, vel: float, cutoff: float, rng) -> np.ndarray:
    """Driving dark synth bass: saw + pulse through a plucky resonant low-pass, plus a sine root."""
    n = ns(dur)
    t = tvec(n)
    x = saw(f, n, rng.uniform()) + 0.6 * square(f * 1.004, n, 0.42, rng.uniform())
    y = svf(x, np.minimum(cutoff * (1.0 + 2.5 * vel * np.exp(-t / 0.04)), 6000.0), 1.5)
    y = y + 0.7 * np.sin(TAU * f * t)
    return vel * sat(y * 0.7, 1.5) * smooth_env(n, 0.003, min(0.03, dur * 0.35))


def i_riser(dur: float, rng, f0: float = 300.0, f1: float = 7000.0) -> np.ndarray:
    """Tension riser: a band of noise sweeping up and swelling, cut dead at the downbeat."""
    n = ns(dur)
    t = tvec(n)
    u = t / dur
    x = U(svf(white(n, rng), f0 * (f1 / f0) ** (u ** 1.4), 2.0, "bp"))
    x = x + 0.4 * U(ffilt(white(n, rng), 4000, 10000)) * u ** 2
    return x * u ** 2.2 * np.clip((dur - t) / 0.008, 0.0, 1.0)


@music("boss")
def music_boss(verbose: bool = False) -> np.ndarray:
    """Portinvartija: D phrygian / harmonic minor, 128 BPM, 24 bars: war drums, a galloping
    bass ostinato, dissonant brass stabs, dark choir and a horn line.  Tension climbs over
    the loop (opening bass filter, chromatic harmony, tremolo strings, riser, snare roll)
    into the loop point, where a gong + brass hit restarts it."""
    r = rng_for("music_boss")
    bpm = 128.0
    spb = 60.0 / bpm
    bar = 4 * spb
    s16 = spb / 4
    L = Loop.tempo(bpm, 96)  # 45 s
    t = L.t
    # name: (bass root, choir voicing, dissonant stab voicing, ostinato neighbour, fifth)
    CH = {
        "Dm": ("D2", ["D3", "F3", "A3", "D4"], ["D3", "A3", "Eb4", "F4"], 1, 7),     # m(b9)
        "Dm5": ("D2", ["D3", "F3", "A3", "D4"], ["D3", "Ab3", "D4", "F4"], 1, 7),    # m(b5)
        "Bb": ("Bb1", ["Bb2", "F3", "A3", "D4"], ["Bb2", "F3", "A3", "E4"], -1, 7),  # maj7#11
        "A": ("A1", ["A2", "E3", "G3", "C#4"], ["A2", "G3", "Bb3", "C#4"], 1, 7),    # 7b9
        "Eb": ("Eb2", ["Eb3", "G3", "Bb3", "D4"], ["Eb3", "Bb3", "D4", "A4"], -1, 7),
        "Edim": ("E2", ["E3", "G3", "Bb3", "C#4"], ["E3", "Bb3", "C#4", "G4"], 1, 6),
        "F": ("F2", ["F3", "A3", "C4", "E4"], ["F3", "C4", "E4", "B4"], -1, 7),
    }
    bars = (["Dm", "Dm", "Dm5", "Dm5", "Bb", "Bb", "A", "A"]          # A: drums, bass, choir, stabs
            + ["Dm", "Dm", "Eb", "Eb", "Bb", "Bb", "A", "A"]          # B: + snare, horn theme
            + ["Dm", "Dm", "Eb", "Eb", "Edim", "F", "A", "A"])        # C: climbing, riser, roll
    # --- bass ostinato: a gallop (8th + two 16ths), filter opening across the loop ---
    gallop = [(0, 0, 1.0), (2, 0, 0.55), (3, 0, 0.62), (4, 12, 0.85), (6, 0, 0.55), (7, 0, 0.62),
              (8, 0, 0.95), (10, 0, 0.55), (11, "N", 0.7), (12, "5", 0.8), (14, "N", 0.65), (15, 0, 0.6)]
    for b, name in enumerate(bars):
        root, _, _, nb, fifth = CH[name]
        cutoff = 330.0 * 2.0 ** (1.4 * b / 23.0)
        steps = [(0, 0, 1.0)] + gallop[6:] if b == 0 else gallop  # bar 0: let the big hit ring
        for i, (st, iv, v) in enumerate(steps):
            nxt = steps[i + 1][0] if i + 1 < len(steps) else 16
            semi = nb if iv == "N" else fifth if iv == "5" else iv
            dur = max(0.07, (nxt - st) * s16 * 0.92) + 0.03
            vel = v * r.uniform(0.93, 1.03)
            L.add("bass", b * bar + st * s16, i_bass(hz(midi(root) + semi), dur, vel, cutoff, r))
    # --- drums ---
    for b in range(24):
        t0 = b * bar
        sec = b // 8
        for st, v in [(0, 1.0), (6, 0.6), (8, 0.85), (14, 0.5)] + ([(10, 0.45)] if sec == 2 else []):
            if b == 23 and st >= 8:
                continue
            L.add("taiko", t0 + st * s16, i_wardrum(52.0, v * r.uniform(0.92, 1.04), r))
        for st, v in [(4, 0.75), (12, 0.8)] + ([(11, 0.4), (15, 0.45)] if sec >= 1 else []):
            L.add("tom", t0 + st * s16, i_wardrum(98.0 if st in (4, 12) else 122.0, v * r.uniform(0.9, 1.05), r,
                                                  dur=0.45, decay=0.11))
        if sec >= 1 and b < 22:
            for st in (4, 12):
                L.add("snare", t0 + st * s16, i_snare(r.uniform(0.75, 0.85), r))
        for st in range(0, 16, 1 if b >= 4 else 2):  # shaker: 8ths at first, then 16ths
            v = (0.9 if st % 4 == 0 else 0.6 if st % 2 == 0 else 0.4) * r.uniform(0.8, 1.1)
            L.add("hat", t0 + st * s16, i_shaker(v * (0.55 if b < 4 else 0.7 if sec == 0 else 1.0), r))
    for j in range(8):  # bar 22: snare 8ths building
        L.add("snare", 22 * bar + j * 2 * s16, i_snare(0.25 + 0.3 * j / 7.0, r, dur=0.18))
    roll = [23 * bar + i * s16 for i in range(8)] + [23 * bar + 2 * spb + j * s16 / 2 for j in range(16)]
    for k, tr in enumerate(roll):  # bar 23: 16ths then 32nds, crescendo into the loop point
        L.add("snare", tr, i_snare(0.3 + 0.55 * (k / (len(roll) - 1)) ** 1.3, r, dur=0.13))
    for j in range(4):
        L.add("taiko", 23 * bar + 2 * spb + j * spb / 2, i_wardrum(60.0 - 3.0 * j, 0.6 + 0.12 * j, r))
    L.add("gong", 0.0, i_gong(68.0, 5.0, 1.0, r))
    L.add("gong", 16 * bar, i_gong(74.0, 4.0, 0.6, r))
    L.add("sub", 0.0, thud(ns(1.6), 72.0, 34.0, 0.18, 0.55, 0.002))
    L.add("sub", 16 * bar, 0.7 * thud(ns(1.4), 72.0, 36.0, 0.15, 0.45, 0.002))
    # --- brass stabs: (step, length in 16ths, velocity) for the 1st / 2nd bar of each pair ---
    stab_pat = {
        0: ([(0, 6, 1.0)], [(12, 2, 0.6), (14, 2, 0.7)]),
        1: ([(0, 3, 1.0), (3, 2, 0.7), (6, 3, 0.8)], [(8, 6, 0.9)]),
        2: ([(0, 3, 1.0), (3, 2, 0.75), (6, 2, 0.8), (10, 2, 0.75), (12, 4, 0.9)],
            [(0, 3, 0.9), (3, 2, 0.7), (6, 2, 0.75), (8, 3, 0.85), (11, 2, 0.75), (14, 2, 0.8)]),
    }
    for b, name in enumerate(bars[:22]):
        sec = b // 8
        stab = [hz(x) for x in CH[name][2]]
        for st, ln, v in stab_pat[sec][b % 2]:
            L.add("stab", b * bar + st * s16, i_brass(stab, ln * s16 + 0.12, v * (0.9 + 0.05 * sec), r))
    stab = [hz(x) for x in CH["A"][2]]
    L.add("stab", 22 * bar, i_brass(stab, bar + 0.1, 0.9, r, swell=0.9 * bar, release=0.05))
    for j in range(4):
        L.add("stab", 23 * bar + j * spb, i_brass(stab, 2 * s16 + 0.1, 0.7 + 0.1 * j, r))
    # --- horn: theme in B, an octave-higher urgent line in C, resolving onto D at the loop ---
    horn = [(8, 0, "D4", 6), (8, 6, "Eb4", 2), (8, 8, "D4", 4), (8, 12, "C4", 4),
            (9, 0, "Bb3", 8), (9, 8, "A3", 8),
            (10, 0, "Eb4", 6), (10, 6, "F4", 2), (10, 8, "G4", 8),
            (11, 0, "F4", 4), (11, 4, "Eb4", 4), (11, 8, "D4", 8),
            (12, 0, "D4", 6), (12, 6, "F4", 2), (12, 8, "A4", 8),
            (13, 0, "G4", 4), (13, 4, "F4", 4), (13, 8, "E4", 8),
            (14, 0, "C#4", 8), (14, 8, "D4", 4), (14, 12, "E4", 4),
            (15, 0, "F4", 6), (15, 6, "E4", 2), (15, 8, "C#4", 8),
            (16, 0, "A4", 6), (16, 6, "Bb4", 2), (16, 8, "A4", 4), (16, 12, "F4", 4),
            (17, 0, "D5", 8), (17, 8, "C5", 8),
            (18, 0, "Bb4", 6), (18, 6, "C5", 2), (18, 8, "D5", 8),
            (19, 0, "Eb5", 8), (19, 8, "D5", 8),
            (20, 0, "C#5", 8), (20, 8, "E5", 8),
            (21, 0, "F5", 8), (21, 8, "E5", 8),
            (22, 0, "C#5", 16), (23, 0, "E5", 16),
            (0, 0, "D5", 14)]
    for b, st, nm, ln in horn:
        vel = (0.8 if ln >= 8 else 0.7) * r.uniform(0.95, 1.05)
        L.add("horn", b * bar + st * s16, i_horn(hz(nm), ln * s16 + 0.12, vel, r))
    # --- dark choir, one swell per chord span ---
    b = 0
    while b < 24:
        e = b
        while e + 1 < 24 and CH[bars[e + 1]][1] == CH[bars[b]][1]:
            e += 1
        fs = [hz(x) for x in CH[bars[b]][1]]
        L.add("choir", b * bar - 0.15, i_pad(fs, (e - b + 1) * bar + 0.5, attack=0.35, release=0.5,
                                             detune=0.006, voices=3, wave="saw", rng=r, vib=0.002))
        b = e + 1
    # --- section C: tremolo strings climbing chromatically on top ---
    trem = {16: ("A4", "D5"), 17: ("A4", "D5"), 18: ("Bb4", "Eb5"), 19: ("Bb4", "Eb5"),
            20: ("Bb4", "E5"), 21: ("C5", "F5"), 22: ("C#5", "G5"), 23: ("E5", "Bb5")}
    for b, (lo, hi) in trem.items():
        L.add("trem", b * bar - 0.02, (0.5 + 0.5 * (b - 16) / 7.0)
              * i_pad([hz(lo), hz(hi)], bar + 0.1, attack=0.05, release=0.08, detune=0.004, voices=3,
                      wave="saw", rng=r))
    # --- risers into section C and into the loop point ---
    L.add("riser", 15 * bar, 0.6 * i_riser(bar, r, 400.0, 5000.0))
    L.add("riser", 22 * bar, i_riser(2 * bar, r))
    # --- the guardian's eye: sparse crystal motif ---
    for b, st, nm in [(1, 8, "D6"), (1, 11, "Eb6"), (3, 8, "A5"), (5, 8, "F6"), (5, 11, "E6"),
                      (7, 8, "C#6"), (7, 12, "Bb5"), (16, 0, "D6"), (18, 0, "Eb6"), (20, 0, "E6"), (21, 0, "F6")]:
        L.add("bell", b * bar + st * s16, i_glass(hz(nm), 3.0, r.uniform(0.6, 0.85), decay=1.6, rng=r))
    # --- bus processing (all circular) ---
    L.buses["choir"] = (chorus(ffilt(L.bus("choir"), 90, 3200, circular=True,
                                     peaks=[(650.0, 3.0, 9.0), (1080.0, 4.0, 7.0), (2500.0, 5.0, 4.0)]),
                               0.3, 3.0, 11.0, 0.5, circular=True) * duck(L, spb, 0.35, 0.12))
    gate32 = 0.25 + 0.75 * (0.5 + 0.5 * np.cos(TAU * t / (s16 / 2))) ** 2  # 768 cycles per loop
    L.buses["trem"] = ffilt(L.bus("trem"), 300, 4500, circular=True) * gate32
    L.buses["stab"] = echo(L.bus("stab"), 3 * s16, 0.25, 2500, 0.2, circular=True)
    L.buses["bell"] = echo(L.bus("bell"), 3 * s16, 0.4, 3500, 0.4, circular=True)
    L.buses["bass"] = L.bus("bass") * duck(L, spb, 0.15, 0.08)
    for name in ("taiko", "tom", "snare"):  # drum-bus saturation: round off the transient peaks
        L.buses[name] = np.tanh(1.5 * P(L.bus(name)))
    spec = {"taiko": (-9, 0.2, "rms"), "tom": (-15, 0.2, "rms"), "snare": (-18, 0.25, "rms"),
            "hat": (-27, 0.1, "rms"), "gong": (-12, 0.6, "peak"), "sub": (-12, 0.0, "peak"),
            "bass": (-12, 0.05, "rms"), "stab": (-13, 0.35, "rms"), "horn": (-14, 0.35, "rms"),
            "choir": (-17, 0.5, "rms"), "trem": (-20, 0.35, "rms"), "riser": (-16, 0.4, "peak"),
            "bell": (-20, 0.7, "peak", 0.7)}
    out = mixdown(L, spec, t60=2.4, ir_seed=808, damp=0.55, bright=6000, verbose=verbose)
    return circ_limiter(out, crest_db=12.0, max_red_db=4.0)  # a little master glue (circular)


# =============================================================================
# Rendering, WAV output, analysis
# =============================================================================

def finalize_sfx(x: np.ndarray, dur: float, fade: float) -> np.ndarray:
    """Cut to length, remove DC, trim trailing silence, fade, normalise to -3 dBFS."""
    x = fit(np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0), ns(dur))
    x = dc_block(x, 18.0)
    pk = np.max(np.abs(x)) + 1e-12
    loud = np.nonzero(np.abs(x) > pk * db(-60.0))[0]
    if len(loud):
        x = x[: min(len(x), loud[-1] + 1 + ns(0.004))]
    fi = min(ns(0.0015), len(x) // 4)
    if fi > 1:
        x[:fi] *= np.linspace(0.0, 1.0, fi)
    fo = min(ns(fade), len(x) // 2)
    if fo > 1:
        x[-fo:] *= (0.5 + 0.5 * np.cos(np.linspace(0.0, np.pi, fo))) ** 1.5
    x[-1] = 0.0
    return x * (db(SFX_PEAK_DB) / (np.max(np.abs(x)) + 1e-12))


def circ_limiter(x: np.ndarray, crest_db: float = 15.0, max_red_db: float = 6.0,
                 block: int = 64) -> np.ndarray:
    """Gentle look-around peak limiter on a periodic signal (gain curve is circular).

    Peaks above RMS + crest_db are pulled down (by at most max_red_db) with a
    smooth gain curve, so isolated transients do not dictate the loop's loudness.
    """
    n = len(x)
    rms = np.sqrt(np.mean(x ** 2)) + 1e-12
    thr = max(rms * db(crest_db), np.max(np.abs(x)) * db(-max_red_db))
    need = np.minimum(1.0, thr / (np.abs(x) + 1e-12))
    nb = -(-n // block)
    padded = np.concatenate([need, np.ones(nb * block - n)])
    bmin = padded.reshape(nb, block).min(axis=1)
    bmin = np.minimum(np.minimum(bmin, np.roll(bmin, 1)), np.roll(bmin, -1))  # look-around
    g = np.repeat(bmin, block)[:n]
    gs = ffilt(g, hi=SR / (block * 6.0), order=1, circular=True)  # smooth gain changes
    y = x * np.minimum(gs, 1.0)
    over = np.abs(y) > thr
    if np.any(over):  # catch smoothing residue softly
        y = np.where(over, np.sign(y) * thr * (1.0 + np.tanh(np.abs(y) / thr - 1.0) * 0.1), y)
    return y


def finalize_loop(x: np.ndarray, peak_db: float, limit: bool = False) -> np.ndarray:
    """Circular DC/sub-sonic removal, optional gentle limiting, peak normalisation.

    Every step is circular (or memoryless), so exact periodicity is preserved.
    """
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    x = ffilt(x - x.mean(), lo=20.0, order=1, circular=True)
    if limit:
        x = circ_limiter(x)
    return x * (db(peak_db) / (np.max(np.abs(x)) + 1e-12))


def write_wav(path: Path, x: np.ndarray, loop: bool = False) -> None:
    """16-bit mono PCM.  Loops get a duplicate first sample at the end and a 'smpl' chunk."""
    pcm = np.clip(np.round(x * 32767.0), -32768, 32767).astype("<i2")
    if loop:
        pcm = np.concatenate([pcm, pcm[:1]])
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    if loop:
        n_loop = len(pcm) - 1
        body = struct.pack("<9I", 0, 0, int(round(1e9 / SR)), 60, 0, 0, 0, 1, 0)
        body += struct.pack("<6I", 0, 0, 0, n_loop, 0, 0)  # cue id, forward, start, end, fraction, infinite
        with open(path, "r+b") as f:
            f.seek(0, 2)
            f.write(b"smpl" + struct.pack("<I", len(body)) + body)
            size = f.tell()
            f.seek(4)
            f.write(struct.pack("<I", size - 8))


def read_wav(path: Path):
    """Return (samples float, sample rate, channels, sample width, smpl loop (start, end) or None)."""
    with wave.open(str(path), "rb") as w:
        ch, sw, fr, nf = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        x = np.frombuffer(w.readframes(nf), dtype="<i2").astype(np.float64) / 32768.0
    loop = None
    raw = path.read_bytes()
    i = raw.find(b"smpl")
    if i >= 0:
        vals = struct.unpack("<15I", raw[i + 8: i + 8 + 60])
        if vals[7] >= 1:
            loop = (vals[11], vals[12])
    return x, fr, ch, sw, loop


def analyze(paths, loops: set[str]) -> int:
    """Print a table of basic quality metrics; returns the number of problems."""
    problems = 0
    print(f"\n{'file':24s} {'dur s':>6s} {'peak':>6s} {'rms':>6s} {'clip':>4s} {'dc':>7s} "
          f"{'start':>6s} {'end':>6s} {'cent Hz':>7s}  loop seam")
    for p in paths:
        x, fr, ch, sw, loop = read_wav(p)
        name = p.stem
        bad = []
        if fr != SR or ch != 1 or sw != 2:
            bad.append(f"format {fr}/{ch}/{sw}")
        if not np.all(np.isfinite(x)):
            bad.append("non-finite")
        pk = np.max(np.abs(x)) + 1e-12
        rms = np.sqrt(np.mean(x ** 2)) + 1e-12
        clip = int(np.sum(np.abs(x) >= 32767 / 32768.0))
        dc = float(np.mean(x))
        spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
        fq = np.fft.rfftfreq(len(x), 1.0 / SR)
        cent = float(np.sum(spec * fq) / (np.sum(spec) + 1e-12))
        seam = ""
        is_loop = p.parent.name == "music" or name in loops
        if is_loop:
            body = x[:-1]
            d = np.abs(np.diff(body))
            jump = abs(body[-1] - body[0])
            ref = np.percentile(d, 99.9) + 1e-12
            w = ns(0.05)
            r_head = np.sqrt(np.mean(body[:w] ** 2))
            r_tail = np.sqrt(np.mean(body[-w:] ** 2))
            seam = (f"jump {jump:.4f} ({jump / ref:4.2f}x p99.9 step), dup {'ok' if x[-1] == x[0] else 'NO'},"
                    f" rms head/tail {20 * np.log10((r_head + 1e-9) / (r_tail + 1e-9)):+.1f} dB,"
                    f" smpl {loop}")
            if jump > ref or x[-1] != x[0] or loop != (0, len(body)):
                bad.append("loop seam")
        else:
            if abs(x[0]) > 0.02 or abs(x[-1]) > 0.002:
                bad.append("edge not faded")
        target = MUSIC_PEAK_DB if p.parent.name == "music" else SFX_PEAK_DB
        if abs(20 * np.log10(pk) - target) > 0.3:
            bad.append("peak level")
        if clip:
            bad.append("clipping")
        print(f"{name:24s} {len(x) / fr:6.3f} {20 * np.log10(pk):6.1f} {20 * np.log10(rms):6.1f} {clip:4d} "
              f"{dc:+7.4f} {x[0]:+6.3f} {x[-1]:+6.3f} {cent:7.0f}  {seam}"
              + (f"  <-- {', '.join(bad)}" if bad else ""))
        problems += bool(bad)
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="generate only these names (sfx or music)")
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--no-sfx", action="store_true")
    ap.add_argument("--analyze", action="store_true", help="only analyse existing files")
    ap.add_argument("--verbose", action="store_true", help="print music bus levels")
    args = ap.parse_args(argv)
    only = set(args.only or [])
    loops = {k for k, v in SFX.items() if v["loop"]}
    written = []
    if not args.analyze:
        t_all = time.time()
        if not args.no_sfx:
            for name, spec in SFX.items():
                if only and name not in only:
                    continue
                t0 = time.time()
                x = spec["fn"](rng_for(name))
                if not np.all(np.isfinite(x)):
                    raise RuntimeError(f"{name}: non-finite samples")
                if spec["loop"]:
                    x = finalize_loop(x, SFX_PEAK_DB)
                else:
                    x = finalize_sfx(x, spec["dur"], spec["fade"])
                path = SFX_DIR / f"{name}.wav"
                write_wav(path, x, loop=spec["loop"])
                written.append(path)
                print(f"  sfx   {name:18s} {len(x) / SR:6.3f} s  ({time.time() - t0:4.1f} s)")
        if not args.no_music:
            for name, fn in MUSIC.items():
                if only and name not in only:
                    continue
                t0 = time.time()
                x = fn(verbose=args.verbose)
                if not np.all(np.isfinite(x)):
                    raise RuntimeError(f"{name}: non-finite samples")
                x = finalize_loop(x, MUSIC_PEAK_DB, limit=True)
                path = MUSIC_DIR / f"{name}.wav"
                write_wav(path, x, loop=True)
                written.append(path)
                print(f"  music {name:18s} {len(x) / SR:6.3f} s  ({time.time() - t0:4.1f} s)")
        print(f"generated {len(written)} files in {time.time() - t_all:.1f} s")
    else:
        written = sorted(SFX_DIR.glob("*.wav")) + sorted(MUSIC_DIR.glob("*.wav"))
        if only:
            written = [p for p in written if p.stem in only]
    problems = analyze(written, loops)
    print(f"\n{problems} file(s) with problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
