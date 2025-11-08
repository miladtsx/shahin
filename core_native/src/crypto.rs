use pyo3::prelude::*;
use ring::aead::{self, Aad, LessSafeKey, UnboundKey, NONCE_LEN};

#[pyfunction]
pub(crate) fn seal(key_material: &[u8], plaintext: &[u8]) -> PyResult<Vec<u8>> {
    let unbound = UnboundKey::new(&aead::AES_256_GCM, key_material)
        .map_err(|_| PyErr::new::<pyo3::exceptions::PyValueError, _>("bad key"))?;
    let key = LessSafeKey::new(unbound);
    let nonce = [0u8; NONCE_LEN]; // replace with random nonce + prepend
    let mut buf = plaintext.to_vec();
    key.seal_in_place_append_tag(
        aead::Nonce::assume_unique_for_key(nonce),
        Aad::empty(),
        &mut buf,
    )
    .map_err(|_| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("seal fail"))?;
    let mut out = nonce.to_vec();
    out.extend_from_slice(&buf);
    Ok(out)
}

#[pyfunction]
pub(crate) fn unseal(key_material: &[u8], nonce_and_ct: &[u8]) -> PyResult<Vec<u8>> {
    if nonce_and_ct.len() < NONCE_LEN {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>("short"));
    }
    let (nonce_bytes, ct) = nonce_and_ct.split_at(NONCE_LEN);
    let nonce_arr: [u8; NONCE_LEN] = nonce_bytes
        .try_into()
        .map_err(|_| PyErr::new::<pyo3::exceptions::PyValueError, _>("bad nonce"))?;
    let unbound = UnboundKey::new(&aead::AES_256_GCM, key_material)
        .map_err(|_| PyErr::new::<pyo3::exceptions::PyValueError, _>("bad key"))?;
    let key = LessSafeKey::new(unbound);
    let nonce = aead::Nonce::try_assume_unique_for_key(&nonce_arr)
        .map_err(|_| PyErr::new::<pyo3::exceptions::PyValueError, _>("bad nonce"))?;
    let mut ct_buf = ct.to_vec();
    let pt = key
        .open_in_place(nonce, Aad::empty(), &mut ct_buf)
        .map_err(|_| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("open fail"))?;
    Ok(pt.to_vec())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn seal_and_unseal_roundtrip() {
        let key = [0xAA; 32];
        let plaintext = b"test payload";

        let sealed = seal(&key, plaintext).expect("seal");
        let unsealed = unseal(&key, &sealed).expect("unseal");
        assert_eq!(unsealed, plaintext);
    }

    #[test]
    fn unseal_rejects_short_ciphertext() {
        let key = [0xAA; 32];
        assert!(unseal(&key, &[0u8; 8]).is_err());
    }

    #[test]
    fn seal_rejects_short_key() {
        let key = [0xAA; 16];
        assert!(seal(&key, b"payload").is_err());
    }
}
