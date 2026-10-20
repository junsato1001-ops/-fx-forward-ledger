from m1macro import canon as c


def run():
    r = {}
    assert c.f64hex(0.0) == "0000000000000000"
    assert c.f64hex(-0.0) == "8000000000000000"
    assert c.f64hex(1.0) == "3ff0000000000000"
    for bad in (float("nan"), float("inf")):
        try:
            c.f64hex(bad); raise AssertionError("nonfinite accepted")
        except c.NonFinite:
            pass
    assert c.pool_sorted([0.5, -0.0, 0.0, -1.0]) == [-1.0, 0.0, -0.0, 0.5]
    s = c.pool_sorted([0.5, -0.0, 0.0, -1.0])
    assert [c.f64hex(v) for v in s][1:3] == ["0000000000000000", "8000000000000000"]
    b = c.pool_bytes("USDJPY", "2026-10-19", "1D", [1.0, -1.0])
    assert b == b"POOL_V1\nUSDJPY,2026-10-19,1D,2\nbff0000000000000\n3ff0000000000000\n"
    r["pool_sha256_example"] = c.sha256_hex(b)
    import numpy as np
    rng = np.random.default_rng(0)
    for k in range(400):                     # vectorized path == reference path, byte for byte
        n = int(rng.integers(0, 80))
        z = (rng.choice([0.0, -0.0, 1.5, -1.5, 2.0, -2.25], size=n) if k % 2 else rng.normal(size=n)).tolist()
        assert c.pool_bytes("CHFJPY", "2020-01-01", "4W", z) == c.pool_bytes_np("CHFJPY", "2020-01-01", "4W", z)
    r["np_path_equal"] = True
    return r
