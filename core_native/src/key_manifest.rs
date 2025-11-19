use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

pub const MANIFEST_FILE: &str = "key_manifest.json";
const FORMAT_VERSION: u32 = 1;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct KeyManifest {
    pub version: u32,
    pub encryption: EncryptionMode,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "mode", rename_all = "kebab-case")]
pub enum EncryptionMode {
    LauncherHash,
    ClientKey {
        #[serde(skip_serializing_if = "Option::is_none")]
        key_id: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        key_hint: Option<String>,
    },
}

impl KeyManifest {
    pub fn launcher_hash() -> Self {
        Self {
            version: FORMAT_VERSION,
            encryption: EncryptionMode::LauncherHash,
        }
    }

    pub fn client_key(key_id: Option<String>, key_hint: Option<String>) -> Self {
        Self {
            version: FORMAT_VERSION,
            encryption: EncryptionMode::ClientKey { key_id, key_hint },
        }
    }
}

pub fn manifest_path(root: &Path) -> PathBuf {
    root.join(MANIFEST_FILE)
}

pub fn write_manifest(root: &Path, manifest: &KeyManifest) -> Result<()> {
    fs::create_dir_all(root)
        .with_context(|| format!("create manifest dir {}", root.to_string_lossy()))?;
    let path = manifest_path(root);
    let data = serde_json::to_vec_pretty(manifest).context("serialize key manifest")?;
    fs::write(&path, &data)
        .with_context(|| format!("write {}", path.to_string_lossy()))?;
    Ok(())
}

pub fn read_manifest(root: &Path) -> Result<Option<KeyManifest>> {
    let path = manifest_path(root);
    if !path.exists() {
        return Ok(None);
    }
    let bytes = fs::read(&path).with_context(|| format!("read {}", path.to_string_lossy()))?;
    let manifest =
        serde_json::from_slice::<KeyManifest>(&bytes).context("parse key manifest json")?;
    Ok(Some(manifest))
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn round_trip_launcher_manifest() {
        let dir = tempdir().expect("tmpdir");
        let manifest = KeyManifest::launcher_hash();
        write_manifest(dir.path(), &manifest).expect("write");
        let loaded = read_manifest(dir.path()).expect("read").expect("manifest");
        assert_eq!(manifest, loaded);
    }

    #[test]
    fn round_trip_client_manifest() {
        let dir = tempdir().expect("tmpdir");
        let manifest = KeyManifest::client_key(
            Some("client-a".into()),
            Some("abc123".into()),
        );
        write_manifest(dir.path(), &manifest).expect("write");
        let loaded = read_manifest(dir.path()).expect("read").expect("manifest");
        assert_eq!(manifest, loaded);
    }
}
