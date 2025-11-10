use base64::engine::general_purpose::STANDARD as B64;
use base64::Engine as _;
use pyo3::{
    exceptions::{PyIOError, PyRuntimeError, PyValueError},
    prelude::*,
};
use ring::{rand::SystemRandom, signature};
use spki::{der::Decode, SubjectPublicKeyInfoRef};
use std::{fs, path::Path};

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
