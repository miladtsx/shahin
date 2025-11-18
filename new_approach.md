Below is a Windows-only approach that makes the scrub region unambiguous by putting it in a dedicated PE section, then locating it by section name (and optionally symbol range). This removes the risk of accidentally matching marker bytes elsewhere in the binary.

# 1) Place the hash payload in a dedicated PE section

Use MSVC-style section naming. PE section names are limited to 8 bytes, so use something short, e.g. `.shn`. For deterministic layout and easy range selection, leverage the `$` suffix ordering convention: the linker merges `.shn$A`, `.shn$M`, `.shn$Z` (lexicographic) into one final `.shn` section, ordered A → M → Z.

```rust
// src/markers.rs (Windows-only)
#![cfg(target_os = "windows")]

#[link_section = ".shn$A"]
#[used] // keep even if "unused"
pub static SHN_START_MAGIC: [u8; 16] = *b"SHAHIN\0START\0\0";

/// This is the only region that may change without affecting the final hash.
/// You can patch it post-link, or embed the current self-hash here.
#[link_section = ".shn$M"]
#[used]
#[no_mangle] // optional: keeps a stable symbol name for this object
pub static mut SHN_SELF_HASH_PAYLOAD: [u8; 64] = [0u8; 64];

#[link_section = ".shn$Z"]
#[used]
pub static SHN_END_MAGIC: [u8; 16] = *b"SHAHIN\0END\0\0\0";
```

Make the section read-only at link time:

```rust
// build.rs
fn main() {
    // Ensure the custom section is readable (R), not executable or writable.
    // MSVC/LLD on Windows accepts /SECTION:.name,flags
    println!("cargo:rustc-link-arg=/SECTION:.shn,R");
    // If you also want it excluded from the image at runtime (not typical), you could add /MERGE etc.
}
```

Notes

* The `$` suffixes ensure the three blocks end up adjacent in `.shn` in the right order, even with LTO and dead-code elimination.
* `#[used]` prevents the linker from dropping these objects.
* If you want to patch the payload after link, you have a stable, bounded location to edit without searching the whole file.

# 2) Locate and scrub by section, not by global byte search

Use `goblin` to parse PE and find `.shn`. Compute the subrange (payload only) by subtracting the A/Z sentinels from the section’s contents.

```toml
# Cargo.toml
[dependencies]
goblin = { version = "0.9", default-features = false, features = ["pe32"] }
sha2 = "0.10"
hex = "0.4"
anyhow = "1"
```

```rust
// src/integrity_windows.rs
#![cfg(target_os = "windows")]

use anyhow::{anyhow, Context, Result};
use goblin::pe::PE;
use sha2::{Digest, Sha256};
use std::{fs, path::Path};

const START_LEN: usize = 16;
const END_LEN: usize = 16;
const PAYLOAD_SECTION: &str = ".shn";

pub fn sanitized_hash_of_file(path: &Path) -> Result<String> {
    let mut data = fs::read(path).with_context(|| format!("read {}", path.display()))?;
    scrub_shahin_section(&mut data)?;
    Ok(obfuscated_digest(&data))
}

/// Zero only the payload subrange inside the dedicated `.shn` section:
/// [.shn$A (16 bytes)] [payload ...] [.shn$Z (16 bytes)]
fn scrub_shahin_section(bytes: &mut [u8]) -> Result<()> {
    let pe = PE::parse(bytes).context("parse PE")?;

    // Find section header for ".shn"
    let sect = pe
        .sections
        .iter()
        .find(|s| s.name().unwrap_or_default() == PAYLOAD_SECTION)
        .ok_or_else(|| anyhow!("section {PAYLOAD_SECTION} not found"))?;

    let file_off = sect.pointer_to_raw_data as usize;
    let raw_size = sect.size_of_raw_data as usize;

    if file_off == 0 || raw_size == 0 || file_off + raw_size > bytes.len() {
        return Err(anyhow!("invalid {PAYLOAD_SECTION} file mapping"));
    }

    // The section contains: start magic (16) + payload + end magic (16).
    if raw_size < START_LEN + END_LEN {
        return Err(anyhow!("{} too small for sentinels", PAYLOAD_SECTION));
    }
    let payload_off = file_off + START_LEN;
    let payload_end = file_off + raw_size - END_LEN;

    // Zero only the payload (allowed to vary). Leave sentinels intact.
    for b in &mut bytes[payload_off..payload_end] {
        *b = 0;
    }
    Ok(())
}

fn obfuscated_digest(all: &[u8]) -> String {
    let mid = all.len() / 2;
    let (first, second) = all.split_at(mid);
    let mut l = Sha256::new();
    l.update(first);
    let mut r = Sha256::new();
    r.update(second);
    let mut final_hasher = Sha256::new();
    final_hasher.update(l.finalize());
    final_hasher.update(r.finalize());
    hex::encode(final_hasher.finalize())
}
```

If you prefer not to rely on sentinel sizes, you can export symbol addresses and compute the exact payload range via symbol RVAs, but for release builds data exports are trickier. The `$` layout plus fixed sentinel lengths keeps it simple and stable.

# 3) Optional: symbol-based range (when exporting is acceptable)

If you want to compute the payload bounds using symbol names rather than lengths, export the sentinels:

```rust
// markers.rs additions
#[no_mangle]
#[link_section = ".shn$A"]
#[used]
pub static SHAHIN_SECTION_BEGIN: u8 = 0;

#[no_mangle]
#[link_section = ".shn$Z"]
#[used]
pub static SHAHIN_SECTION_END: u8 = 0;
```

Then in `build.rs`, force them to be exported:

```rust
println!("cargo:rustc-link-arg=/INCLUDE:SHAHIN_SECTION_BEGIN");
println!("cargo:rustc-link-arg=/INCLUDE:SHAHIN_SECTION_END");
```

At scrub time, parse the PE export directory with `goblin` to resolve RVAs of those symbols to file offsets, and zero the range between them. This avoids hard-coding 16-byte sentinel sizes, at the cost of exposing symbol names (often fine).

# 4) Tests that lock the behavior

Unit tests for the PE scrubber should be integration-style: build a tiny Windows test binary containing the section, mutate only the payload, and assert the sanitized hash stays the same; mutate outside and assert the hash changes.

Skeleton:

```rust
// tests/pe_scrub.rs  (runs only on Windows CI/host)
#![cfg(target_os = "windows")]

use std::{fs, path::PathBuf, process::Command};

fn build_fixture() -> PathBuf {
    // Build a tiny crate in tests/fixtures/app with the markers.rs module.
    let status = Command::new("cargo")
        .args(["build", "--release", "--manifest-path", "tests/fixtures/app/Cargo.toml"])
        .status()
        .unwrap();
    assert!(status.success());
    // target\release\app.exe
    ["tests","fixtures","app","target","release","app.exe"].iter().collect()
}

#[test]
fn in_section_mutations_do_not_change_sanitized_hash() {
    let exe = build_fixture();
    let buf = fs::read(&exe).unwrap();

    let h1 = sanitized_hash_of_file(&exe).unwrap();

    // Locate .shn section and flip payload bytes
    let mut mutated = buf.clone();
    scrub_shahin_section(&mut mutated).unwrap(); // zero now to learn bounds
    // Undo zeroing but flip to other values in the same range to simulate "changed payload"
    // …or directly compute payload range like in the library and modify it here…

    let tmp = tempfile::NamedTempFile::new().unwrap();
    fs::write(tmp.path(), &mutated).unwrap();

    let h2 = sanitized_hash_of_file(tmp.path()).unwrap();
    assert_eq!(h1, h2);
}

#[test]
fn out_of_section_mutations_change_sanitized_hash() {
    let exe = build_fixture();
    let mut buf = fs::read(&exe).unwrap();
    let h1 = sanitized_hash_of_file(&exe).unwrap();

    // Flip a byte in .text (e.g., at offset 0x200) that is not inside .shn
    buf[0x200] ^= 0x01;

    let tmp = tempfile::NamedTempFile::new().unwrap();
    fs::write(tmp.path(), &buf).unwrap();

    let h2 = sanitized_hash_of_file(tmp.path()).unwrap();
    assert_ne!(h1, h2);
}
```

Tips

* Put the minimal fixture app under `tests/fixtures/app` with the same `markers.rs` and `build.rs` shown above.
* Pin the `.shn` section contents in a golden test (e.g., assert `raw_size >= 16+64+16`) to detect toolchain changes.

# 5) Why this is safer and more deterministic

* No global byte scanning: the scrubber never touches unrelated bytes, so it can’t accidentally “clean” a coincidental marker sequence embedded in code/data.
* Stable layout: `$`-ordered subsections give you a contiguous, well-defined region regardless of LTO, COMDAT folding, or dead-stripping.
* Windows-native: `/SECTION:.shn,R` makes the intent explicit to the PE loader and other tools.

# 6) Hardening options

* Add `/INCREMENTAL:NO /OPT:REF,ICF` to make layout more deterministic across builds.
* Consider `/MERGE:.rdata=.text` if you must reduce section count, but keep `.shn` separate for clarity.
* If you patch the payload post-link, do it via file offset computed from `.shn` rather than by searching for magic bytes.

This gives you a Windows-only, section-scoped scrub that pairs cleanly with your “sanitized hash” and is straightforward to test in CI.
