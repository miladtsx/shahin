use anyhow::{anyhow, Context, Result};
use chacha20poly1305::{
    aead::{Aead, KeyInit},
    ChaCha20Poly1305, Key, Nonce,
};
use once_cell::sync::OnceCell;
use pyo3::prelude::*;
use rand::{rng, RngCore};
use sha2::{Digest, Sha256};

const KEY_SEED: [u8; 32] = [
    0xca, 0xe5, 0xe1, 0x84, 0x98, 0xa5, 0x13, 0xf0, 0x0e, 0x22, 0x24, 0x55, 0x4c, 0xfc, 0xb4, 0x50,
    0xf2, 0x4b, 0x66, 0x14, 0x5d, 0xb7, 0xcd, 0x9d, 0xe0, 0x17, 0xf2, 0x9a, 0xc9, 0x47, 0x4d, 0x5d,
];
static DERIVED_KEY: OnceCell<[u8; 32]> = OnceCell::new();

#[derive(Clone, Copy)]
pub enum ModuleKeySource<'a> {
    LauncherHash(&'a str),
    Direct([u8; 32]),
    DefaultSeed,
}

fn cipher_from_key(key_material: &[u8]) -> Result<ChaCha20Poly1305> {
    if key_material.len() != 32 {
        return Err(anyhow!("module key must be 32 bytes"));
    }
    Ok(ChaCha20Poly1305::new(Key::from_slice(key_material)))
}

fn seal_with_key(key_material: &[u8], plaintext: &[u8]) -> Result<Vec<u8>> {
    let cipher = cipher_from_key(key_material)?;
    let mut nonce = [0u8; 12];
    let mut rng = rng();
    rng.fill_bytes(&mut nonce);
    let ct = cipher
        .encrypt(Nonce::from_slice(&nonce), plaintext)
        .context("encrypt protected payload")?;
    let mut out = nonce.to_vec();
    out.extend_from_slice(&ct);
    Ok(out)
}

fn open_with_key(key_material: &[u8], nonce_and_ct: &[u8]) -> Result<Vec<u8>> {
    if nonce_and_ct.len() <= 12 {
        return Err(anyhow!("ciphertext missing nonce prefix"));
    }
    let (nonce_bytes, ct) = nonce_and_ct.split_at(12);
    let cipher = cipher_from_key(key_material)?;
    cipher
        .decrypt(Nonce::from_slice(nonce_bytes), ct)
        .context("decrypt protected payload")
}

pub fn encrypt_data(data: &[u8]) -> Result<Vec<u8>> {
    let key = module_key()?;
    seal_with_key(key, data)
}

pub fn decrypt_data(payload: &[u8]) -> Result<Vec<u8>> {
    let key = module_key()?;
    open_with_key(key, payload)
}

pub fn initialize_module_key(source: ModuleKeySource<'_>) -> Result<()> {
    DERIVED_KEY.get_or_try_init(|| match source {
        ModuleKeySource::LauncherHash(value) => derive_key_material(value),
        ModuleKeySource::Direct(bytes) => Ok(bytes),
        ModuleKeySource::DefaultSeed => Ok(KEY_SEED),
    })?;
    Ok(())
}

fn derive_key_material(hash_hex: &str) -> Result<[u8; 32]> {
    let normalized = hash_hex.trim();
    let bytes = hex::decode(normalized)
        .map_err(|err| anyhow!("invalid launcher hash {normalized}: {err}"))?;
    if bytes.len() != 32 {
        return Err(anyhow!(
            "launcher hash must decode to 32 bytes, got {} bytes",
            bytes.len()
        ));
    }
    let mut hasher = Sha256::new();
    hasher.update(&KEY_SEED);
    hasher.update(&bytes);
    let digest = hasher.finalize();
    let mut derived = [0u8; 32];
    derived.copy_from_slice(&digest[..32]);
    Ok(derived)
}

fn module_key() -> Result<&'static [u8; 32]> {
    DERIVED_KEY
        .get()
        .ok_or_else(|| anyhow!("module key not initialized"))
}

#[pyfunction]
pub(crate) fn seal(key_material: &[u8], plaintext: &[u8]) -> PyResult<Vec<u8>> {
    if !crate::hardened_permits("crypto::seal") {
        return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            "operation blocked by hardened guard",
        ));
    }
    seal_with_key(key_material, plaintext)
        .map_err(|err| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(err.to_string()))
}

#[pyfunction]
pub(crate) fn unseal(key_material: &[u8], nonce_and_ct: &[u8]) -> PyResult<Vec<u8>> {
    if !crate::hardened_permits("crypto::unseal") {
        return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            "operation blocked by hardened guard",
        ));
    }
    open_with_key(key_material, nonce_and_ct)
        .map_err(|err| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(err.to_string()))
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
