#![allow(unsafe_op_in_unsafe_fn)]

mod crypto;
mod hwid;
mod integrity;
mod licensing;

static LIC_PUB_KEY_DER: &[u8] = include_bytes!("../../.keys/licencing_public.pem");
#[allow(dead_code)]
static INT_PUB_KEY_DER: &[u8] = include_bytes!("../../.keys/integrity_public.pem");

pub use hwid::{HwidCollector, HwidCollectorFactory, collect_hwid_signals};
use pyo3::prelude::*;

pub fn hwid_signals() -> Vec<String> {
    collect_hwid_signals()
}

#[allow(dead_code)]
fn k_of_n_match(stored_hashes: &[Vec<u8>], current_signals: &[String], k: usize) -> bool {
    let mut matches = 0;
    for sig in current_signals {
        let h = ring::digest::digest(&ring::digest::SHA256, sig.as_bytes());
        if stored_hashes.iter().any(|s| s.as_slice() == h.as_ref()) {
            matches += 1;
            if matches >= k {
                return true;
            }
        }
    }
    false
}

#[pyfunction]
fn derive_hwid() -> PyResult<Vec<String>> {
    Ok(hwid_signals())
}

#[pymodule]
fn core_native(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(licensing::verify_signed_blob, m)?)?;
    m.add_function(wrap_pyfunction!(derive_hwid, m)?)?;
    m.add_function(wrap_pyfunction!(crypto::seal, m)?)?;
    m.add_function(wrap_pyfunction!(crypto::unseal, m)?)?;
    m.add_function(wrap_pyfunction!(integrity::self_check, m)?)?;
    Ok(())
}

#[cfg(test)]
mod test {
    use super::*;

    #[test]
    fn public_keys_are_loaded() {
        assert!(
            !LIC_PUB_KEY_DER.is_empty(),
            "licensing public key should not be empty"
        );
        assert!(
            !INT_PUB_KEY_DER.is_empty(),
            "integrity public key should not be empty"
        );
    }
}
