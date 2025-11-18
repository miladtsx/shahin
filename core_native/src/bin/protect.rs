use anyhow::{anyhow, Context, Result};
use core_native::{crypto, integrity, protected};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

fn main() {
    if let Err(err) = run() {
        eprintln!("protect: {err:?}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let out_dir = parse_out_dir(env::args().skip(1))?;
    let source_root = Path::new(protected::SOURCE_ROOT).canonicalize()?;
    crypto::initialize_module_key(protected::expected_self_hash())?;
    for spec in protected::PROTECTED_MODULES {
        seal_payload(
            &source_root,
            out_dir.as_path(),
            spec.plaintext_path,
            spec.encrypted_name,
            spec.expected_sha256,
            spec.import_name,
        )?;
    }

    for spec in protected::PROTECTED_ASSETS {
        seal_payload(
            &source_root,
            out_dir.as_path(),
            spec.plaintext_path,
            spec.encrypted_name,
            spec.expected_sha256,
            spec.label,
        )?;
    }
    Ok(())
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
    let encrypted = crypto::encrypt_data(&plaintext)?;
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

fn parse_out_dir<I>(mut args: I) -> Result<PathBuf>
where
    I: Iterator<Item = String>,
{
    let mut out_dir: Option<PathBuf> = None;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--out" => {
                let value = args
                    .next()
                    .ok_or_else(|| anyhow!("--out requires a value"))?;
                out_dir = Some(PathBuf::from(value));
            }
            unknown => {
                return Err(anyhow!("unknown argument: {unknown}"));
            }
        }
    }
    Ok(out_dir.unwrap_or_else(|| PathBuf::from("build/protected")))
}
