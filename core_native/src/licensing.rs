use base64::engine::general_purpose::STANDARD;
use base64::Engine as _;
use pyo3::prelude::*;
use ring::signature;

fn lic_pubkey_from_bytes(bytes: &[u8]) -> signature::UnparsedPublicKey<Vec<u8>> {
    signature::UnparsedPublicKey::new(&signature::ECDSA_P256_SHA256_ASN1, bytes.to_vec())
}

pub(crate) fn verify_signed_blob_with_key(
    payload_json: &str,
    sig_b64: &str,
    public_key_der: &[u8],
) -> PyResult<bool> {
    let sig = STANDARD
        .decode(sig_b64)
        .map_err(|_| PyErr::new::<pyo3::exceptions::PyValueError, _>("bad b64"))?;
    let pk = lic_pubkey_from_bytes(public_key_der);
    pk.verify(payload_json.as_bytes(), &sig)
        .map(|_| true)
        .map_err(|_| PyErr::new::<pyo3::exceptions::PyValueError, _>("bad sig"))
}

#[pyfunction]
pub(crate) fn verify_signed_blob(payload_json: &str, sig_b64: &str) -> PyResult<bool> {
    verify_signed_blob_with_key(payload_json, sig_b64, super::LIC_PUB_KEY_DER)
}

#[cfg(test)]
mod tests {
    use super::*;
    use base64::engine::general_purpose::STANDARD;
    use ring::{rand::SystemRandom, signature, signature::KeyPair};

    #[test]
    fn verify_signed_blob_accepts_valid_signature() {
        let rng = SystemRandom::new();
        let pkcs8 = signature::EcdsaKeyPair::generate_pkcs8(
            &signature::ECDSA_P256_SHA256_ASN1_SIGNING,
            &rng,
        )
        .expect("generate test key");
        let key_pair = signature::EcdsaKeyPair::from_pkcs8(
            &signature::ECDSA_P256_SHA256_ASN1_SIGNING,
            pkcs8.as_ref(),
            &rng,
        )
        .expect("parse test key");

        let payload = r#"{"foo":"bar"}"#;
        let sign_rng = SystemRandom::new();
        let sig = key_pair
            .sign(&sign_rng, payload.as_bytes())
            .expect("sign payload")
            .as_ref()
            .to_vec();
        let sig_b64 = STANDARD.encode(&sig);

        let result = verify_signed_blob_with_key(payload, &sig_b64, key_pair.public_key().as_ref());
        assert_eq!(result.unwrap(), true);
    }

    #[test]
    fn verify_signed_blob_rejects_tampered_payload() {
        let rng = SystemRandom::new();
        let pkcs8 = signature::EcdsaKeyPair::generate_pkcs8(
            &signature::ECDSA_P256_SHA256_ASN1_SIGNING,
            &rng,
        )
        .expect("generate test key");
        let key_pair = signature::EcdsaKeyPair::from_pkcs8(
            &signature::ECDSA_P256_SHA256_ASN1_SIGNING,
            pkcs8.as_ref(),
            &rng,
        )
        .expect("parse test key");

        let payload = r#"{"foo":"bar"}"#;
        let sign_rng = SystemRandom::new();
        let sig = key_pair
            .sign(&sign_rng, payload.as_bytes())
            .expect("sign payload")
            .as_ref()
            .to_vec();
        let sig_b64 = STANDARD.encode(&sig);

        let result = verify_signed_blob_with_key(
            r#"{"foo":"baz"}"#,
            &sig_b64,
            key_pair.public_key().as_ref(),
        );
        assert!(result.is_err());
    }
}
