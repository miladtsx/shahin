use anyhow::{anyhow, Context, Result};
use core_native::{client_key, crypto, integrity, key_manifest, protected};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use core_native::crypto::ModuleKeySource;

fn main() {
    if let Err(err) = run() {
        eprintln!("protect: {err:?}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let options = parse_args(env::args().skip(1))?;
    let source_root = Path::new(protected::SOURCE_ROOT).canonicalize()?;
    fs::create_dir_all(&options.out_dir)
        .with_context(|| format!("create {}", options.out_dir.display()))?;
    let manifest = configure_module_key(options.client_key.as_ref())?;

    for spec in protected::PROTECTED_MODULES {
        seal_payload(
            &source_root,
            options.out_dir.as_path(),
            spec.plaintext_path,
            spec.encrypted_name,
            spec.expected_sha256,
            spec.import_name,
        )?;
    }

    for spec in protected::PROTECTED_ASSETS {
        seal_payload(
            &source_root,
            options.out_dir.as_path(),
            spec.plaintext_path,
            spec.encrypted_name,
            spec.expected_sha256,
            spec.label,
        )?;
    }
    key_manifest::write_manifest(&options.out_dir, &manifest)?;
    Ok(())
}

fn configure_module_key(client_key: Option<&ClientKeyInput>) -> Result<key_manifest::KeyManifest> {
    if let Some(key) = client_key {
        let finalized = client_key::finalize_key_material(&key.bytes, &key.client_id);
        crypto::initialize_module_key(ModuleKeySource::Direct(finalized))?;
        let hint = integrity::sha256_of_bytes(&finalized);
        return Ok(key_manifest::KeyManifest::client_key(
            Some(key.client_id.clone()),
            Some(hint),
        ));
    }

    let manifest = if let Some(expected) = protected::expected_self_hash() {
        crypto::initialize_module_key(ModuleKeySource::LauncherHash(expected))?;
        key_manifest::KeyManifest::launcher_hash()
    } else {
        crypto::initialize_module_key(ModuleKeySource::DefaultSeed)?;
        key_manifest::KeyManifest::launcher_hash()
    };
    Ok(manifest)
}

fn seal_payload(
    source_root: &Path,
    out_dir: &Path,
    plaintext_relative: &str,
    encrypted_relative: &str,
    expected_hash: &str,
    label: &str,
) -> Result<()> {
    let plaintext_path = source_root.join(plaintext_relative);
    let plaintext = fs::read(&plaintext_path)
        .with_context(|| format!("read plaintext {}", plaintext_path.to_string_lossy()))?;
    let digest = integrity::sha256_of_bytes(&plaintext);
    if !digest.eq_ignore_ascii_case(expected_hash) {
        return Err(anyhow!(
            "hash mismatch for {} (expected {}, got {})",
            label,
            expected_hash,
            digest
        ));
    }
    let encrypted = crypto::encrypt_scoped(&plaintext, label)?;
    let target_path = out_dir.join(encrypted_relative);
    if let Some(parent) = target_path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("create {}", parent.to_string_lossy()))?;
    }
    fs::write(&target_path, &encrypted)
        .with_context(|| format!("write {}", target_path.to_string_lossy()))?;
    println!(
        "sealed {} -> {} ({} bytes)",
        label,
        target_path.to_string_lossy(),
        encrypted.len()
    );
    Ok(())
}

struct ProtectOptions {
    out_dir: PathBuf,
    client_key: Option<ClientKeyInput>,
}

#[derive(Clone)]
struct ClientKeyInput {
    bytes: [u8; 32],
    client_id: String,
}

fn parse_args<I>(mut args: I) -> Result<ProtectOptions>
where
    I: Iterator<Item = String>,
{
    let mut out_dir: Option<PathBuf> = None;
    let mut client_key_bytes: Option<[u8; 32]> = None;
    let mut client_id: Option<String> = None;

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--out" => {
                let value = args
                    .next()
                    .ok_or_else(|| anyhow!("--out requires a value"))?;
                out_dir = Some(PathBuf::from(value));
            }
            "--client-key" => {
                let value = args
                    .next()
                    .ok_or_else(|| anyhow!("--client-key requires a value"))?;
                if client_key_bytes.is_some() {
                    return Err(anyhow!("--client-key specified multiple times"));
                }
                client_key_bytes = Some(decode_hex_key(&value)?);
            }
            "--client-id" => {
                let value = args
                    .next()
                    .ok_or_else(|| anyhow!("--client-id requires a value"))?;
                let trimmed = value.trim().to_string();
                if trimmed.is_empty() {
                    return Err(anyhow!("--client-id cannot be empty"));
                }
                client_id = Some(trimmed);
            }
            unknown => {
                return Err(anyhow!("unknown argument: {unknown}"));
            }
        }
    }

    if (client_key_bytes.is_some() && client_id.is_none())
        || (client_id.is_some() && client_key_bytes.is_none())
    {
        return Err(anyhow!("--client-key and --client-id must be provided together"));
    }

    let client_key = client_key_bytes.map(|bytes| ClientKeyInput {
        bytes,
        client_id: client_id.expect("client id present with key"),
    });

    Ok(ProtectOptions {
        out_dir: out_dir.unwrap_or_else(|| PathBuf::from("build/protected")),
        client_key,
    })
}

fn decode_hex_key(input: &str) -> Result<[u8; 32]> {
    let normalized = input.trim();
    let bytes = hex::decode(normalized)
        .map_err(|err| anyhow!("invalid hex key material: {err}"))?;
    if bytes.len() != 32 {
        return Err(anyhow!(
            "client key must decode to 32 bytes, got {} bytes",
            bytes.len()
        ));
    }
    let mut exact = [0u8; 32];
    exact.copy_from_slice(&bytes);
    Ok(exact)
}
