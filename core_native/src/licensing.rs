use base64::engine::general_purpose::STANDARD as B64;
use base64::Engine as _;
use once_cell::sync::OnceCell;
use pyo3::{
    exceptions::{PyIOError, PyRuntimeError, PyValueError},
    prelude::*,
    types::{PyDict, PyList},
};
use ring::{rand::SystemRandom, signature};
use serde_json::{json, Map, Value};
use spki::{der::Decode, SubjectPublicKeyInfoRef};
use std::{
    fs,
    path::{Path, PathBuf},
};
use time::{
    format_description::well_known::Rfc3339, macros::format_description, OffsetDateTime,
    PrimitiveDateTime, UtcOffset,
};

#[pyclass(name = "LicenseStatus")]
pub struct LicenseStatus {
    #[pyo3(get)]
    valid: bool,
    #[pyo3(get)]
    reason: String,
    #[pyo3(get)]
    payload: Option<PyObject>,
}

#[pymethods]
impl LicenseStatus {
    #[new]
    #[pyo3(signature = (valid, reason, payload=None))]
    fn new(valid: bool, reason: String, payload: Option<PyObject>) -> Self {
        Self {
            valid,
            reason,
            payload,
        }
    }
}

impl LicenseStatus {
    fn ok(py: Python<'_>, payload: Map<String, Value>) -> PyResult<Self> {
        let dict = PyDict::new_bound(py);
        for (key, value) in payload {
            dict.set_item(key, json_to_py(py, value)?)?;
        }
        Ok(Self {
            valid: true,
            reason: "license_valid".to_string(),
            payload: Some(dict.into_py(py)),
        })
    }

    fn err(_py: Python<'_>, reason: impl Into<String>) -> PyResult<Self> {
        Ok(Self {
            valid: false,
            reason: reason.into(),
            payload: None,
        })
    }
}

#[pyfunction]
pub(crate) fn verify_signed_blob(payload_json: &str, sig_b64: &str) -> PyResult<bool> {
    verify_signed_blob_with_key(payload_json, sig_b64, crate::LIC_PUB_KEY_DER)
}

fn lic_pubkey_from_spki(spki_der: &[u8]) -> PyResult<signature::UnparsedPublicKey<Vec<u8>>> {
    // Validate it's really SPKI before handing to ring
    let spki = SubjectPublicKeyInfoRef::from_der(spki_der)
        .map_err(|_| PyErr::new::<PyValueError, _>("public key is not valid SPKI DER"))?;
    Ok(signature::UnparsedPublicKey::new(
        &signature::ECDSA_P256_SHA256_ASN1,
        spki.subject_public_key.raw_bytes().to_vec(),
    ))
}

/// Load PKCS#8 private key as DER. Accepts:
/// - PEM: "-----BEGIN PRIVATE KEY-----"
/// - raw DER bytes
fn load_pkcs8_der(path: &Path) -> PyResult<Vec<u8>> {
    let blob =
        fs::read(path).map_err(|e| PyErr::new::<PyIOError, _>(format!("read {path:?}: {e}")))?;
    // Try PEM first
    if let Ok(text) = std::str::from_utf8(&blob) {
        if text.contains("-----BEGIN PRIVATE KEY-----") {
            let der = pem_rfc7468::decode_vec(text.as_bytes())
                .map_err(|e| PyErr::new::<PyValueError, _>(format!("decode PKCS#8 PEM: {e}")))?;
            return Ok(der.1); // bytes
        }
        if text.contains("-----BEGIN EC PRIVATE KEY-----") {
            return Err(PyErr::new::<PyValueError, _>(
                "Found SEC1 EC private key. Convert to PKCS#8:\n  openssl pkcs8 -topk8 -nocrypt -in sec1.pem -out pkcs8.pem",
            ));
        }
    }
    // Fallback: raw DER
    Ok(blob)
}

/// Load SPKI public key as DER. Accepts:
/// - PEM: "-----BEGIN PUBLIC KEY-----"
/// - raw DER bytes
#[cfg(test)]
fn load_spki_der(path: &Path) -> PyResult<Vec<u8>> {
    let blob =
        fs::read(path).map_err(|e| PyErr::new::<PyIOError, _>(format!("read {path:?}: {e}")))?;
    if let Ok(text) = std::str::from_utf8(&blob) {
        if text.contains("-----BEGIN PUBLIC KEY-----") {
            let der = pem_rfc7468::decode_vec(&blob)
                .map_err(|e| PyErr::new::<PyValueError, _>(format!("decode SPKI PEM: {e}")))?;
            // Validate SPKI
            let _ = SubjectPublicKeyInfoRef::from_der(&der.1)
                .map_err(|_| PyErr::new::<PyValueError, _>("public key is not valid SPKI DER"))?;
            return Ok(der.1);
        }
    }
    // Validate SPKI
    let _ = SubjectPublicKeyInfoRef::from_der(&blob)
        .map_err(|_| PyErr::new::<PyValueError, _>("public key is not valid SPKI DER"))?;
    Ok(blob)
}

pub(crate) fn verify_signed_blob_with_key(
    payload_json: &str,
    sig_b64: &str,
    public_key_spki_der: &[u8],
) -> PyResult<bool> {
    let sig = B64
        .decode(sig_b64.as_bytes())
        .map_err(|_| PyErr::new::<PyValueError, _>("bad b64"))?;
    let pk = lic_pubkey_from_spki(public_key_spki_der)?;
    pk.verify(payload_json.as_bytes(), &sig)
        .map(|_| true)
        .map_err(|_| PyErr::new::<PyValueError, _>("bad sig"))
}

#[pyfunction]
pub(crate) fn sign_license_payload(payload_json: &str, private_key_path: &str) -> PyResult<String> {
    if payload_json.trim().is_empty() {
        return Err(PyErr::new::<PyValueError, _>("payload must not be empty"));
    }
    let pkcs8_der = load_pkcs8_der(Path::new(private_key_path))?;
    let rng = SystemRandom::new();
    let key_pair = signature::EcdsaKeyPair::from_pkcs8(
        &signature::ECDSA_P256_SHA256_ASN1_SIGNING,
        &pkcs8_der,
        &rng,
    )
    .map_err(|_| PyErr::new::<PyValueError, _>("rejected private key (expect PKCS#8)"))?;

    let sig = key_pair
        .sign(&rng, payload_json.as_bytes())
        .map_err(|_| PyErr::new::<PyRuntimeError, _>("failed to sign payload"))?;
    Ok(B64.encode(sig.as_ref())) // DER-encoded ECDSA signature
}

static FINGERPRINT_CACHE: OnceCell<String> = OnceCell::new();

fn machine_fingerprint() -> PyResult<String> {
    if let Some(fp) = FINGERPRINT_CACHE.get() {
        return Ok(fp.clone());
    }
    let fp = crate::get_machine_fingerprint()?;
    let _ = FINGERPRINT_CACHE.set(fp.clone());
    Ok(fp)
}

fn json_to_py(py: Python<'_>, value: Value) -> PyResult<PyObject> {
    Ok(match value {
        Value::Null => py.None(),
        Value::Bool(b) => b.into_py(py),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                i.into_py(py)
            } else if let Some(u) = n.as_u64() {
                u.into_py(py)
            } else if let Some(f) = n.as_f64() {
                f.into_py(py)
            } else {
                return Err(PyErr::new::<PyValueError, _>("unsupported number type"));
            }
        }
        Value::String(s) => s.into_py(py),
        Value::Array(items) => {
            let list = PyList::empty_bound(py);
            for item in items {
                list.append(json_to_py(py, item)?)?;
            }
            list.into_py(py)
        }
        Value::Object(map) => {
            let dict = PyDict::new_bound(py);
            for (k, v) in map {
                dict.set_item(k, json_to_py(py, v)?)?;
            }
            dict.into_py(py)
        }
    })
}

fn normalize_blob(raw: &str) -> String {
    raw.split_whitespace().collect::<String>()
}

fn decode_blob(blob: &str) -> Result<(String, String, String), String> {
    let normalized = normalize_blob(blob);
    let (payload_b64, signature_b64) = normalized
        .split_once('.')
        .ok_or_else(|| "license format must be <payload_b64>.<signature_b64>".to_string())?;
    let payload_json = B64
        .decode(payload_b64.as_bytes())
        .map_err(|_| "payload base64 is invalid".to_string())
        .and_then(|bytes| {
            String::from_utf8(bytes).map_err(|_| "payload base64 is invalid".to_string())
        })?;
    Ok((payload_json, payload_b64.to_string(), signature_b64.to_string()))
}

fn parse_expiry(raw: &str) -> Option<OffsetDateTime> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return None;
    }
    if let Ok(dt) = OffsetDateTime::parse(trimmed, &Rfc3339) {
        return Some(dt.to_offset(UtcOffset::UTC));
    }
    if let Ok(dt) =
        PrimitiveDateTime::parse(trimmed, &format_description!("[year]-[month]-[day]T[hour]:[minute]:[second]"))
    {
        return Some(dt.assume_utc());
    }
    None
}

fn verify_payload(payload_json: &str, signature_b64: &str) -> Result<Map<String, Value>, String> {
    let verified = verify_signed_blob_with_key(payload_json, signature_b64, crate::LIC_PUB_KEY_DER)
        .map_err(|err| err.to_string())?;
    if !verified {
        return Err("signature invalid".to_string());
    }
    let parsed: Value =
        serde_json::from_str(payload_json).map_err(|_| "payload is not valid JSON".to_string())?;
    let object = parsed
        .as_object()
        .cloned()
        .ok_or_else(|| "payload is not an object".to_string())?;
    Ok(object)
}

fn validate_payload(payload: &Map<String, Value>) -> Result<(), String> {
    let fingerprint = payload
        .get("fingerprint")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "missing_fingerprint".to_string())?;
    let current_fp = machine_fingerprint().map_err(|e| e.to_string())?;
    if fingerprint != current_fp {
        return Err("fingerprint_mismatch".to_string());
    }

    if let Some(exp) = payload.get("exp").and_then(|v| v.as_str()) {
        let expiry = parse_expiry(exp).ok_or_else(|| "invalid_expiry_format".to_string())?;
        if expiry < OffsetDateTime::now_utc() {
            return Err("license_expired".to_string());
        }
    }

    Ok(())
}

fn license_dir() -> Option<PathBuf> {
    #[cfg(windows)]
    {
        std::env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .or_else(|| {
                std::env::var_os("USERPROFILE")
                    .map(|p| PathBuf::from(p).join("AppData").join("Local"))
            })
            .map(|base| base.join("shahin").join("license"))
    }

    #[cfg(not(windows))]
    {
        std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".shahin").join("license"))
    }
}

fn license_file_path() -> PyResult<PathBuf> {
    let dir = license_dir().ok_or_else(|| PyErr::new::<PyIOError, _>("could not resolve data dir"))?;
    fs::create_dir_all(&dir)
        .map_err(|e| PyErr::new::<PyIOError, _>(format!("create {dir:?}: {e}")))?;
    Ok(dir.join("license.json"))
}

fn read_license_from_disk() -> Option<String> {
    let path = license_file_path().ok()?;
    if !path.exists() {
        return None;
    }
    let raw = fs::read_to_string(path).ok()?;
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return None;
    }
    if trimmed.starts_with('{') {
        let parsed: Value = serde_json::from_str(trimmed).ok()?;
        if let Some(obj) = parsed.as_object() {
            if let Some(blob) = obj.get("license").and_then(|v| v.as_str()) {
                return Some(normalize_blob(blob));
            }
            let payload = obj.get("payload_b64").and_then(|v| v.as_str());
            let signature = obj.get("signature_b64").and_then(|v| v.as_str());
            if let (Some(p), Some(s)) = (payload, signature) {
                return Some(normalize_blob(&format!("{p}.{s}")));
            }
        }
        return None;
    }
    Some(normalize_blob(trimmed))
}

fn write_license_to_disk(blob: &str) -> PyResult<()> {
    let path = license_file_path()?;
    let data = json!({
        "license": normalize_blob(blob)
    });
    fs::write(&path, serde_json::to_vec(&data).unwrap())
        .map_err(|e| PyErr::new::<PyIOError, _>(format!("write {path:?}: {e}")))
}

fn verify_license_blob_impl(py: Python<'_>, blob: &str) -> PyResult<LicenseStatus> {
    match decode_blob(blob)
        .and_then(|(payload_json, _, signature)| verify_payload(&payload_json, &signature))
        .and_then(|payload| {
            validate_payload(&payload)?;
            Ok(payload)
        })
    {
        Ok(payload) => LicenseStatus::ok(py, payload),
        Err(reason) => LicenseStatus::err(py, reason),
    }
}

#[pyfunction(name = "verify_license_blob")]
pub(crate) fn verify_license_blob_py(py: Python<'_>, blob: &str) -> PyResult<LicenseStatus> {
    verify_license_blob_impl(py, blob)
}

#[pyfunction(name = "license_status")]
pub(crate) fn license_status_py(py: Python<'_>) -> PyResult<LicenseStatus> {
    let blob = read_license_from_disk();
    match blob {
        Some(value) => verify_license_blob_impl(py, &value),
        None => LicenseStatus::err(py, "missing_license"),
    }
}

#[pyfunction(name = "license_is_valid")]
pub(crate) fn license_is_valid_py(py: Python<'_>) -> PyResult<bool> {
    Ok(license_status_py(py)?.valid)
}

#[pyfunction(name = "activate_license")]
pub(crate) fn activate_license_py(py: Python<'_>, blob: &str) -> PyResult<LicenseStatus> {
    let status = verify_license_blob_impl(py, blob)?;
    if status.valid {
        if let Err(err) = write_license_to_disk(blob) {
            eprintln!("failed_to_store_license: {err:?}");
            return LicenseStatus::err(py, "write_failed");
        }
        // Re-read so any normalization is reflected and the write actually landed.
        return license_status_py(py);
    }
    Ok(status)
}

#[pyfunction(name = "current_license_summary")]
pub(crate) fn current_license_summary_py(py: Python<'_>) -> PyResult<Option<PyObject>> {
    let status = license_status_py(py)?;
    if !status.valid {
        return Ok(None);
    }
    if let Some(payload) = status.payload {
        let payload_dict = payload
            .bind(py)
            .downcast::<PyDict>()
            .map_err(|_| PyErr::new::<PyValueError, _>("payload is not a dict"))?;
        let summary = PyDict::new_bound(py);
        for (key, value) in payload_dict.iter() {
            if let Ok(k) = key.extract::<&str>() {
                if k == "signature" {
                    continue;
                }
            }
            summary.set_item(key, value)?;
        }
        return Ok(Some(summary.into_py(py)));
    }
    Ok(None)
}

#[cfg(test)]
mod tests {
    use super::*;
    use ring::signature::KeyPair;
    use serde_json::Value;
    use std::collections::BTreeMap;

    #[cfg(test)]
    fn ensure_python() {
        use std::sync::Once;
        static START: Once = Once::new();
        START.call_once(|| {
            pyo3::prepare_freethreaded_python();
        });
    }

    #[test]
    fn sign_and_verify_with_openssl_keys() {
        ensure_python();

        // Adjust to your repo layout
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join(".keys");
        let priv_pem = root.join("licensing_private_pkcs8.pem");
        let pub_der = root.join("licensing_public.der");

        // Stable JSON
        let mut payload: BTreeMap<String, _> = BTreeMap::new();
        payload.insert("customer".into(), Value::String("tester".into()));
        payload.insert(
            "features".into(),
            Value::Array(vec![Value::String("backend".into())]),
        );
        payload.insert(
            "fingerprint".into(),
            Value::String("deadbeefdeadbeefdeadbeefdeadbeef".into()),
        );
        payload.insert(
            "issued_at".into(),
            Value::String("2025-01-01T00:00:00Z".into()),
        );
        payload.insert("license_id".into(), Value::String("123".into()));

        let payload_str = serde_json::to_string(&payload).unwrap();

        // Sign
        let sig_b64 = sign_license_payload(&payload_str, priv_pem.to_str().unwrap()).unwrap();

        // Verify against SPKI DER
        let spki_der = load_spki_der(&pub_der).unwrap();
        // Sanity: SPKI’s raw point equals signer’s point
        {
            let pkcs8_der = load_pkcs8_der(&priv_pem).unwrap();
            let kp = ring::signature::EcdsaKeyPair::from_pkcs8(
                &ring::signature::ECDSA_P256_SHA256_ASN1_SIGNING,
                &pkcs8_der,
                &ring::rand::SystemRandom::new(),
            )
            .unwrap();
            let signer_point = kp.public_key().as_ref(); // SEC1 uncompressed
            let spki = SubjectPublicKeyInfoRef::from_der(&spki_der).unwrap();
            assert_eq!(
                spki.subject_public_key.raw_bytes(),
                signer_point,
                "pubkey mismatch"
            );
        }

        let ok = verify_signed_blob_with_key(&payload_str, &sig_b64, &spki_der).unwrap();
        assert!(ok);
    }
}
