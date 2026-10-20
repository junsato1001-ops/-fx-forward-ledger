"""Synthetic problem generators for gates G1-G3 (no real data)."""
import numpy as np

from m1macro import solver as S


def case_A(rng, G=300, N=200, c=(0.004, -0.006, 0.003)):
    """Phi symmetric about c (mirror groups) -> c is a minimizer."""
    c = np.array(c)
    X = rng.normal(0, .3, (G, 3)); X[1::3, 0] = 0; X[2::3, 0] = 0
    sig = rng.uniform(.004, .008, G); Z = rng.standard_t(5, (G, N)); y = sig * rng.standard_t(5, G)
    groups = []
    w = 1.0 / (2 * G)
    for g in range(G):
        groups.append(S.make_group(X[g], sig[g], w, y[g] + X[g] @ c, Z[g]))
    for g in range(G):
        groups.append(S.make_group(-X[g], sig[g], w, y[g] - X[g] @ c, Z[g]))
    return groups, c


def flat_groups(c, w):
    out = []
    for k in range(3):
        for sgn in (1.0, -1.0):
            x = np.zeros(3); x[k] = sgn
            out.append(S.make_group(x, 1.0, w, sgn * c[k], [-1.0, 1.0]))   # a = y - Z -> {sgn*c-1? }
    return out


def case_B():
    c = np.array([2.0, 0.5, -3.0])
    return flat_groups(c, 1 / 6), np.array([1.0, 0.0, -2.0])


def case_C(tilt):
    c = np.array([2.0, 0.5, -3.0]); target = np.array([3.0, 1.5, -4.0])
    gs = flat_groups(c, (1 - 3 * tilt) / 6)
    for k in range(3):
        x = np.zeros(3); x[k] = 1.0
        gs.append(S.make_group(x, 1.0, tilt, target[k], [0.0]))
    return gs, target


def case_random(rng, G, N, zero_col=False):
    X = rng.normal(0, .3, (G, 3)); X[1::3, 0] = 0; X[2::3, 0] = 0
    if zero_col:
        X[:, 0] = 0
    sig = rng.uniform(.004, .008, G)
    y = X @ np.array([.004, -.006, .003]) + sig * rng.standard_t(5, G)
    groups = [S.make_group(X[g], sig[g], 1.0 / G, y[g], rng.standard_t(5, N)) for g in range(G)]
    return groups


# ------------------------------------------------------------------ IMPL-FINDINGS-06: real-input STRUCTURE (synthetic)
def _quant_changes(rng, n, q, p_move, pin=None):
    lv = np.zeros(n + 20)
    for i in range(1, len(lv)):
        mv = rng.random() < p_move
        if pin is not None and pin[0] <= i < pin[1]:
            mv = rng.random() < p_move * 0.05
        lv[i] = lv[i - 1] + (q * rng.choice([-2, -1, 1, 2]) if mv else 0.0)
    lv = np.round(lv / q) * q
    return np.array([float(round(lv[i + 20] - lv[i], 6)) for i in range(n)])


def structured_case(kind, seed, kel_origins=(3000, 5000)):
    """Same problems as tools/m1macro_stress (seed -> identical draws): 3 pairs per origin, omega = 1/(n_e*n_p),
    expanding overlapping pools with exact zeros, x_us on USDJPY only (0.01-quantized 20-day changes), x_jp
    0.001-quantized with a pinned spell, x_pos weekly constant. Returns production solver groups."""
    rng = np.random.default_rng(seed)
    if kind == "epi":
        n = int(rng.integers(250, 1334)); pool0 = int(rng.integers(2500, 4500))
    else:
        n = int(rng.integers(*kel_origins)); pool0 = int(rng.integers(4000, 6500))
    zero_frac = float(rng.choice([0.0, 0.03])); pin = bool(rng.integers(0, 2))
    pairs = ("CHFJPY", "INRJPY", "USDJPY")
    hist = {p: rng.standard_t(5, pool0 + n) for p in pairs}
    for p in pairs:
        hist[p][rng.random(len(hist[p])) < zero_frac] = 0.0
    sig = {p: 0.006 * np.exp(np.cumsum(rng.normal(0, 0.02, n))) for p in pairs}
    us = _quant_changes(rng, n, 0.01, 0.6)
    jp = _quant_changes(rng, n, 0.001, 0.5, pin=(int(n * 0.3), int(n * 0.8)) if pin else None)
    wk = np.repeat(rng.uniform(-0.4, 0.4, n // 5 + 1), 5)[:n]
    pos = np.array([float(np.float64(round(v * 1e5)) / 1e5) for v in wk])
    raw = []
    for i in range(n):
        for p in pairs:
            x = (us[i] if p == "USDJPY" else 0.0, jp[i], pos[i])
            raw.append((x, sig[p][i], sig[p][i] * rng.standard_t(5), hist[p][: pool0 + i]))
    return [S.make_group(x, s, 1.0 / (n * 3), y, z) for x, s, y, z in raw]
