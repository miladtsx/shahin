#[cfg(not(target_os = "windows"))]
fn main() {
    eprintln!("embedhash is only available on Windows targets");
    std::process::exit(1);
}

#[cfg(target_os = "windows")]
fn main() {
    if let Err(err) = real_main() {
        eprintln!("embedhash: {err:?}");
        std::process::exit(1);
    }
}

#[cfg(target_os = "windows")]
fn real_main() -> anyhow::Result<()> {
    use anyhow::{anyhow, bail, Context};
    use std::env;
    use std::fs;
    use std::path::PathBuf;

    let mut args = env::args().skip(1);
    let hash_arg = args
        .next()
        .ok_or_else(|| anyhow!("missing hash argument (expected 64 hex chars)"))?;
    let targets: Vec<PathBuf> = args.map(PathBuf::from).collect();
    if targets.is_empty() {
        bail!("no executable paths provided");
    }

    let hash = hash_arg.trim().to_ascii_lowercase();
    if hash.len() != 64 || !hash.chars().all(|c| c.is_ascii_hexdigit()) {
        bail!("hash must be exactly 64 hexadecimal characters");
    }
    let hash_bytes = hash.into_bytes();

    for exe in targets {
        let mut image = fs::read(&exe).with_context(|| format!("read {}", exe.display()))?;
        core_native::selfhash::embed_shn_payload(&mut image, &hash_bytes)
            .with_context(|| format!("mutate {}", exe.display()))?;
        fs::write(&exe, &image).with_context(|| format!("write {}", exe.display()))?;
        println!("embedded hash into {}", exe.display());
    }

    Ok(())
}
