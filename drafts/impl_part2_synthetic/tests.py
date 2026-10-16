import numpy as np,time,sys
from solver import *
rng=np.random.default_rng(7)
def show(name,s1,s2,expect=None):
    e='' if expect is None else ' err=%.1e'%np.abs(s2['beta']-expect).max()
    g=float(s1['UB']-s1['LB']) if s1['ok'] else float('nan')
    print(f"{name}: s1 ok={s1['ok']} {s1.get('why','')} it={s1['it']} gap={g:.1e} | s2 dJ={s2.get('dJ',float('nan')):.1e} s2 ok={s2['ok']} it={s2['it']} beta={np.round(s2['beta'],9)}{e}",flush=True)
# A: known exact minimizer via symmetric construction, shifted by c
def caseA(G=300,N=200,c=np.array([.004,-.006,.003])):
    X=rng.normal(0,.3,(G,3));X[1::3,0]=0;X[2::3,0]=0;sig=rng.uniform(.004,.008,G);Z=rng.standard_t(5,(G,N));y=sig*rng.standard_t(5,G)
    X2=np.vstack([X,-X]);sig2=np.r_[sig,sig];Z2=np.vstack([Z,Z]);y2=np.r_[y+X@c,y-X@c]  # Phi symmetric about c
    return Prob(X2,sig2,list(Z2),y2,np.full(2*G,1/(2*G))),c
P,c=caseA(); s1,s2=solve(P); show('A symmetric about c',s1,s2,c); print('   Phi(b*)-Phi(c)=%.1e  |b*|-|c|=%.1e'%(P.phi(s2['beta'])-P.phi(c),np.linalg.norm(s2['beta'])-np.linalg.norm(c)))
# B: flat minimum: argmin = c + [-1,1]^3 box -> min-norm known
def flat_groups(c,w):
    X=[];sig=[];pools=[];y=[];om=[]
    for k in range(3):
        for sgn in (1,-1):
            x=np.zeros(3);x[k]=sgn; X.append(x);sig.append(1.0);pools.append(np.array([1.0,-1.0]));y.append(sgn*c[k]);om.append(w)
    return X,sig,pools,y,om
c=np.array([2.0,0.5,-3.0]); X,sig,pools,y,om=flat_groups(c,1/6)
show('B flat minimum',*solve(Prob(X,sig,pools,y,om)),np.array([1.0,0.0,-2.0]))
# C: nearly flat but unique: flat box + tilt pulling to (3,1.5,-4) with total loss advantage 5e-9 over min-norm corner
def caseC(tilt):
    X,sig,pools,y,om=flat_groups(c,(1-3*tilt)/6)
    target=np.array([3.0,1.5,-4.0])
    for k in range(3):
        x=np.zeros(3);x[k]=1;X.append(x);sig.append(1.0);pools.append(np.array([0.0]));y.append(target[k]);om.append(tilt)
    return Prob(X,sig,pools,y,om),target
for tilt in (2.5e-9,1e-10,1e-11,1e-12,1e-14):
    P,t=caseC(tilt); s1,s2=solve(P)
    show(f'C nearly flat unique (tilt={tilt:.0e}, min-norm corner worse by {tilt*(2+1.5+2):.1e})',s1,s2,t)
# D: random realistic, larger
for G,N in [(600,800),(3000,2000)][:int(__import__('sys').argv[1]) if len(__import__('sys').argv)>1 else 2]:
    X=rng.normal(0,.3,(G,3));X[1::3,0]=0;X[2::3,0]=0;sig=rng.uniform(.004,.008,G)
    y=X@np.array([.004,-.006,.003])+sig*rng.standard_t(5,G);Z=rng.standard_t(5,(G,N))
    t0=time.time();P=Prob(X,sig,list(Z),y,np.full(G,1/G));s1,s2=solve(P)
    show(f'D random G={G} N={N} ({time.time()-t0:.0f}s) shift|b*-bhat|={np.abs(s2["beta"]-s1["bhat"]).max():.1e}',s1,s2)
# E: structural zero column (no USDJPY-like rows): beta_US must be exactly 0
G,N=400,600
X=rng.normal(0,.3,(G,3));X[:,0]=0;sig=rng.uniform(.004,.008,G)
y=X@np.array([.004,-.006,.003])+sig*rng.standard_t(5,G);Z=rng.standard_t(5,(G,N))
P=Prob(X,sig,list(Z),y,np.full(G,1/G));s1,s2=solve(P);show('E zero column',s1,s2);print('   beta_US exactly 0:',s2['beta'][0]==0.0)
