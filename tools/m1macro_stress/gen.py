"""Synthetic problems with the STRUCTURE of the real M1 estimation input (no real data):
3 pairs per origin, omega = 1/(n_e*n_p), expanding overlapping pools per pair (Z with exact zeros),
x_us on USDJPY only with 0.01-quantized 20-day changes, x_jp 0.001-quantized with long pinned (zero) spells,
x_pos weekly piecewise-constant ratio, smooth sigma."""
import numpy as np, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))


class G:  # minimal group (what indep.Prob.from_groups needs)
    def __init__(s, x, sigma, omega, a): s.x = np.asarray(x, float); s.sigma = sigma; s.omega = omega; s.a = a


def series_quant(rng, n, q, p_move, pin=None):
    lv = np.zeros(n + 20); 
    for i in range(1, len(lv)):
        mv = rng.random() < p_move
        if pin is not None and pin[0] <= i < pin[1]:
            mv = rng.random() < p_move * 0.05
        lv[i] = lv[i - 1] + (q * rng.choice([-2, -1, 1, 2]) if mv else 0.0)
    lv = np.round(lv / q) * q
    return np.array([float(round(lv[i + 20] - lv[i], 6)) for i in range(n)])


def problem(rng, n_origins, pool0=300, zero_frac=0.03, pin=True, horizon_step=1):
    n = n_origins
    pairs = ("CHFJPY", "INRJPY", "USDJPY")
    hist = {p: rng.standard_t(5, pool0 + n) for p in pairs}
    for p in pairs:
        hist[p][rng.random(len(hist[p])) < zero_frac] = 0.0
    sig = {p: 0.006 * np.exp(np.cumsum(rng.normal(0, 0.02, n))) for p in pairs}
    us = series_quant(rng, n, 0.01, 0.6)
    jp = series_quant(rng, n, 0.001, 0.5, pin=(int(n * 0.3), int(n * 0.8)) if pin else None)
    wk = np.repeat(rng.uniform(-0.4, 0.4, n // 5 + 1), 5)[:n]
    pos = np.array([float(np.float64(round(v * 1e5)) / 1e5) for v in wk])
    gs = []
    for i in range(0, n, horizon_step):
        for p in pairs:
            x = (us[i] if p == "USDJPY" else 0.0, jp[i], pos[i])
            z = hist[p][: pool0 + i]
            y = sig[p][i] * rng.standard_t(5)
            a = np.sort(np.float64(y) - sig[p][i] * z, kind="stable")
            gs.append((x, sig[p][i], a))
    ne = len(gs) // 3
    return [G(x, s, 1.0 / (ne * 3), a) for x, s, a in gs]
