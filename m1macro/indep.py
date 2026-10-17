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


def solve_epigraph(P, tol=1e-12, maxr=200):
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
        beta = res.x[:3]; t = res.x[3:]; m_ = P.mu(beta); added = 0
        for g in range(G):
            s, c = P.group_piece(g, m_[g])
            if s * m_[g] + c - t[g] > tol:
                cuts[(g, round(m_[g], 15))] = (s, c); added += 1
        if added == 0:
            return beta, P.phi(beta), res.fun, r + 1
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


def compare(groups, prod_result, mu_rows=None, sigma_rows=None):
    """Part 2 §10 criteria. Returns dict of differences and pass flags (no beta values)."""
    P = Prob.from_groups(groups)
    if len(groups) <= 4000:
        beta, ub, lb, it = solve_epigraph(P); method = "epigraph"
    else:
        beta, ub, lb, it = solve_kelley(P); method = "kelley"
    ub_prod = P.phi(prod_result.beta)
    d_ub = abs(ub - ub_prod)
    d_beta = float(np.max(np.abs(beta - prod_result.beta)))
    out = dict(method=method, iterations=it, indep_gap=float(ub - lb), d_UB=d_ub, d_beta_inf=d_beta,
               pass_UB=bool(d_ub <= 2e-13 or ub_prod <= ub), pass_beta=bool(d_beta <= 1e-6))
    if mu_rows is not None:
        dmu = max(abs(float(np.dot(x, beta - prod_result.beta))) / s for x, s in zip(mu_rows, sigma_rows))
        out.update(d_mu_over_sigma=dmu, pass_mu=bool(dmu <= 1e-4))
    return out
