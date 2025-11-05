use base64::Engine as _;
use base64::engine::general_purpose::STANDARD;
use object::{Object, ObjectSection};
use pyo3::prelude::*;
use ring::signature;
use serde::Deserialize;
use std::path::{Path, PathBuf};

#[derive(Deserialize)]
struct IntegrityManifest {
    #[serde(default)]
    text_section_sha256: Option<String>,
    #[serde(default)]
    text_sha256: Option<String>,
    #[serde(default)]
    exe_hash: Option<String>,
}

impl IntegrityManifest {
    fn expected_hash(&self) -> Option<&str> {
        self.text_section_sha256
            .as_deref()
            .or(self.text_sha256.as_deref())
            .or(self.exe_hash.as_deref())
    }
}

#[pyfunction]
pub(crate) fn self_check(py: Python<'_>) -> PyResult<bool> {
    Ok(run_self_check(py).unwrap_or(false))
}

fn run_self_check(py: Python<'_>) -> Option<bool> {
    let (manifest_json, manifest_sig_b64) = embedded_manifest()?;
    let manifest_json = manifest_json.trim();
    let manifest_sig_b64 = manifest_sig_b64.trim();
    if manifest_json.is_empty() || manifest_sig_b64.is_empty() {
        return Some(false);
    }

    let signature = STANDARD.decode(manifest_sig_b64).ok()?;
    if !verify_manifest_signature(manifest_json.as_bytes(), &signature) {
        return Some(false);
    }

    let manifest: IntegrityManifest = serde_json::from_str(manifest_json).ok()?;
    let expected_hash = manifest.expected_hash()?.trim();
    if expected_hash.is_empty() {
        return Some(false);
    }

    let module_path = module_library_path(py)?;
    let actual_hash = compute_text_section_sha256_hex(&module_path)?;

    Some(actual_hash.eq_ignore_ascii_case(expected_hash))
}

fn embedded_manifest() -> Option<(&'static str, &'static str)> {
    let json = option_env!("CORE_NATIVE_INTEGRITY_MANIFEST_JSON")?;
    let sig = option_env!("CORE_NATIVE_INTEGRITY_MANIFEST_SIG_B64")?;
    Some((json, sig))
}

fn verify_manifest_signature(manifest: &[u8], signature_bytes: &[u8]) -> bool {
    let pk = signature::UnparsedPublicKey::new(
        &signature::ECDSA_P256_SHA256_ASN1,
        super::INT_PUB_KEY_DER.to_vec(),
    );
    pk.verify(manifest, signature_bytes).is_ok()
}

fn module_library_path(py: Python<'_>) -> Option<PathBuf> {
    let module = py.import_bound("core_native").ok()?;
    let file_attr = module.getattr("__file__").ok()?;
    let file: String = file_attr.extract().ok()?;
    Some(file.into())
}

fn compute_text_section_sha256_hex(path: &Path) -> Option<String> {
    let data = std::fs::read(path).ok()?;
    let file = object::File::parse(&*data).ok()?;
    let section_names = [".text", "__text"];

    for name in &section_names {
        if let Some(section) = file.section_by_name(name) {
            let bytes = section.data().ok()?;
            let digest = ring::digest::digest(&ring::digest::SHA256, bytes.as_ref());
            return Some(to_lower_hex(digest.as_ref()));
        }
    }

    None
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
