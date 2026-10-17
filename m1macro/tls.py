"""CFTC transport (Impl Part 1 V1.2 §3): system CA + pinned Sectigo Public Server Authentication Root R46.
Fingerprint checked at startup; the extra root is used for CFTC host names only; verification is never disabled."""
import base64
import hashlib
import json
import ssl
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
CFTC_HOSTS = ("www.cftc.gov", "cftc.gov", "publicreporting.cftc.gov")


class PinMismatch(Exception):
    pass


def _cfg():
    return json.loads((HERE / "config" / "m1macro_config.json").read_text("utf-8"))["cftc_tls"]


def pem_der(text: str) -> bytes:
    body = text.split("-----BEGIN CERTIFICATE-----")[1].split("-----END CERTIFICATE-----")[0]
    return base64.b64decode("".join(body.split()))


def check_pin() -> Path:
    c = _cfg(); p = HERE / c["root_file"]
    text = p.read_text("ascii")
    if text.count("-----BEGIN CERTIFICATE-----") != 1:
        raise PinMismatch("pinned file must hold exactly one certificate")
    fp = hashlib.sha256(pem_der(text)).hexdigest()
    if fp != c["root_sha256"].lower():
        raise PinMismatch("pinned root fingerprint mismatch")
    return p


def context_for(url: str):
    host = (urlsplit(url).hostname or "").lower()
    if host not in CFTC_HOSTS:
        return None                      # default urllib verification (system CA)
    ctx = ssl.create_default_context()   # system CA kept
    ctx.load_verify_locations(cafile=str(check_pin()))
    return ctx
