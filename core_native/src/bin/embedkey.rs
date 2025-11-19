use anyhow::{anyhow, bail, Context, Result};
use core_native::client_key;
use std::{env, fs, path::PathBuf};

fn main() {
    if let Err(err) = run() {
        eprintln!("embedkey: {err:?}");
        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let mut args = env::args().skip(1);
    let key_hex = args
        .next()
        .ok_or_else(|| anyhow!("missing client key hex argument (64 chars)"))?;
    let targets: Vec<PathBuf> = args.map(PathBuf::from).collect();
    if targets.is_empty() {
        bail!("no executable paths provided");
    }

    let key = decode_hex_key(&key_hex)?;
    let obfuscated = client_key::obfuscate_key(&key);
    let payload = hex::encode(obfuscated);

    for exe in targets {
        let mut image = fs::read(&exe).with_context(|| format!("read {}", exe.display()))?;
        client_key::embed_client_key_payload(&mut image, payload.as_bytes())
            .with_context(|| format!("embed key into {}", exe.display()))?;
        fs::write(&exe, &image).with_context(|| format!("write {}", exe.display()))?;
        println!("embedded client key into {}", exe.display());
    }

    Ok(())
}

fn decode_hex_key(input: &str) -> Result<[u8; 32]> {
    let trimmed = input.trim();
    if trimmed.len() != 64 {
        bail!("client key hex must be exactly 64 characters");
    }
    let bytes =
        hex::decode(trimmed).map_err(|err| anyhow!("invalid client key hex payload: {err}"))?;
    if bytes.len() != 32 {
        bail!("client key must decode to 32 bytes, got {}", bytes.len());
    }
    let mut buf = [0u8; 32];
    buf.copy_from_slice(&bytes);
    Ok(buf)
}
