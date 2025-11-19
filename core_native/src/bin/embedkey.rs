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
    let hash_hex = args
        .next()
        .ok_or_else(|| anyhow!("missing launcher hash argument (64 chars)"))?;
    let targets: Vec<PathBuf> = args.map(PathBuf::from).collect();
    if targets.is_empty() {
        bail!("no executable paths provided");
    }

    let key = decode_hex_key(&key_hex)?;
    let hash = normalize_hash(&hash_hex)?;
    let fragments = client_key::scatter_fragments_for_embedding(&key, &hash)?;

    for exe in targets {
        let mut image = fs::read(&exe).with_context(|| format!("read {}", exe.display()))?;
        embed_fragments(&mut image, &fragments)
            .with_context(|| format!("embed key into {}", exe.display()))?;
        fs::write(&exe, &image).with_context(|| format!("write {}", exe.display()))?;
        println!("embedded client key into {}", exe.display());
    }

    Ok(())
}

fn embed_fragments(image: &mut [u8], fragments: &[[u8; 8]; 4]) -> Result<()> {
    let patterns = client_key::embedded_shards();
    for (idx, pattern) in patterns.iter().enumerate() {
        patch_shard(image, pattern.start, pattern.end, &fragments[idx])?;
    }
    Ok(())
}

fn patch_shard(bytes: &mut [u8], start: &[u8], end: &[u8], payload: &[u8]) -> Result<()> {
    let mut cursor = 0usize;
    while cursor < bytes.len() {
        let Some(rel_start) = locate(&bytes[cursor..], start) else {
            break;
        };
        let payload_start = cursor + rel_start + start.len();
        let Some(rel_end) = locate(&bytes[payload_start..], end) else {
            return Err(anyhow!("shard end marker missing"));
        };
        let payload_end = payload_start + rel_end;
        if payload_end - payload_start == payload.len() {
            bytes[payload_start..payload_end].copy_from_slice(payload);
            return Ok(());
        }
        cursor = payload_start + rel_end;
    }
    Err(anyhow!("shard markers not found in image"))
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

fn normalize_hash(input: &str) -> Result<String> {
    let trimmed = input.trim().to_ascii_lowercase();
    if trimmed.len() != 64 {
        bail!("launcher hash must be exactly 64 hex characters");
    }
    if !trimmed.chars().all(|c| c.is_ascii_hexdigit()) {
        bail!("launcher hash must be hexadecimal");
    }
    Ok(trimmed)
}

fn locate(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    if haystack.len() < needle.len() {
        return None;
    }
    haystack
        .windows(needle.len())
        .position(|window| constant_time_eq(window, needle))
}

fn constant_time_eq(lhs: &[u8], rhs: &[u8]) -> bool {
    if lhs.len() != rhs.len() {
        return false;
    }
    lhs.iter()
        .zip(rhs.iter())
        .fold(0u8, |acc, (&l, &r)| acc | (l ^ r))
        == 0
}
