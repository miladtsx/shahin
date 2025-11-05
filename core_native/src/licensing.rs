use base64::Engine as _;
use base64::engine::general_purpose::STANDARD;
use pyo3::prelude::*;
use ring::signature;

fn lic_pubkey() -> signature::UnparsedPublicKey<Vec<u8>> {
    signature::UnparsedPublicKey::new(
        &signature::ECDSA_P256_SHA256_ASN1,
        super::LIC_PUB_KEY_DER.to_vec(),
    )
}

#[pyfunction]
pub(crate) fn verify_signed_blob(payload_json: &str, sig_b64: &str) -> PyResult<bool> {
    let sig = STANDARD
        .decode(sig_b64)
        .map_err(|_| PyErr::new::<pyo3::exceptions::PyValueError, _>("bad b64"))?;
    let pk = lic_pubkey();
    pk.verify(payload_json.as_bytes(), &sig)
        .map(|_| true)
        .map_err(|_| PyErr::new::<pyo3::exceptions::PyValueError, _>("bad sig"))
}
