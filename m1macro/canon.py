"""Canonical serialization and hashes (M1-MACRO-IMPL-PART4-V1 §2).

All functions are pure. Floats are serialized as IEEE-754 binary64, big-endian,
lowercase hex (16 chars). +0.0 and -0.0 are distinct. NaN/Inf raise NonFinite.
"""
from __future__ import annotations

import hashlib
import math
import struct
from typing import Iterable, Sequence


class NonFinite(ValueError):
    pass


def f64hex(x: float) -> str:
    x = float(x)
    if not math.isfinite(x):
        raise NonFinite(repr(x))
    return struct.pack(">d", x).hex()


def hex2f64(h: str) -> float:
    return struct.unpack(">d", bytes.fromhex(h))[0]


def int_ascii(n: int) -> str:
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("integer required")
    return str(n)


def _lines(lines: Iterable[str]) -> bytes:
    out = []
    for ln in lines:
        if "\n" in ln or "\r" in ln:
            raise ValueError("newline inside a field line")
        out.append(ln + "\n")
    return "".join(out).encode("utf-8")


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def pool_sorted(z: Sequence[float]) -> list:
    """Numeric ascending; numeric ties broken by ASCII order of the hex string (+0.0 before -0.0)."""
    for v in z:
        if not math.isfinite(v):
            raise NonFinite(repr(v))
    return sorted((float(v) for v in z), key=lambda v: (v, f64hex(v)))


def pool_bytes(pair: str, origin: str, horizon: str, z: Sequence[float]) -> bytes:
    zs = pool_sorted(z)
    lines = ["POOL_V1", f"{pair},{origin},{horizon},{int_ascii(len(zs))}"]
    lines += [f64hex(v) for v in zs]
    return _lines(lines)


def pool_sha256(pair: str, origin: str, horizon: str, z: Sequence[float]) -> str:
    return sha256_hex(pool_bytes(pair, origin, horizon, z))


def e_input_bytes(origin_t: str, horizon: str, n_e: int, groups: Sequence[dict]) -> bytes:
    """groups: dicts with origin, pair, n_p, x_us, x_jp, x_pos, sigma, y, pool_sha256.
    Must already be in canonical order (origin ascending, pair ASCII)."""
    keys = [(g["origin"], g["pair"]) for g in groups]
    if keys != sorted(keys):
        raise ValueError("groups not in canonical order")
    lines = ["E_INPUT_V1", f"{origin_t},{horizon},{int_ascii(n_e)},{int_ascii(len(groups))}"]
    for g in groups:
        lines.append(",".join([g["origin"], g["pair"], int_ascii(g["n_p"]), f64hex(g["x_us"]), f64hex(g["x_jp"]),
                               f64hex(g["x_pos"]), f64hex(g["sigma"]), f64hex(g["y"]), g["pool_sha256"]]))
    return _lines(lines)


def beta_bytes(origin_t: str, horizon: str, state: str, beta) -> bytes:
    if state in ("ESTIMATION_FAILED", "NOT_EVALUATED"):
        b = ["", "", ""]
    else:
        b = [f64hex(v) for v in beta]
    return _lines(["BETA_V1", ",".join([origin_t, horizon, state] + b)])


def code_manifest_bytes(entries: Sequence[tuple]) -> bytes:
    """entries: (path, sha256) pairs; sorted by path ASCII."""
    es = sorted(entries)
    return _lines(["CODE_MANIFEST_V1"] + [f"{p},{h}" for p, h in es])


def range_sha256(row_bytes: Sequence[bytes]) -> str:
    return sha256_hex(b"".join(row_bytes))


def pool_sorted_np(z):
    """Vectorized pool_sorted (same order): numeric sort, then within the run of zeros +0.0 before -0.0
    (the only numerically equal values whose hex strings differ)."""
    import numpy as np
    a = np.asarray(z, dtype=np.float64)
    if not np.all(np.isfinite(a)):
        raise NonFinite("pool")
    a = np.sort(a, kind="stable")
    zero = np.flatnonzero(a == 0.0)
    if len(zero):
        lo, hi = zero[0], zero[-1] + 1
        neg = np.signbit(a[lo:hi]).sum()
        a[lo:hi - neg] = 0.0
        a[hi - neg:hi] = -0.0
    return a


def pool_bytes_np(pair: str, origin: str, horizon: str, z) -> bytes:
    import numpy as np
    a = pool_sorted_np(z)
    hx = np.ascontiguousarray(a, dtype=">f8").tobytes().hex()
    body = "\n".join(hx[i:i + 16] for i in range(0, len(hx), 16))
    head = f"POOL_V1\n{pair},{origin},{horizon},{int_ascii(len(a))}\n"
    return (head + body + ("\n" if len(a) else "")).encode("ascii")


def pool_sha256_np(pair: str, origin: str, horizon: str, z) -> str:
    return sha256_hex(pool_bytes_np(pair, origin, horizon, z))
