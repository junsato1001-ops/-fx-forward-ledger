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
