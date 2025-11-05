import sys
import ctypes
from threading import Thread
import time
import os
from pathlib import Path
import hashlib
import uuid
import subprocess
import json
import requests
import logging

# CONFIG / BUILD-TIME VALUES (replace during build/release)
PRODUCT_SALT = b"shahin-product-salt-v1"  # per-product bake-in salt
MIN_MATCH_SIGNALS = 3  # K-of-N tolerance, choose per policy
LICENSE_DIR = Path(os.getenv("LOCALAPPDATA") or os.path.expanduser("~/.shahin"))
ENCRYPTED_LICENSE_PATH = LICENSE_DIR / "license.enc"

# Embedded public key for validating license signatures and manifests
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAn_example_KEY_replace
-----END PUBLIC KEY-----"""

# Embedded integrity manifest (example). At build time generate a manifest_json and sign it.
# manifest_json should include exe_hash (sha256 hex) and timestamp.
EMBEDDED_MANIFEST_JSON = (
    '{"exe_hash":"<replace_at_build_time>","timestamp":"2025-01-01T00:00:00Z"}'
)
EMBEDDED_MANIFEST_SIG_B64 = "<replace_base64_sig_at_build_time>"

# Setup minimal logging for support
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# --- Mandatory crypto imports (fail closed if unavailable) ---
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    CRYPTO_AVAILABLE = True
except Exception:
    CRYPTO_AVAILABLE = False

if not CRYPTO_AVAILABLE:
    # Fail closed: cryptography must be vendored into the bundle.
    logging.critical("cryptography library unavailable: failing closed")
    sys.exit(1)


# --- Helpers: integrity verification of embedded manifest (self-check) ---
def _compute_exe_hash():
    """Compute SHA256 of the running executable (frozen) or the main source file."""
    exe_path = (
        Path(sys.executable)
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve()
    )
    h = hashlib.sha256()
    try:
        with open(exe_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def verify_embedded_manifest():
    """
    Verify the embedded manifest signature and compare exe hash.
    Fail closed if verification is impossible or mismatch.
    """
    try:
        manifest_bytes = EMBEDDED_MANIFEST_JSON.encode("utf-8")
        # verify manifest signature with embedded public key
        pub = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
        import base64

        sig = base64.b64decode(EMBEDDED_MANIFEST_SIG_B64)
        pub.verify(sig, manifest_bytes, padding.PKCS1v15(), hashes.SHA256())
        manifest = json.loads(EMBEDDED_MANIFEST_JSON)
        exe_hash_expected = manifest.get("exe_hash")
        actual = _compute_exe_hash()
        if not actual or not exe_hash_expected or actual != exe_hash_expected:
            logging.critical("integrity manifest mismatch: failing closed")
            return False
        return True
    except Exception as e:
        logging.critical(f"integrity verification failed: {e}")
        return False


# --- HWID signals collection and salt-hashed signal values ---
def _signal_machine_guid():
    if sys.platform.startswith("win"):
        try:
            out = subprocess.check_output(
                [
                    "reg",
                    "query",
                    r"HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography",
                    "/v",
                    "MachineGuid",
                ],
                stderr=subprocess.DEVNULL,
            ).decode(errors="ignore")
            # parse value
            parts = out.strip().split()
            return parts[-1] if parts else ""
        except Exception:
            return ""
    return ""


def _signal_disk_serial():
    try:
        if sys.platform.startswith("win"):
            out = subprocess.check_output(
                ["wmic", "diskdrive", "get", "SerialNumber"], stderr=subprocess.DEVNULL
            ).decode(errors="ignore")
            # Pick first serial-like token
            lines = [l.strip() for l in out.splitlines() if l.strip()]
            return lines[1] if len(lines) > 1 else ""
        else:
            return ""
    except Exception:
        return ""


def _signal_cpu_id():
    try:
        if sys.platform.startswith("win"):
            out = subprocess.check_output(
                ["wmic", "cpu", "get", "ProcessorId"], stderr=subprocess.DEVNULL
            ).decode(errors="ignore")
            lines = [l.strip() for l in out.splitlines() if l.strip()]
            return lines[1] if len(lines) > 1 else ""
        else:
            return ""
    except Exception:
        return ""


def _signal_hostname():
    try:
        return subprocess.check_output(["hostname"]).decode().strip()
    except Exception:
        return ""


def _signal_mac():
    try:
        mac = uuid.getnode()
        return f"{mac:012x}"
    except Exception:
        return ""


SIGNAL_FUNCS = {
    "install_guid": _signal_machine_guid,
    "disk_serial": _signal_disk_serial,
    "cpu_id": _signal_cpu_id,
    "hostname": _signal_hostname,
    "mac": _signal_mac,
}


def collect_hw_signals():
    """Return dict signal_name -> salted hash (hex)."""
    res = {}
    for name, fn in SIGNAL_FUNCS.items():
        try:
            val = fn() or ""
            h = hashlib.sha256(PRODUCT_SALT + name.encode() + val.encode()).hexdigest()
            res[name] = h
        except Exception:
            res[name] = ""
    return res


# --- Seal key derivation and secure license storage (AES-GCM) ---
def derive_seal_key(signals_dict):
    """
    Derive a 32-byte seal key via HKDF over the concatenation of sorted signal values.
    This ties the key to the current HW signals.
    """
    concat = b"".join(signals_dict[k].encode() for k in sorted(signals_dict.keys()))
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=PRODUCT_SALT,
        info=b"shahin-license-seal",
    )
    return hkdf.derive(concat)


def encrypt_license_blob(blob_dict, seal_key):
    try:
        aes = AESGCM(seal_key)
        nonce = os.urandom(12)
        plaintext = json.dumps(blob_dict, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        ct = aes.encrypt(nonce, plaintext, None)
        return nonce + ct
    except Exception:
        return None


def decrypt_license_blob(data_bytes, seal_key):
    try:
        aes = AESGCM(seal_key)
        nonce = data_bytes[:12]
        ct = data_bytes[12:]
        pt = aes.decrypt(nonce, ct, None)
        return json.loads(pt.decode("utf-8"))
    except Exception:
        return None


# --- Signature verification (detached signature, payload is canonical JSON) ---
def verify_signature_on_payload(payload_obj, signature_b64):
    try:
        payload_bytes = json.dumps(
            payload_obj, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        pub = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
        import base64

        sig = base64.b64decode(signature_b64)
        pub.verify(sig, payload_bytes, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


# --- License validation logic (offline-first) ---
def validate_payload_hw_match(payload):
    """
    Payload is expected to include 'hwid_hashes' mapping signal->hash, or an aggregated hwid list.
    Accept if at least MIN_MATCH_SIGNALS signals match the local computed signals.
    """
    try:
        payload_hw = payload.get("hwid_hashes", {})  # dict expected
        local = collect_hw_signals()
        matches = 0
        for sig_name, expected_hash in payload_hw.items():
            if (
                expected_hash
                and local.get(sig_name)
                and expected_hash == local.get(sig_name)
            ):
                matches += 1
        return matches >= MIN_MATCH_SIGNALS
    except Exception:
        return False


def check_payload_expiry(payload):
    exp = payload.get("expiry")
    if not exp:
        return True
    try:
        from datetime import datetime, timezone

        exp_dt = datetime.fromisoformat(exp)
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) <= exp_dt
    except Exception:
        return False


def accept_and_cache_license(payload, signature_b64):
    """
    Verify signature, validate hwid match & expiry, then encrypt and cache.
    Returns True if accepted and cached.
    """
    if not verify_signature_on_payload(payload, signature_b64):
        logging.warning("license signature invalid")
        return False
    if not check_payload_expiry(payload):
        logging.warning("license expired")
        return False
    if not validate_payload_hw_match(payload):
        logging.warning("HWID signals do not match")
        return False
    # Encrypt and store using derived seal key
    signals = collect_hw_signals()
    key = derive_seal_key(signals)
    blob = {"payload": payload, "signature": signature_b64}
    enc = encrypt_license_blob(blob, key)
    if not enc:
        logging.critical("failed to encrypt license: failing closed")
        return False
    try:
        LICENSE_DIR.mkdir(parents=True, exist_ok=True)
        with open(ENCRYPTED_LICENSE_PATH, "wb") as f:
            f.write(enc)
        try:
            os.chmod(ENCRYPTED_LICENSE_PATH, 0o600)
        except Exception:
            pass
        logging.info("license accepted and cached")
        return True
    except Exception as e:
        logging.critical(f"failed to persist license: {e}")
        return False


def load_cached_license():
    """Attempt to decrypt and return cached license blob (dict) or None."""
    try:
        if not ENCRYPTED_LICENSE_PATH.exists():
            return None
        data = ENCRYPTED_LICENSE_PATH.read_bytes()
        key = derive_seal_key(collect_hw_signals())
        blob = decrypt_license_blob(data, key)
        if not blob:
            # decrypt failed: treat as absent/invalid
            return None
        # verify signature and expiry again
        payload = blob.get("payload")
        signature = blob.get("signature")
        if (
            payload
            and signature
            and verify_signature_on_payload(payload, signature)
            and check_payload_expiry(payload)
        ):
            # Also ensure HWID still matches (with tolerance)
            if validate_payload_hw_match(payload):
                return blob
    except Exception:
        pass
    return None


# --- Remote fetch (signed blobs only). Treat remote as untrusted transport. ---
def fetch_signed_blob_from_url(url, timeout=6):
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            # expect {"payload": {...}, "signature": "<base64>"}
            return r.json()
    except Exception:
        pass
    return None


def try_fetch_and_activate_from_remote(url):
    blob = fetch_signed_blob_from_url(url)
    if not blob:
        return False
    payload = blob.get("payload")
    signature = blob.get("signature")
    if not payload or not signature:
        return False
    return accept_and_cache_license(payload, signature)


# --- Runtime state and gating token ---
_LICENSE_VALID = False
_LICENSE_REASON = "uninitialized"


def _set_license_state(valid, reason=None):
    global _LICENSE_VALID, _LICENSE_REASON
    _LICENSE_VALID = bool(valid)
    _LICENSE_REASON = reason or (None if valid else "unknown")


def license_is_valid():
    return _LICENSE_VALID


# --- Startup and periodic checks ---
def startup_checks(allow_remote_fetch=True):
    # 1) Verify embedded manifest (self-integrity) first
    if not verify_embedded_manifest():
        logging.critical("embedded manifest verification failed: exiting")
        _set_license_state(False, "integrity_failed")
        return False

    # 2) Try local cached license first (offline-first)
    cached = load_cached_license()
    if cached:
        _set_license_state(True, "cached_valid")
        return True

    # 3) If allowed, attempt remote signed blob (URL controlled via env)
    if allow_remote_fetch:
        remote_url = os.getenv(
            "LICENSE_REMOTE_URL"
        )  # e.g. raw gist url returning signed JSON
        if remote_url:
            if try_fetch_and_activate_from_remote(remote_url):
                _set_license_state(True, "remote_activated")
                return True

    # 4) No valid license => fail closed
    _set_license_state(False, "no_valid_license")
    logging.critical("no valid license available: exiting")
    return False


def periodic_recheck(interval_seconds=3600):
    """Periodically re-validate license and optional CRL/allow-list.
    This function updates _LICENSE_VALID so other parts can gate features.
    """
    while True:
        try:
            # re-derive from cached license (decrypt and re-verify expiry)
            cached = load_cached_license()
            if cached:
                _set_license_state(True, "periodic_ok")
            else:
                # optional: fetch a signed CRL/allowlist and apply (must be signed)
                crl_url = os.getenv("LICENSE_CRL_URL")
                if crl_url:
                    crl_blob = fetch_signed_blob_from_url(crl_url)
                    # CRL handling omitted for brevity — enforce signing & expiry
                    # If CRL indicates revocation of current license_id -> set invalid
                    pass
                # if no cached and no valid remote -> mark invalid
                _set_license_state(False, "periodic_no_license")
        except Exception:
            _set_license_state(False, "periodic_error")
        time.sleep(interval_seconds)


# --- Anti-debugging (simple checks) ---
def detect_debugger():
    """Simple anti-debug; keep lightweight and non-invasive."""
    try:
        if sys.platform.startswith("win"):
            if ctypes.windll.kernel32.IsDebuggerPresent():
                logging.critical("debugger detected: exiting")
                sys.exit(1)
    except Exception:
        pass


# --- Main runtime guard: run at import/startup and spawn periodic thread ---
def runtime_guard():
    # perform startup checks (integrity + license)
    ok = startup_checks(allow_remote_fetch=True)
    if not ok:
        sys.exit(1)

    # Start periodic recheck thread (gates license_is_valid)
    Thread(target=periodic_recheck, args=(3600,), daemon=True).start()

    # keep lightweight runtime anti-debug loop in this module to trip if someone attaches
    while True:
        detect_debugger()
        # If the periodic recheck invalidated license, fail closed after short grace
        if not license_is_valid():
            logging.critical(f"license invalidated: {_LICENSE_REASON}")
            sys.exit(1)
        time.sleep(1)


# Start protection thread on import — ensures early enforcement
Thread(target=runtime_guard, daemon=True).start()
