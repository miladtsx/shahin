#![allow(unsafe_op_in_unsafe_fn)]

pub mod crypto;
#[cfg(feature = "hardened")]
mod hardened;
mod hwid;
pub mod integrity;
mod licensing;
#[cfg(target_os = "windows")]
mod markers;
pub mod protected;
pub mod selfhash;

pub(crate) static LIC_PUB_KEY_DER: &[u8] = include_bytes!("../.keys/licensing_public.der");
#[allow(dead_code)]
static INT_PUB_KEY_DER: &[u8] = include_bytes!("../.keys/integrity_public.der");

pub use hwid::{collect_hwid_signals, HwidCollector, HwidCollectorFactory};
use pyo3::prelude::*;
use ring::digest::{self, Context};
use std::fs;
use std::path::Path;

pub fn hwid_signals() -> Vec<String> {
    if !hardened_permits("hwid_signals") {
        return Vec::new();
    }
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
    if !hardened_permits("derive_hwid") {
        return Ok(Vec::new());
    }
    Ok(hwid_signals())
}

#[pyfunction]
fn verify_file_hash(path: &str, expected_hex: &str) -> PyResult<bool> {
    if !hardened_permits("verify_file_hash") {
        return Ok(false);
    }
    let expected = expected_hex.trim();
    if expected.is_empty() {
        return Ok(false);
    }
    let data = fs::read(Path::new(path))
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("read {path}: {e}")))?;
    let actual = sha256_hex(&data);
    Ok(actual.eq_ignore_ascii_case(expected))
}

#[pyfunction]
fn get_machine_fingerprint() -> PyResult<String> {
    if !hardened_permits("get_machine_fingerprint") {
        return Ok(debug_blocked_fingerprint());
    }
    let signals = hwid_signals();
    let fingerprint = fingerprint_from_signals(&signals).ok_or_else(|| {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("no hardware signals available")
    })?;
    Ok(fingerprint)
}

fn fingerprint_from_signals(signals: &[String]) -> Option<String> {
    if !hardened_permits("fingerprint_from_signals") {
        return None;
    }
    if signals.is_empty() {
        return None;
    }
    let mut ctx = Context::new(&digest::SHA256);
    for sig in signals {
        ctx.update(sig.as_bytes());
        ctx.update(&[0u8]); // delimiter to reduce collisions
    }
    Some(to_lower_hex(ctx.finish().as_ref()))
}

pub(crate) fn sha256_hex(bytes: &[u8]) -> String {
    let digest = digest::digest(&digest::SHA256, bytes);
    to_lower_hex(digest.as_ref())
}

fn to_lower_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push(HEX[(byte >> 4) as usize] as char);
        out.push(HEX[(byte & 0x0f) as usize] as char);
    }
    out
}

#[pymodule(name = "core_native")]
pub fn core_native_py(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(licensing::verify_signed_blob, m)?)?;
    m.add_function(wrap_pyfunction!(licensing::sign_license_payload, m)?)?;
    m.add_function(wrap_pyfunction!(derive_hwid, m)?)?;
    m.add_function(wrap_pyfunction!(crypto::seal, m)?)?;
    m.add_function(wrap_pyfunction!(crypto::unseal, m)?)?;
    m.add_function(wrap_pyfunction!(integrity::self_check, m)?)?;
    m.add_function(wrap_pyfunction!(integrity::calculate_file_sha256, m)?)?;
    m.add_function(wrap_pyfunction!(integrity::calculate_bytes_sha256, m)?)?;
    m.add_function(wrap_pyfunction!(verify_file_hash, m)?)?;
    m.add_function(wrap_pyfunction!(get_machine_fingerprint, m)?)?;
    Ok(())
}

#[inline]
pub(crate) fn hardened_permits(label: &str) -> bool {
    #[cfg(feature = "hardened")]
    {
        return hardened::guard_operation(label);
    }
    #[cfg(not(feature = "hardened"))]
    {
        let _ = label;
        return true;
    }
}

fn debug_blocked_fingerprint() -> String {
    "debugger-blocked".to_string()
}

#[cfg(test)]
mod test {
    use super::*;
    use std::env;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[cfg(feature = "hardened")]
    use crate::hardened;

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

    #[test]
    fn verify_file_hash_matches_content() {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("duration")
            .as_nanos();
        let path = env::temp_dir().join(format!("core_native_hash_{unique}.txt"));
        fs::write(&path, b"hello world").expect("write");
        let expected = sha256_hex(b"hello world");
        let path_str = path.to_str().expect("path str");
        assert!(verify_file_hash(path_str, &expected).unwrap());
        assert!(!verify_file_hash(path_str, "deadbeef").unwrap());
        let _ = fs::remove_file(path);
    }

    #[test]
    fn fingerprint_from_signals_is_deterministic() {
        let signals = vec!["alpha".into(), "beta".into()];
        let fp1 = fingerprint_from_signals(&signals).expect("fp1");
        let fp2 = fingerprint_from_signals(&signals).expect("fp2");
        assert_eq!(fp1, fp2);
    }

    #[cfg(not(feature = "hardened"))]
    #[test]
    fn hardened_guard_is_noop_without_feature() {
        assert!(hardened_permits("test_gate"));
    }

    #[cfg(feature = "hardened")]
    #[test]
    fn hardened_beacon_smoke_test() {
        assert!(hardened_permits("smoke_beacon"));
    }

    #[cfg(feature = "hardened")]
    #[test]
    fn hardened_beacon_blocks_after_trip() {
        let engine = hardened::beacon::global();
        engine.force_trip();
        assert!(!hardened_permits("trip_block"));
        engine.reset();
    }
}
