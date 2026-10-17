"""Estimator / solver for M1-MACRO-V1 (M1-MACRO-IMPL-PART2-V1).

Phi(beta) = sum_g omega_g * G_g(x_g . beta),  G_g(mu) = (1/(N_g sigma_g)) sum_j |mu - a_gj|,
a_gj = y_g - sigma_g * Z_gj.  beta* = argmin{ ||beta||_2 : beta in argmin Phi }.

Stage 1: level-stabilised cutting plane on aggregated exact pieces (float LP via HiGHS for search
only); the master optimum is certified in exact rational arithmetic (Part 2 §5).
Stage 2: exact rational minimum-norm point of F = {beta : L_r(beta) <= LB for all r, box}
(Part 2 §6). Two-sided checks with eps_tie (Part 2 v2 §5, §6).
No randomness. Each (t, h) is solved from scratch.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from fractions import Fraction as Fr
from typing import List, Optional, Sequence

import numpy as np

# ---- constants (Part 2 §7) ----
EPS_TIE = 1e-13
LAMBDA_LEV = 0.3
BOX_B = 10.0
CAND_SIZES = (8, 12, 16, 24)
STAGE1_MAX = 3000
STAGE2_MAX = 100
LP_TOL = 1e-10
D = 3  # beta = (US, JP, POS)


class SolverFailure(Exception):
    def __init__(self, subreason: str, detail: str = ""):
        super().__init__(f"{subreason}: {detail}")
        self.subreason = subreason
        self.detail = detail


# ---------------------------------------------------------------- LP backend (HiGHS via highspy)
def lp_min(c: Sequence[float], A: np.ndarray, b: np.ndarray, lo: Sequence[float], hi: Sequence[float]) -> np.ndarray:
    """min c.x s.t. A x <= b, lo <= x <= hi. Dual simplex, 1 thread, seed 0. Returns x or raises SOLVER_STATUS."""
    import highspy
    inf = highspy.kHighsInf
    h = highspy.Highs()
    for k, v in (("output_flag", False), ("threads", 1), ("random_seed", 0), ("presolve", "on"),
                 ("solver", "simplex"), ("simplex_strategy", 1),
                 ("primal_feasibility_tolerance", LP_TOL), ("dual_feasibility_tolerance", LP_TOL)):
        h.setOptionValue(k, v)
    n = len(c); m = A.shape[0]
    lp = highspy.HighsLp()
    lp.num_col_ = n; lp.num_row_ = m
    lp.col_cost_ = np.asarray(c, dtype=np.float64)
    lp.col_lower_ = np.array([(-inf if v is None else v) for v in lo], dtype=np.float64)
    lp.col_upper_ = np.array([(inf if v is None else v) for v in hi], dtype=np.float64)
    lp.row_lower_ = np.full(m, -inf, dtype=np.float64)
    lp.row_upper_ = np.asarray(b, dtype=np.float64)
    Ac = np.asarray(A, dtype=np.float64)
    starts, idx, val = [0], [], []
    for j in range(n):  # column-wise, deterministic order
        col = Ac[:, j]
        nz = np.nonzero(col)[0]
        idx.extend(nz.tolist()); val.extend(col[nz].tolist()); starts.append(len(idx))
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_ = np.array(starts, dtype=np.int32)
    lp.a_matrix_.index_ = np.array(idx, dtype=np.int32)
    lp.a_matrix_.value_ = np.array(val, dtype=np.float64)
    h.passModel(lp)
    h.run()
    st = h.getModelStatus()
    if st != highspy.HighsModelStatus.kOptimal:
        raise SolverFailure("SOLVER_STATUS", str(st))
    x = np.array(h.getSolution().col_value, dtype=np.float64)
    if not np.all(np.isfinite(x)):
        raise SolverFailure("NONFINITE", "lp solution")
    return x


# ---------------------------------------------------------------- problem data
@dataclass
class Group:
    x: np.ndarray        # (3,) float64
    sigma: float
    omega: float
    a: np.ndarray        # sorted breakpoints a_gj = y - sigma*Z (float64)
    S: np.ndarray        # compensated prefix sums, len N+1


def neumaier_prefix(a: np.ndarray) -> np.ndarray:
    """Left-to-right Neumaier-compensated prefix sums (Part 2 §3)."""
    out = np.empty(len(a) + 1, dtype=np.float64)
    out[0] = 0.0
    s = 0.0; c = 0.0
    for j, v in enumerate(a.tolist()):
        t = s + v
        if abs(s) >= abs(v):
            c += (s - t) + v
        else:
            c += (v - t) + s
        s = t
        out[j + 1] = s + c
    return out


def make_group(x, sigma: float, omega: float, y: float, z: Sequence[float]) -> Group:
    x = np.asarray(x, dtype=np.float64)
    zz = np.asarray(z, dtype=np.float64)
    if not (np.all(np.isfinite(x)) and math.isfinite(sigma) and math.isfinite(y) and np.all(np.isfinite(zz))):
        raise SolverFailure("NONFINITE", "group input")
    prod = sigma * zz                      # one multiplication, then one subtraction (no FMA)
    a = np.sort(np.float64(y) - prod, kind="stable")
    return Group(x=x, sigma=float(sigma), omega=float(omega), a=a, S=neumaier_prefix(a))


def _mu(g: Group, beta) -> float:
    return math.fsum(float(beta[k]) * float(g.x[k]) for k in range(D))


def piece(groups: List[Group], beta):
    """Aggregated exact piece at beta: returns (s (3,), c, Phi(beta))."""
    sl = []; ic = []; val = []
    for g in groups:
        mu = _mu(g, beta)
        N = len(g.a)
        k = int(np.searchsorted(g.a, mu, side="right"))
        den = N * g.sigma
        s_g = (2 * k - N) / den
        c_g = (g.S[N] - 2.0 * g.S[k]) / den
        sl.append(g.omega * s_g); ic.append(g.omega * c_g); val.append(g.omega * (s_g * mu + c_g))
    s = np.array([math.fsum(sl[i] * float(g.x[k]) for i, g in enumerate(groups)) for k in range(D)])
    c = math.fsum(ic)
    phi = math.fsum(val)
    return s, c, phi


# ---------------------------------------------------------------- exact linear algebra
def _fsolve(A, b):
    n = len(A[0]); M = [[Fr(v) for v in r] + [Fr(bb)] for r, bb in zip(A, b)]; m = len(M)
    for col in range(n):
        p = next((i for i in range(col, m) if M[i][col] != 0), None)
        if p is None:
            return None
        M[col], M[p] = M[p], M[col]
        pv = M[col][col]; M[col] = [v / pv for v in M[col]]
        for i in range(m):
            if i != col and M[i][col] != 0:
                f = M[i][col]; M[i] = [u - f * w for u, w in zip(M[i], M[col])]
    return [M[i][n] for i in range(n)]


def _rows(cuts, B):
    R, H = [], []
    for s, c in cuts:
        R.append([float(s[0]), float(s[1]), float(s[2]), -1.0]); H.append(-float(c))
    for k in range(D):
        e = [0.0] * (D + 1); e[k] = 1.0; R.append(e); H.append(B)
        e = [0.0] * (D + 1); e[k] = -1.0; R.append(e); H.append(B)
    return R, H


def exact_master(cuts, B, xf):
    """Exact optimal vertex (beta, theta) of min theta s.t. rows, from candidate bases near float xf."""
    R, H = _rows(cuts, B)
    n = D + 1
    res = [sum(r[i] * xf[i] for i in range(n)) - h for r, h in zip(R, H)]
    order = sorted(range(len(R)), key=lambda i: (-res[i], i))
    Rf = [[Fr(v) for v in r] for r in R]; Hf = [Fr(h) for h in H]
    tried = set()
    for K in CAND_SIZES:
        for S in itertools.combinations(order[:K], n):
            key = tuple(sorted(S))
            if key in tried:
                continue
            tried.add(key)
            x = _fsolve([R[i] for i in S], [H[i] for i in S])
            if x is None:
                continue
            lam = _fsolve([[R[i][j] for i in S] for j in range(n)], [0.0] * D + [-1.0])
            if lam is None or any(l < 0 for l in lam):
                continue
            if all(sum(Rf[i][j] * x[j] for j in range(n)) <= Hf[i] for i in range(len(R))):
                return x
    raise SolverFailure("EXACT_CERT", f"no certified basis among {len(tried)} candidates")


def exact_min_norm(A, b, x0, maxit=2000):
    """min ||x||^2 s.t. A x <= b (exact rationals), primal active set from feasible x0."""
    A = [[Fr(v) for v in r] for r in A]; b = [Fr(v) for v in b]; x = list(x0)
    m = len(A); n = len(A[0])
    dot = lambda u, v: sum(p * q for p, q in zip(u, v))
    if not all(dot(A[i], x) <= b[i] for i in range(m)):
        raise SolverFailure("TIEBREAK_NOT_CONVERGED", "infeasible start")
    W: List[int] = []
    for _ in range(maxit):
        if W:
            Aw = [A[i] for i in W]
            G = [[dot(r1, r2) for r2 in Aw] for r1 in Aw]
            nu = _fsolve(G, [dot(r, x) for r in Aw])
            if nu is None:  # dependent working set: drop the newest
                W.pop(); continue
            target = [sum(nu[k] * Aw[k][j] for k in range(len(W))) for j in range(n)]
        else:
            nu = []; target = [Fr(0)] * n
        p = [t - xi for t, xi in zip(target, x)]
        if all(v == 0 for v in p):
            if not W:
                return x
            lam = [-v for v in nu]
            j = min(range(len(W)), key=lambda k: (lam[k], k))
            if lam[j] >= 0:
                return x
            W.pop(j); continue
        alpha = Fr(1); blk = None
        for i in range(m):
            if i in W:
                continue
            ap = dot(A[i], p)
            if ap <= 0:
                continue
            a_ = (b[i] - dot(A[i], x)) / ap
            if a_ < alpha:
                alpha = a_; blk = i
        x = [xi + alpha * pi for xi, pi in zip(x, p)]
        if blk is not None:
            W.append(blk)
    raise SolverFailure("TIEBREAK_NOT_CONVERGED", "active set iteration cap")


# ---------------------------------------------------------------- stages
@dataclass
class Result:
    beta: np.ndarray
    ub: float
    lb: Fr
    stage1_iter: int
    stage2_iter: int
    ub_minus_lb: float
    phi2_minus_lb: float
    n_cuts: int = 0
    nonzero_cols: list = field(default_factory=list)


def _master_float(cuts, B):
    R, H = _rows(cuts, B)
    return lp_min([0.0] * D + [1.0], np.array(R), np.array(H), [None] * (D + 1), [None] * (D + 1))


def _level_point(cuts, B, lev, center):
    A = []; b = []
    for s, c in cuts:
        A.append([float(s[0]), float(s[1]), float(s[2]), 0.0]); b.append(lev - float(c))
    for j in range(D):
        e = [0.0] * (D + 1); e[j] = 1.0; e[D] = -1.0; A.append(e); b.append(float(center[j]))
        e = [0.0] * (D + 1); e[j] = -1.0; e[D] = -1.0; A.append(e); b.append(-float(center[j]))
    try:
        x = lp_min([0.0] * D + [1.0], np.array(A), np.array(b), [-B] * D + [0.0], [B] * D + [None])
        return x[:D]
    except SolverFailure:
        return None


def solve(groups: List[Group]) -> Result:
    if not groups:
        raise SolverFailure("SOLVER_STATUS", "empty E")
    B = BOX_B
    cuts = []
    best = (math.inf, None)
    pts = [np.zeros(D)]
    for it in range(1, STAGE1_MAX + 1):
        for p in pts:
            s, c, phi = piece(groups, p)
            if not math.isfinite(phi):
                raise SolverFailure("NONFINITE", "phi")
            cuts.append((s, c))
            if phi < best[0]:
                best = (phi, np.array(p, dtype=np.float64))
        xf = _master_float(cuts, B)
        xm = exact_master(cuts, B, xf)
        LB = xm[D]
        gap = Fr(best[0]) - LB
        if gap < -Fr(EPS_TIE):
            raise SolverFailure("CERT_INCONSISTENT", f"LB exceeds UB by {float(-gap):.3e}")
        if abs(gap) <= Fr(EPS_TIE):
            break
        lev = float(LB) + LAMBDA_LEV * float(gap)
        q = _level_point(cuts, B, lev, best[1])
        pts = [np.array([float(v) for v in xm[:D]])] + ([q] if q is not None else [])
    else:
        raise SolverFailure("GAP_NOT_REACHED", f"stage1 cap {STAGE1_MAX}")
    UB = best[0]; s1_it = it; ub_lb = float(Fr(UB) - LB)
    # ---- stage 2
    x0 = xm[:D]
    for it2 in range(1, STAGE2_MAX + 1):
        A = [[float(s[0]), float(s[1]), float(s[2])] for s, _ in cuts]
        b = [LB - Fr(float(c)) for _, c in cuts]
        for k in range(D):
            e = [0.0] * D; e[k] = 1.0; A.append(e); b.append(Fr(B))
            e = [0.0] * D; e[k] = -1.0; A.append(e); b.append(Fr(B))
        xs = exact_min_norm(A, b, x0)
        b2 = np.array([float(v) for v in xs], dtype=np.float64)
        s, c, phi2 = piece(groups, b2)
        d2 = Fr(phi2) - LB
        if d2 < -Fr(EPS_TIE):
            raise SolverFailure("CERT_INCONSISTENT", f"Phi(beta2) below LB by {float(-d2):.3e}")
        if abs(d2) <= Fr(EPS_TIE):
            nz = [k for k in range(D) if any(g.x[k] != 0.0 for g in groups)]
            for k in nz:
                if abs(xs[k]) >= Fr(B):
                    raise SolverFailure("BOX_ACTIVE", f"coordinate {k}")
            return Result(beta=b2, ub=UB, lb=LB, stage1_iter=s1_it, stage2_iter=it2, ub_minus_lb=ub_lb,
                          phi2_minus_lb=float(d2), n_cuts=len(cuts), nonzero_cols=nz)
        cuts.append((s, c))
        xf = _master_float(cuts, B)
        xm = exact_master(cuts, B, xf)
        LB = xm[D]; x0 = xm[:D]
    raise SolverFailure("TIEBREAK_NOT_CONVERGED", f"stage2 cap {STAGE2_MAX}")
