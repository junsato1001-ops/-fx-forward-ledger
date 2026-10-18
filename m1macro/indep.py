"""Independent implementation of beta* for gate G3/G6 (Impl Part 2 §10). Written separately from solver.py.

Differences from production: Phi is evaluated directly as sum_j |mu - a_gj| (math.fsum), not via prefix-sum
pieces; LPs use scipy's linprog interface; for small E the lower bound comes from a per-group epigraph LP
with lazily added group pieces; for large E an aggregated-cut Kelley method written here.
Tie-break: argmin is checked for a unique vertex; the result is compared with the production beta*.
"""
import math

import numpy as np
from scipy.optimize import linprog

OPT = dict(primal_feasibility_tolerance=1e-10, dual_feasibility_tolerance=1e-10)


class Prob:
    def __init__(self, X, sig, om, a_list):
        self.X = np.asarray(X, float); self.sig = np.asarray(sig, float); self.om = np.asarray(om, float)
        self.a = [np.sort(np.asarray(a, float)) for a in a_list]
        self.N = np.array([len(a) for a in self.a])

    @classmethod
    def from_groups(cls, groups):
        return cls([g.x for g in groups], [g.sigma for g in groups], [g.omega for g in groups], [g.a for g in groups])

    def mu(self, b):
        return [math.fsum(float(b[k]) * self.X[g, k] for k in range(3)) for g in range(len(self.a))]

    def phi(self, b):
        m = self.mu(b)
        return math.fsum(self.om[g] * math.fsum(np.abs(m[g] - self.a[g]).tolist()) / (self.N[g] * self.sig[g])
                         for g in range(len(self.a)))

    def group_piece(self, g, mu):
        a = self.a[g]; N = self.N[g]; k = int(np.searchsorted(a, mu, side="right"))
        lo = math.fsum(a[:k].tolist()); hi = math.fsum(a[k:].tolist())
        return (2 * k - N) / (N * self.sig[g]), (hi - lo) / (N * self.sig[g])


def solve_epigraph(P, tol=1e-13, maxr=200, return_state=False):
    """Per-group epigraph LP with lazily added group pieces (search), then a lower bound.

    Clean convergence (no group piece above its epigraph variable by more than tol): LB = the LP value, as before.
    STALL (IMPL-FINDINGS-06): a round re-adds only cuts that are already in the model with the same key and value,
    so the cut set, the next LP and (deterministic solver) its solution are identical: the loop would repeat until
    maxr. The violation is the LP's own feasibility tolerance (1e-10) against the separation tolerance (1e-13). The
    cut rule and the LP path before this point are exactly the original ones.
    The search then stops and the lower bound is certified exactly by the aggregated-cut master (solve_kelley_fast,
    own Cramer-rule certificate, criterion UB - exact LB <= tol), started from the epigraph point. Returns
    (beta, UB, LB, rounds, termination) with termination in EPIGRAPH_CONVERGED / EPIGRAPH_STALLED_EXACT_CERT."""
    G = len(P.a); cuts = {}
    for g in range(G):
        for mu0 in (P.a[g][0] - 1.0, P.a[g][-1] + 1.0):
            cuts[(g, round(mu0, 15))] = P.group_piece(g, mu0)
    for r in range(maxr):
        keys = sorted(cuts); m = len(keys)
        A = np.zeros((m, 3 + G)); b = np.zeros(m)
        for i, (g, _) in enumerate(keys):
            s, c = cuts[(g, _)]
            A[i, :3] = s * P.X[g]; A[i, 3 + g] = -1.0; b[i] = -c
        res = linprog(np.r_[np.zeros(3), P.om], A_ub=A, b_ub=b, bounds=_bounds(P) + [(None, None)] * G,
                      method="highs-ds", options=OPT)
        if res.status != 0:
            raise RuntimeError(res.message)
        beta = res.x[:3]; t = res.x[3:]; m_ = P.mu(beta); added = 0; changed = False
        for g in range(G):
            s, c = P.group_piece(g, m_[g])
            if s * m_[g] + c - t[g] > tol:                         # cut rule unchanged (same LP path as before)
                key = (g, round(m_[g], 15))
                if cuts.get(key) != (s, c):
                    changed = True
                cuts[key] = (s, c); added += 1
        if added == 0:
            out = (beta, P.phi(beta), res.fun, r + 1, "EPIGRAPH_CONVERGED")
            return out + (None,) if return_state else out
        if not changed:          # fixed point: the cut set (hence the next LP and its solution) is identical -> certify
            kb, kub, klb, kit, kterm, kst = solve_kelley_fast(P, start=[np.array(beta, float)], return_termination=True,
                                                               return_state=True)
            if kterm != "KELLEY_CERTIFIED":
                raise RuntimeError("epigraph stalled; exact certification failed: " + kterm)
            pb = P.phi(np.array(beta, float))
            bb, bub = (np.array(beta, float), pb) if pb <= kub else (kb, kub)
            out = (bb, bub, klb, r + 1 + kit, "EPIGRAPH_STALLED_EXACT_CERT")
            return out + (kst,) if return_state else out
    raise RuntimeError("epigraph not converged")


def solve_kelley(P, tol=1e-12, maxit=4000):
    cuts = []; best = (math.inf, None); pts = [np.zeros(3)]
    for it in range(maxit):
        for p in pts:
            m = P.mu(p); sl = np.zeros(3); c0 = []
            for g in range(len(P.a)):
                s, c = P.group_piece(g, m[g]); sl += P.om[g] * s * P.X[g]; c0.append(P.om[g] * c)
            cuts.append((sl, math.fsum(c0)))
            ph = P.phi(p)
            if ph < best[0]:
                best = (ph, np.array(p))
        A = np.array([np.r_[s, -1.0] for s, _ in cuts]); b = np.array([-c for _, c in cuts])
        res = linprog(np.r_[np.zeros(3), 1.0], A_ub=A, b_ub=b, bounds=_bounds(P) + [(None, None)],
                      method="highs-ds", options=OPT)
        lb = res.fun
        if best[0] - lb <= tol:
            return best[1], best[0], lb, it + 1
        pts = [res.x[:3]]
    raise RuntimeError("kelley not converged")


def _bounds(P):
    """Minimum-norm handling of structural null directions: a coordinate whose column is zero for every group
    does not enter Phi, so its min-norm value is exactly 0 (fixed by bounds)."""
    return [(0.0, 0.0) if not np.any(P.X[:, k] != 0.0) else (-10.0, 10.0) for k in range(3)]


class FastProb:
    """Large-E path. Prefix sums in extended precision (np.longdouble cumulative sums, flattened with offsets),
    a numerical path different from production (binary64 Neumaier per group). Vectorised over groups."""

    def __init__(self, P):
        self.P = P
        Ls = [np.concatenate([[np.longdouble(0)], np.cumsum(a.astype(np.longdouble))]) for a in P.a]
        self.off = np.cumsum([0] + [len(x) for x in Ls[:-1]])
        self.flat = np.concatenate(Ls)
        self.N = P.N.astype(np.int64)
        self.den = self.N.astype(np.longdouble) * P.sig.astype(np.longdouble)
        self.w = P.om.astype(np.longdouble)
        self.XL = P.X.astype(np.longdouble)

    def eval(self, b):
        P = self.P
        m = P.X[:, 0] * b[0] + P.X[:, 1] * b[1] + P.X[:, 2] * b[2]
        k = np.fromiter((np.searchsorted(P.a[g], m[g], side="right") for g in range(len(P.a))), dtype=np.int64, count=len(P.a))
        sl = (2 * k - self.N).astype(np.longdouble) / self.den
        ic = (self.flat[self.off + self.N] - 2 * self.flat[self.off + k]) / self.den
        s = (self.w * sl)[:, None] * self.XL
        return s.sum(axis=0).astype(float), float((self.w * ic).sum()), float((self.w * (sl * m.astype(np.longdouble) + ic)).sum())


def _vertex_polish(F, cuts, x, bnd, K=8):
    """Recompute the master vertex exactly from the K most active rows (own Fraction elimination)
    and evaluate Phi there; independent of production's certification code."""
    from fractions import Fraction
    import itertools
    rows = [(list(s) + [-1.0], -c) for s, c in cuts]
    for k in range(3):
        lo, hi = bnd[k]
        e = [0.0] * 4; e[k] = 1.0; rows.append((e, hi))
        e = [0.0] * 4; e[k] = -1.0; rows.append((e, -lo))
    act = sorted(range(len(rows)), key=lambda i: -(np.dot(rows[i][0], x) - rows[i][1]))[:K]
    best = (math.inf, None)
    for comb in itertools.combinations(act, 4):
        M = [[Fraction(v) for v in rows[i][0]] + [Fraction(rows[i][1])] for i in comb]
        ok = True
        for c in range(4):
            p = next((r for r in range(c, 4) if M[r][c] != 0), None)
            if p is None:
                ok = False; break
            M[c], M[p] = M[p], M[c]; pv = M[c][c]; M[c] = [v / pv for v in M[c]]
            for r in range(4):
                if r != c and M[r][c] != 0:
                    f = M[r][c]; M[r] = [u - f * w for u, w in zip(M[r], M[c])]
        if not ok:
            continue
        b = np.array([float(M[i][4]) for i in range(3)])
        if any(b[k] < bnd[k][0] or b[k] > bnd[k][1] for k in range(3)):
            continue
        v = F.eval(b)[2]
        if v < best[0]:
            best = (v, b)
    return best[1], best[0]


def _det_solve(M, r):
    """Cramer's rule on a 4x4 Fraction system (own code, different from production's elimination)."""
    from fractions import Fraction

    def det(A):
        n = len(A)
        if n == 1:
            return A[0][0]
        return sum(((-1) ** j) * A[0][j] * det([row[:j] + row[j + 1:] for row in A[1:]]) for j in range(n) if A[0][j] != 0)
    d = det(M)
    if d == 0:
        return None
    out = []
    for j in range(len(M)):
        Mj = [row[:j] + [r[i]] + row[j + 1:] for i, row in enumerate(M)]
        out.append(Fraction(det(Mj)) / d)
    return out


def _exact_rows(cuts, bnd):
    from fractions import Fraction
    rows = [([Fraction(float(v)) for v in s] + [Fraction(-1)], Fraction(-float(c))) for s, c in cuts]
    for k in range(3):
        lo, hi = bnd[k]
        e = [Fraction(0)] * 4; e[k] = Fraction(1); rows.append((e, Fraction(hi)))
        e = [Fraction(0)] * 4; e[k] = Fraction(-1); rows.append((e, Fraction(-lo)))
    return rows


def _basis_check(rows, comb):
    """(vertex, dual-feasible, primal-feasible) of a 4-row basis, exactly."""
    from fractions import Fraction
    M = [rows[i][0] for i in comb]
    v = _det_solve(M, [rows[i][1] for i in comb])
    if v is None:
        return None, False, False
    MT = [[M[i][j] for i in range(4)] for j in range(4)]
    lam = _det_solve(MT, [Fraction(0), Fraction(0), Fraction(0), Fraction(-1)])
    if lam is None or min(lam) < 0:
        return v, False, False
    return v, True, all(sum(a * b for a, b in zip(r, v)) <= h for r, h in rows)


def exact_lb(cuts, bnd, x, prefer=()):
    """Exact optimal value of the master LP (min theta s.t. s.beta + c <= theta, box) certified by a primal-feasible
    vertex with nonnegative exact dual multipliers. Returns the exact vertex (beta_1..3, theta) or None.

    Stage 1 (original, unchanged): 4-row bases among the 6 / 10 / 14 rows that are most active at the float point.
    Stage 2 (IMPL-FINDINGS-06, only if stage 1 finds nothing): near a degenerate optimum the float LP's basis can be
    exactly infeasible by 1e-13..1e-12 (far below its 1e-10 feasibility tolerance), so no basis among the top rows is
    exactly optimal. Starting from the LP-binding rows (prefer) and then from the dual-feasible bases met in stage 1,
    an exact dual simplex (_exact_dual_simplex) walks to the exact optimum. The certificate (exact primal feasibility
    of every row, exact duals >= 0) is the same in both stages; stage 2 only finds the basis.
    Row order: cuts 0..m-1, then for k = 0..2 the upper box row m+2k and the lower box row m+2k+1."""
    import itertools
    rows = _exact_rows(cuts, bnd)
    xf = [float(v) for v in x]
    act = sorted(range(len(rows)), key=lambda i: (-(sum(float(a) * b for a, b in zip(rows[i][0], xf)) - float(rows[i][1])), i))
    seen = set(); dual_ok = []
    for K in (6, 10, 14):                                   # stage 1: original search
        for comb in itertools.combinations(act[:K], 4):
            if comb in seen:
                continue
            seen.add(comb)
            v, dfeas, pfeas = _basis_check(rows, comb)
            if pfeas:
                return v
            if dfeas and len(dual_ok) < MAX_WALKS:
                dual_ok.append(list(comb))
    pre = []                                                # stage 2: exact walk to the optimum
    for i in prefer:
        if 0 <= i < len(rows) and i not in pre:
            pre.append(i)
    starts = ([pre] if len(pre) == 4 and _basis_check(rows, pre)[1] else []) + dual_ok
    for b0 in starts[:MAX_WALKS]:
        w = _exact_dual_simplex(rows, list(b0))
        if w is not None:
            return w
    return None


MAX_WALKS = 3            # dual-simplex walks tried per certification attempt (search effort only; not a criterion)
MAX_PIVOTS = 400


def _exact_dual_simplex(rows, basis):
    """Exact dual simplex on the 4-variable master (min theta s.t. rows), started from a dual-feasible basis
    (IMPL-FINDINGS-06). Fractions only, own Cramer-rule solves, Bland's rule (smallest index enters and, on ties,
    leaves), so it cannot cycle. Returns the exact optimal vertex (primal feasible, exact duals >= 0) or None."""
    from fractions import Fraction
    c_neg = [Fraction(0), Fraction(0), Fraction(0), Fraction(-1)]
    for _ in range(MAX_PIVOTS):
        M = [rows[i][0] for i in basis]
        v = _det_solve(M, [rows[i][1] for i in basis])
        MT = [[M[i][j] for i in range(4)] for j in range(4)]
        lam = _det_solve(MT, c_neg)
        if v is None or lam is None or min(lam) < 0:
            return None
        enter = next((i for i, (r, h) in enumerate(rows) if sum(a * b for a, b in zip(r, v)) > h), None)
        if enter is None:
            return v                                  # primal feasible + dual feasible: exact optimum
        d = _det_solve(MT, rows[enter][0])            # A_B^T d = a_enter
        if d is None:
            return None
        cand = [(lam[k] / d[k], basis[k], k) for k in range(4) if d[k] > 0]
        if not cand:
            return None                               # cannot happen for a bounded master; fail closed
        _, _, k = min(cand)
        basis = basis[:k] + [enter] + basis[k + 1:]
    return None


def _binding_rows(res, m, bnd):
    """Rows the float master LP reports as binding (nonzero dual multipliers), in exact_lb's row order."""
    out = []
    try:
        out += [i for i, v in enumerate(res.ineqlin.marginals) if v != 0.0]
        for k in range(3):
            if bnd[k][0] == bnd[k][1]:
                out += [m + 2 * k, m + 2 * k + 1]
                continue
            if res.upper.marginals[k] != 0.0:
                out.append(m + 2 * k)
            if res.lower.marginals[k] != 0.0:
                out.append(m + 2 * k + 1)
    except (AttributeError, IndexError, TypeError):
        return []
    return out


def solve_kelley_fast(P, tol=1e-13, maxit=600, lam=0.5, start=None, return_termination=False, return_state=False):
    """Aggregated-cut cutting plane with a different stabilisation (level 0.5) and scipy's interface. The float LP is
    used for search; once its gap is within 1e-10 the master is certified exactly every iteration (own Cramer-rule
    code, exact dual check), the exact vertex becomes the next point, and the run stops when UB - exact LB <= tol
    (Part 2 §10 criterion 1 for this implementation)."""
    F = FastProb(P); cuts = []; best = (math.inf, None); bnd = _bounds(P)
    pts = [np.zeros(3)] + [np.array(p, float) for p in (start or [])]
    def ret(*v, term, state=None):
        out = v + ((term,) if return_termination else ())
        return out + (state,) if return_state else out
    lb = -math.inf
    for it in range(maxit):
        for p in pts:
            s, c, v = F.eval(p); cuts.append((s, c))
            if v < best[0]:
                best = (v, np.array(p))
        A = np.array([np.r_[s, -1.0] for s, _ in cuts]); b = np.array([-c for _, c in cuts])
        res = linprog(np.r_[np.zeros(3), 1.0], A_ub=A, b_ub=b, bounds=bnd + [(None, None)], method="highs-ds", options=OPT)
        lb = res.fun; gap = best[0] - lb
        xm = res.x[:3]
        if gap <= 1e-10:                                   # near the end: certify the master exactly every iteration
            v = exact_lb(cuts, bnd, res.x, _binding_rows(res, len(cuts), bnd))
            if v is not None:
                lb = float(v[3]); xm = np.array([float(t) for t in v[:3]])
                if best[0] - lb <= tol:
                    vb, vv = _vertex_polish(F, cuts, res.x, bnd)
                    if vb is not None and vv < best[0]:
                        best = (vv, vb)
                    return ret(best[1], best[0], lb, it + 1, term="KELLEY_CERTIFIED",
                               state={"F": F, "cuts": cuts, "bnd": bnd, "v": v})
        lev = lb + lam * (best[0] - lb)
        A2 = np.array([np.r_[s, 0.0] for s, _ in cuts] + [np.r_[np.eye(3)[j], -1.0] for j in range(3)] + [np.r_[-np.eye(3)[j], -1.0] for j in range(3)])
        b2 = np.r_[[lev - c for _, c in cuts], best[1], -best[1]]
        r2 = linprog(np.r_[np.zeros(3), 1.0], A_ub=A2, b_ub=b2, bounds=bnd + [(0, None)], method="highs-ds", options=OPT)
        pts = [xm] + ([r2.x[:3]] if r2.status == 0 else [])
    return ret(best[1], best[0], lb, maxit, term="KELLEY_MAXIT")


def _solve_small(M, r):
    """Exact solve of a k x k (k <= 3) Fraction system by Gaussian elimination (own code). None if singular."""
    k = len(M)
    A = [list(M[i]) + [r[i]] for i in range(k)]
    for c in range(k):
        p = next((i for i in range(c, k) if A[i][c] != 0), None)
        if p is None:
            return None
        A[c], A[p] = A[p], A[c]
        for i in range(k):
            if i != c and A[i][c] != 0:
                f = A[i][c] / A[c][c]
                A[i] = [a - f * b for a, b in zip(A[i], A[c])]
    return [A[i][k] / A[i][i] for i in range(k)]


def _exact_min_norm(G, h, x0, max_iter=5000):
    """argmin ||x||^2 s.t. G x <= h (3 variables), exact primal active-set method in Fractions from the feasible
    point x0 (IMPL-FINDINGS-06; Impl Part 2 §6 step 2, written independently of production). Bland-type choices
    (smallest row index) for blocking and for dropping. Returns the exact minimiser or None."""
    from fractions import Fraction
    dot = lambda a, b: sum(p * q for p, q in zip(a, b))
    x = list(x0)
    if any(dot(g, x) > hh for g, hh in zip(G, h)):
        return None
    W = []
    for i, (g, hh) in enumerate(zip(G, h)):                  # active, linearly independent rows at x0
        if len(W) < 3 and dot(g, x) == hh:
            cand = W + [i]
            gram = [[dot(G[a], G[b]) for b in cand] for a in cand]
            if _det_solve(gram, [Fraction(0)] * len(cand)) is not None:     # nonsingular Gram matrix
                W.append(i)
    for _ in range(max_iter):
        if W:
            GW = [G[i] for i in W]
            y = _solve_small([[dot(a, b) for b in GW] for a in GW], [h[i] for i in W])
            if y is None:
                return None
            xs = [sum(y[j] * GW[j][k] for j in range(len(W))) for k in range(3)]
        else:
            xs = [Fraction(0)] * 3
        p = [a - b for a, b in zip(xs, x)]
        if all(v == 0 for v in p):
            if not W:
                return x
            GW = [G[i] for i in W]
            lam = _solve_small([[dot(a, b) for b in GW] for a in GW], [-dot(g, x) for g in GW])
            if lam is None:
                return None
            neg = [W[j] for j in range(len(W)) if lam[j] < 0]
            if not neg:
                return x
            W.remove(min(neg))
            continue
        alpha, blk = Fraction(1), None
        for i, (g, hh) in enumerate(zip(G, h)):
            if i in W:
                continue
            gp = dot(g, p)
            if gp > 0:
                a = (hh - dot(g, x)) / gp
                if a < alpha or (a == alpha and blk is not None and i < blk):
                    alpha, blk = a, i
        x = [a + alpha * b for a, b in zip(x, p)]
        if blk is not None:
            W.append(blk)
    return None


REFINE_TOL = 1e-14       # internal refinement target of the independent §6 stage (IMPL-FINDINGS-06); the acceptance
                         # criterion stays eps_tie = 1e-13 (Part 2 §7, §10) and CERT_INCONSISTENT stays at -eps_tie


def min_norm_stage(P, st, tol=1e-13, max_rounds=200, refine=REFINE_TOL):
    """Impl Part 2 §6 for the independent implementation (IMPL-FINDINGS-06): over F = {beta : L_r(beta) <= LB for
    every aggregated cut r, box}, LB the EXACT model minimum, take the exact minimum-norm point beta2 (Phi by direct
    fsum). Phi(beta2) < LB - tol -> CERT_INCONSISTENT. Phi(beta2) > LB + refine -> add the aggregated cut at beta2,
    certify the new model minimum exactly, repeat. Stops when -tol <= Phi(beta2) - LB <= refine.
    Why refine < tol: stopping as soon as Phi(beta2) - LB <= tol leaves beta2 anywhere in the eps_tie band of a nearly
    flat minimum; on synthetic data that was 1e-6..2.2e-6 away from the min-norm point, while continuing to 1e-14
    converged (1e-14 and 3e-15 gave the same point) and production's beta* lay within 9.4e-7 of it. A reference
    implementation should approximate the defined point as closely as it can; the criterion is unchanged.
    If refine is not reached within max_rounds, the last beta2 is returned only if it satisfies the criterion
    (|Phi - LB| <= tol). Returns (beta2, Phi, LB, rounds, refined)."""
    from fractions import Fraction
    F, cuts, bnd, v = st["F"], list(st["cuts"]), st["bnd"], st["v"]
    last = None
    for rnd in range(max_rounds):
        LBq = v[3]
        G = [[Fraction(float(t)) for t in s] for s, _ in cuts]; h = [LBq - Fraction(float(c)) for _, c in cuts]
        for k in range(3):
            lo, hi = bnd[k]
            e = [Fraction(0)] * 3; e[k] = Fraction(1); G.append(e); h.append(Fraction(hi))
            e = [Fraction(0)] * 3; e[k] = Fraction(-1); G.append(e); h.append(Fraction(-lo))
        x = _exact_min_norm(G, h, list(v[:3]))
        if x is None:
            raise RuntimeError("MINNORM_QP_FAILED")
        b2 = np.array([float(t) for t in x]); phi2 = P.phi(b2); lbf = float(LBq)
        if phi2 < lbf - tol:
            raise RuntimeError("CERT_INCONSISTENT")
        if phi2 - lbf <= refine:
            return b2, phi2, lbf, rnd + 1, True
        last = (b2, phi2, lbf, rnd + 1, False) if phi2 - lbf <= tol else None
        s, c, _ = F.eval(b2); cuts.append((s, c))
        A = np.array([np.r_[ss, -1.0] for ss, _ in cuts]); b = np.array([-cc for _, cc in cuts])
        res = linprog(np.r_[np.zeros(3), 1.0], A_ub=A, b_ub=b, bounds=bnd + [(None, None)], method="highs-ds", options=OPT)
        v = exact_lb(cuts, bnd, res.x, _binding_rows(res, len(cuts), bnd)) if res.status == 0 else None
        if v is None:
            if last is not None:
                return last
            raise RuntimeError("MINNORM_RECERT_FAILED")
    if last is not None:
        return last
    raise RuntimeError("MINNORM_NOT_CONVERGED")


def compare(groups, prod_result, mu_rows=None, sigma_rows=None):
    """Part 2 §10 criteria. Returns dict of differences and pass flags (no beta values)."""
    P = Prob.from_groups(groups)
    if len(groups) <= 4000:
        beta, ub, lb, it, term, st = solve_epigraph(P, return_state=True); method = "epigraph"
    else:
        beta, ub, lb, it, term, st = solve_kelley_fast(P, return_termination=True, return_state=True)
        method = "kelley_fast_longdouble"
    if method == "epigraph":
        # §6 needs the exact model minimum of an aggregated-cut model that bounds the region around the optimum: a
        # Kelley model built from scratch (a warm start at an exact minimiser can certify with one flat cut, leaving
        # F almost the whole box). The epigraph result stays the search result recorded in `iterations`.
        _, _, _, kit, kterm, st = solve_kelley_fast(P, return_termination=True, return_state=True)
        it += kit
        if kterm != "KELLEY_CERTIFIED":
            st = None; term += "+CERT_" + kterm
    if st is not None:                                # Impl Part 2 §6: exact minimum-norm tie-break
        beta, _, lb, rounds, refined = min_norm_stage(P, st)
        it += rounds; term += "+MINNORM_OK" if refined else "+MINNORM_OK_UNREFINED"
    else:
        term += "+NO_MINNORM"
    ub = P.phi(beta)                      # both UBs by the same direct |mu - a| evaluation
    ub_prod = P.phi(prod_result.beta)
    d_ub = abs(ub - ub_prod)
    d_beta = float(np.max(np.abs(beta - prod_result.beta)))
    # pass_gap = §10 criterion 1 for this implementation: §5 (search certified, |UB - LB| <= tol) and §6 (min-norm
    # point accepted with |Phi(beta2) - LB| <= tol); without the §6 stage it cannot pass.
    out = dict(method=method, iterations=it, termination=term, indep_gap=float(ub - lb), d_UB=d_ub, d_beta_inf=d_beta,
               pass_UB=bool(d_ub <= 2e-13), pass_beta=bool(d_beta <= 1e-6),
               pass_gap=bool(abs(float(ub - lb)) <= 1e-13 and "+MINNORM_OK" in term))          # Part 2 §10 criterion 1 for this implementation
    if mu_rows is not None:
        dmu = max(abs(float(np.dot(x, beta - prod_result.beta))) / s for x, s in zip(mu_rows, sigma_rows))
        out.update(d_mu_over_sigma=dmu, pass_mu=bool(dmu <= 1e-4))
    return out
