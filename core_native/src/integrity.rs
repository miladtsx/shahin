use base64::engine::general_purpose::STANDARD;
use base64::Engine as _;
use object::{Object, ObjectSection};
use pyo3::prelude::*;
use ring::signature;
use serde::Deserialize;
use std::path::PathBuf;

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
    Ok(default_self_check(py).unwrap_or(false))
}

fn default_self_check(py: Python<'_>) -> Option<bool> {
    let (manifest_json, manifest_sig_b64) = embedded_manifest()?;
    let manifest_json = manifest_json.trim();
    let manifest_sig_b64 = manifest_sig_b64.trim();
    if manifest_json.is_empty() || manifest_sig_b64.is_empty() {
        return Some(false);
    }

    let signature = match STANDARD.decode(manifest_sig_b64) {
        Ok(sig) => sig,
        Err(_) => return Some(false),
    };

    let module_path = module_library_path(py)?;
    let module_bytes = std::fs::read(module_path).ok()?;

    Some(run_self_check_with(
        manifest_json,
        &signature,
        &module_bytes,
        super::INT_PUB_KEY_DER,
    ))
}

pub(crate) fn run_self_check_with(
    manifest_json: &str,
    manifest_sig: &[u8],
    module_bytes: &[u8],
    public_key_der: &[u8],
) -> bool {
    if manifest_json.trim().is_empty() || manifest_sig.is_empty() {
        return false;
    }

    if !verify_manifest_signature_with_key(manifest_json.as_bytes(), manifest_sig, public_key_der) {
        return false;
    }

    let manifest: IntegrityManifest = match serde_json::from_str(manifest_json) {
        Ok(m) => m,
        Err(_) => return false,
    };

    let expected_hash = match manifest.expected_hash() {
        Some(hash) if !hash.trim().is_empty() => hash.trim(),
        _ => return false,
    };

    let actual_hash = match text_section_sha256_hex(module_bytes) {
        Some(hash) => hash,
        None => return false,
    };

    actual_hash.eq_ignore_ascii_case(expected_hash)
}

fn embedded_manifest() -> Option<(&'static str, &'static str)> {
    let json = option_env!("CORE_NATIVE_INTEGRITY_MANIFEST_JSON")?;
    let sig = option_env!("CORE_NATIVE_INTEGRITY_MANIFEST_SIG_B64")?;
    Some((json, sig))
}

fn verify_manifest_signature_with_key(
    manifest: &[u8],
    signature_bytes: &[u8],
    public_key_der: &[u8],
) -> bool {
    let pk = signature::UnparsedPublicKey::new(
        &signature::ECDSA_P256_SHA256_ASN1,
        public_key_der.to_vec(),
    );
    pk.verify(manifest, signature_bytes).is_ok()
}

fn module_library_path(py: Python<'_>) -> Option<PathBuf> {
    let module = py.import_bound("core_native").ok()?;
    let file_attr = module.getattr("__file__").ok()?;
    let file: String = file_attr.extract().ok()?;
    Some(file.into())
}

pub(crate) fn text_section_sha256_hex(module_bytes: &[u8]) -> Option<String> {
    let file = object::File::parse(module_bytes).ok()?;
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

#[cfg(test)]
mod tests {
    use super::*;
    use object::write::{Object as WriteObject, StandardSection, Symbol, SymbolSection};
    use object::{Architecture, BinaryFormat, Endianness, SymbolFlags, SymbolKind, SymbolScope};
    use ring::{rand::SystemRandom, signature, signature::KeyPair};

    fn build_test_object(text: &[u8]) -> Vec<u8> {
        let mut obj = WriteObject::new(BinaryFormat::Elf, Architecture::X86_64, Endianness::Little);
        let section_id = obj.section_id(StandardSection::Text);
        obj.append_section_data(section_id, text, 1);
        let symbol = Symbol {
            name: b"_start".to_vec(),
            value: 0,
            size: text.len() as u64,
            kind: SymbolKind::Text,
            scope: SymbolScope::Linkage,
            weak: false,
            section: SymbolSection::Section(section_id),
            flags: SymbolFlags::None,
        };
        obj.add_symbol(symbol);
        obj.write().expect("serialize object")
    }

    fn sign_manifest(manifest_json: &str, key_pair: &signature::EcdsaKeyPair) -> Vec<u8> {
        let rng = SystemRandom::new();
        key_pair
            .sign(&rng, manifest_json.as_bytes())
            .expect("sign manifest")
            .as_ref()
            .to_vec()
    }

    #[test]
    fn run_self_check_with_passes_for_matching_manifest_and_binary() {
        let text = b"fn main() { 42 }";
        let module_bytes = build_test_object(text);
        let expected_hash = text_section_sha256_hex(&module_bytes).expect("hash");
        let manifest_json =
            serde_json::json!({ "text_section_sha256": expected_hash, "timestamp": "2025-01-01T00:00:00Z" })
                .to_string();

        let rng = SystemRandom::new();
        let pkcs8 = signature::EcdsaKeyPair::generate_pkcs8(
            &signature::ECDSA_P256_SHA256_ASN1_SIGNING,
            &rng,
        )
        .expect("generate key");
        let key_pair = signature::EcdsaKeyPair::from_pkcs8(
            &signature::ECDSA_P256_SHA256_ASN1_SIGNING,
            pkcs8.as_ref(),
            &rng,
        )
        .expect("parse key");
        let sig = sign_manifest(&manifest_json, &key_pair);

        assert!(run_self_check_with(
            &manifest_json,
            &sig,
            &module_bytes,
            key_pair.public_key().as_ref()
        ));
    }

    #[test]
    fn run_self_check_with_fails_on_hash_mismatch() {
        let text = b"fn main() { 42 }";
        let module_bytes = build_test_object(text);
        let manifest_json =
            serde_json::json!({ "text_section_sha256": "deadbeef", "timestamp": "2025-01-01T00:00:00Z" })
                .to_string();

        let rng = SystemRandom::new();
        let pkcs8 = signature::EcdsaKeyPair::generate_pkcs8(
            &signature::ECDSA_P256_SHA256_ASN1_SIGNING,
            &rng,
        )
        .expect("generate key");
        let key_pair = signature::EcdsaKeyPair::from_pkcs8(
            &signature::ECDSA_P256_SHA256_ASN1_SIGNING,
            pkcs8.as_ref(),
            &rng,
        )
        .expect("parse key");
        let sig = sign_manifest(&manifest_json, &key_pair);

        assert!(!run_self_check_with(
            &manifest_json,
            &sig,
            &module_bytes,
            key_pair.public_key().as_ref()
        ));
    }

    #[test]
    fn run_self_check_with_fails_on_bad_signature() {
        let text = b"fn main() { 42 }";
        let module_bytes = build_test_object(text);
        let expected_hash = text_section_sha256_hex(&module_bytes).expect("hash");
        let manifest_json =
            serde_json::json!({ "text_section_sha256": expected_hash, "timestamp": "2025-01-01T00:00:00Z" })
                .to_string();

        let rng = SystemRandom::new();
        let pkcs8_a = signature::EcdsaKeyPair::generate_pkcs8(
            &signature::ECDSA_P256_SHA256_ASN1_SIGNING,
            &rng,
        )
        .expect("generate key a");
        let key_pair_a = signature::EcdsaKeyPair::from_pkcs8(
            &signature::ECDSA_P256_SHA256_ASN1_SIGNING,
            pkcs8_a.as_ref(),
            &rng,
        )
        .expect("parse key a");
        let pkcs8_b = signature::EcdsaKeyPair::generate_pkcs8(
            &signature::ECDSA_P256_SHA256_ASN1_SIGNING,
            &rng,
        )
        .expect("generate key b");
        let key_pair_b = signature::EcdsaKeyPair::from_pkcs8(
            &signature::ECDSA_P256_SHA256_ASN1_SIGNING,
            pkcs8_b.as_ref(),
            &rng,
        )
        .expect("parse key b");
        let sig = sign_manifest(&manifest_json, &key_pair_a);

        assert!(!run_self_check_with(
            &manifest_json,
            &sig,
            &module_bytes,
            key_pair_b.public_key().as_ref()
        ));
    }
}
