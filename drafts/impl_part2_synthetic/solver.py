"""Prototype v1: float search + exact-rational certification and tie-break (synthetic only)."""
import numpy as np, math, itertools
from fractions import Fraction as Fr
from scipy.optimize import linprog
OPT=dict(primal_feasibility_tolerance=1e-10,dual_feasibility_tolerance=1e-10)
class Prob:
    def __init__(s,X,sig,pools,y,om):
        s.X=np.asarray(X,float); s.G,s.d=s.X.shape; s.sig=np.asarray(sig,float); s.om=np.asarray(om,float)
        s.a=[];s.S=[]
        for g in range(s.G):
            a=np.sort(np.asarray(y[g],float)-s.sig[g]*np.asarray(pools[g],float),kind='stable'); s.a.append(a)
            P=np.empty(len(a)+1);P[0]=0.0;tot=0.0;c=0.0
            for j,v in enumerate(a.tolist()):
                t=tot+v; c+= (tot-t)+v if abs(tot)>=abs(v) else (v-t)+tot; tot=t; P[j+1]=tot+c
            s.S.append(P)
    def mu(s,b): return [math.fsum(float(b[k])*s.X[g,k] for k in range(s.d)) for g in range(s.G)]
    def piece(s,b):
        m=s.mu(b); sl=np.empty(s.G);ic=np.empty(s.G)
        for g in range(s.G):
            a=s.a[g];N=len(a);k=int(np.searchsorted(a,m[g],side='right'))
            sl[g]=(2*k-N)/(N*s.sig[g]); ic[g]=(s.S[g][N]-2*s.S[g][k])/(N*s.sig[g])
        return np.array([math.fsum((s.om*sl*s.X[:,k]).tolist()) for k in range(s.d)]), math.fsum((s.om*ic).tolist())
    def phi(s,b):
        m=s.mu(b)
        return math.fsum(s.om[g]*math.fsum(np.abs(m[g]-s.a[g]).tolist())/(len(s.a[g])*s.sig[g]) for g in range(s.G))
# ---------- rows of master LP in (beta, theta):  row . z <= rhs
def rows_of(cuts,d,B):
    R=[];H=[]
    for sv,c in cuts: R.append(list(sv)+[-1.0]); H.append(-c)
    for k in range(d):
        e=[0.0]*(d+1);e[k]=1.0;R.append(e);H.append(B)
        e=[0.0]*(d+1);e[k]=-1.0;R.append(e);H.append(B)
    return R,H
def fsolve(A,b):
    n=len(A[0]);M=[[Fr(v) for v in r]+[Fr(bb)] for r,bb in zip(A,b)];m=len(M)
    for c in range(n):
        p=next((i for i in range(c,m) if M[i][c]!=0),None)
        if p is None: return None
        M[c],M[p]=M[p],M[c];pv=M[c][c];M[c]=[v/pv for v in M[c]]
        for i in range(m):
            if i!=c and M[i][c]!=0:
                f=M[i][c];M[i]=[a-f*bv for a,bv in zip(M[i],M[c])]
    return [M[i][n] for i in range(n)]
def exact_master(cuts,d,B,xf):
    """Exact optimum of min theta s.t. rows<=rhs, via candidate bases near float solution xf."""
    R,H=rows_of(cuts,d,B); n=d+1
    res=[sum(r[i]*xf[i] for i in range(n))-h for r,h in zip(R,H)]
    order=sorted(range(len(R)),key=lambda i:-res[i])  # most active first
    Rf=[[Fr(v) for v in r] for r in R]; Hf=[Fr(h) for h in H]
    for K in (8,12,16,24):
        cand=order[:K]
        for S in itertools.combinations(cand,n):
            x=fsolve([R[i] for i in S],[H[i] for i in S])
            if x is None: continue
            # dual: sum lam_i row_i = (0..0,-1)
            AT=[[R[i][j] for i in S] for j in range(n)]
            lam=fsolve(AT,[0.0]*d+[-1.0])
            if lam is None or any(l<0 for l in lam): continue
            if all(sum(Rf[i][j]*x[j] for j in range(n))<=Hf[i] for i in range(len(R))):
                return x  # exact optimal vertex (beta..., theta)
    return None
def stage1(P,B=10.0,eps=1e-13,lam=0.3,maxit=3000):
    d=P.d;cuts=[];best=(np.inf,None);pts=[np.zeros(d)];LBx=None
    for it in range(maxit):
        for b in pts:
            cuts.append(P.piece(b));J=P.phi(b)
            if J<best[0]: best=(J,np.array([float(v) for v in b]))
        R,H=rows_of(cuts,d,B)
        r=linprog(np.r_[np.zeros(d),1],A_ub=np.array(R),b_ub=np.array(H),bounds=[(None,None)]*(d+1),method='highs-ds',options=OPT)
        xm=exact_master(cuts,d,B,r.x)
        if xm is None: return dict(ok=False,why='EXACT_MASTER',it=it+1)
        LBx=xm[d]; gap=Fr(best[0])-LBx
        if gap< -Fr(eps): return dict(ok=False,why='CERT_INCONSISTENT',it=it+1)
        if abs(gap)<=Fr(eps): return dict(ok=True,bhat=best[1],UB=best[0],LB=LBx,xm=xm,it=it+1,cuts=cuts)
        lev=float(LBx)+lam*float(gap);A2=[];r2=[]
        for sv,c in cuts: A2.append(np.r_[sv,0]);r2.append(lev-c)
        for j in range(d):
            e=np.zeros(d+1);e[j]=1;e[d]=-1;A2.append(e.copy());r2.append(best[1][j])
            e=np.zeros(d+1);e[j]=-1;e[d]=-1;A2.append(e);r2.append(-best[1][j])
        q=linprog(np.r_[np.zeros(d),1],A_ub=np.array(A2),b_ub=np.array(r2),bounds=[(-B,B)]*d+[(0,None)],method='highs-ds',options=OPT)
        pts=[[float(v) for v in xm[:d]]]+([q.x[:d]] if q.status==0 else [])
    return dict(ok=False,why='MAXIT',it=maxit)
def exact_minnorm(A,b,x0,maxit=1000):
    """min ||x||^2 s.t. A x <= b, exact rational primal active set from feasible x0."""
    m=len(A);n=len(A[0]);A=[[Fr(v) for v in r] for r in A];b=[Fr(v) for v in b];x=list(x0);W=[]
    dot=lambda u,v:sum(p*q for p,q in zip(u,v))
    assert all(dot(A[i],x)<=b[i] for i in range(m))
    for it in range(maxit):
        # min ||x+p|| s.t. A_W p = 0 : target = projection of 0 onto {z: A_W z = A_W x}
        if W:
            Aw=[A[i] for i in W]; G=[[dot(r1,r2) for r2 in Aw] for r1 in Aw]
            # least-norm: z = Aw^T nu, Aw Aw^T nu = Aw x  (W kept linearly independent)
            nu=fsolve(G,[dot(r,x) for r in Aw])
            target=[sum(nu[k]*Aw[k][j] for k in range(len(W))) for j in range(n)]
        else: target=[Fr(0)]*n
        p=[t-xi for t,xi in zip(target,x)]
        if all(v==0 for v in p):
            if not W: return x
            # multipliers: x + Aw^T lam = 0 -> lam = -nu
            lamv=[-v for v in nu]; j=min(range(len(W)),key=lambda k:lamv[k])
            if lamv[j]>=0: return x
            W.pop(j); continue
        alpha=Fr(1);blk=None
        for i in range(m):
            if i in W: continue
            ap=dot(A[i],p)
            if ap<=0: continue
            a_=(b[i]-dot(A[i],x))/ap
            if a_<alpha: alpha=a_;blk=i
        x=[xi+alpha*pi for xi,pi in zip(x,p)]
        if blk is not None:
            # keep W independent
            Aw=[A[i] for i in W]+[A[blk]]
            G=[[dot(r1,r2) for r2 in Aw] for r1 in Aw]
            if fsolve(G,[Fr(0)]*len(Aw)) is not None: W.append(blk)
            else: W.append(blk); W.pop(0) if False else None
    raise RuntimeError('minnorm maxit')
def stage2(P,s1,B=10.0,eps=1e-13,maxit=100):
    cuts=list(s1['cuts']);d=P.d;LB=s1['LB'];x0=s1['xm'][:d]
    for it in range(maxit):
        A=[list(sv) for sv,_ in cuts]+[list(np.eye(d)[k]) for k in range(d)]+[list(-np.eye(d)[k]) for k in range(d)]
        bb=[LB-Fr(c) for _,c in cuts]+[Fr(B)]*(2*d)
        xs=exact_minnorm(A,bb,x0); b2=np.array([float(v) for v in xs]); J2=P.phi(b2)
        dJ=Fr(J2)-LB
        if dJ< -Fr(eps): return dict(ok=False,beta=b2,it=it+1,why='CERT_INCONSISTENT')
        if abs(dJ)<=Fr(eps): return dict(ok=True,beta=b2,J=J2,it=it+1,dJ=float(dJ))
        cuts.append(P.piece(b2))
        R,H=rows_of(cuts,d,B)
        r=linprog(np.r_[np.zeros(d),1],A_ub=np.array(R),b_ub=np.array(H),bounds=[(None,None)]*(d+1),method='highs-ds',options=OPT)
        xm=exact_master(cuts,d,B,r.x)
        if xm is None: return dict(ok=False,beta=b2,it=it+1,why='EXACT_MASTER')
        LB=xm[d]; x0=xm[:d]
    return dict(ok=False,beta=b2,it=maxit)
def solve(P,eps=1e-13):
    s1=stage1(P,eps=eps)
    if not s1['ok']: return s1,dict(ok=False,beta=np.full(P.d,np.nan),it=0)
    return s1,stage2(P,s1,eps=eps)
