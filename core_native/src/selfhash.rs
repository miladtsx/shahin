use crate::integrity;
#[cfg(target_os = "windows")]
use crate::markers;
#[cfg(not(target_os = "windows"))]
use crate::protected;
#[cfg(target_os = "windows")]
use anyhow::bail;
use anyhow::{anyhow, Context, Result};
#[cfg(target_os = "windows")]
use goblin::pe::PE;
use sha2::{Digest, Sha256};
use std::fs;
use std::path::Path;

#[cfg(not(target_os = "windows"))]
const REGION_PAD: u8 = 0xA5;

#[cfg(target_os = "windows")]
const SHN_SECTION_NAME: &str = ".shn";

/// Windows: scrub the dedicated `.shn` section before hashing.
#[cfg(target_os = "windows")]
pub fn sanitized_hash_of_file(path: &Path) -> Result<String> {
    let data = fs::read(path).with_context(|| format!("read {}", path.display()))?;
    let mut scrubbed = data.clone();
    scrub_shn_section(&mut scrubbed)?;
    Ok(obfuscated_digest(&scrubbed))
}

/// Other platforms: fall back to marker-based scrubbing.
#[cfg(not(target_os = "windows"))]
pub fn sanitized_hash_of_file(path: &Path) -> Result<String> {
    let mut data = fs::read(path).with_context(|| format!("read {}", path.display()))?;
    scrub_embedded_hash(&mut data)?;
    Ok(obfuscated_digest(&data))
}

#[cfg(target_os = "windows")]
fn scrub_shn_section(bytes: &mut [u8]) -> Result<()> {
    mutate_shn_payload(bytes, |region| {
        region.fill(0);
        Ok(())
    })
}

#[cfg(target_os = "windows")]
pub fn embed_shn_payload(bytes: &mut [u8], payload: &[u8]) -> Result<()> {
    mutate_shn_payload(bytes, |region| {
        if payload.len() > region.len() {
            bail!(
                "payload larger than reserved region ({} > {})",
                payload.len(),
                region.len()
            );
        }
        region.fill(0);
        let len = payload.len();
        region[..len].copy_from_slice(payload);
        Ok(())
    })
}

#[cfg(target_os = "windows")]
fn mutate_shn_payload<F>(bytes: &mut [u8], mutator: F) -> Result<()>
where
    F: FnOnce(&mut [u8]) -> Result<()>,
{
    let (start, end) = shn_payload_window(bytes)?;
    mutator(&mut bytes[start..end])
}

#[cfg(target_os = "windows")]
fn shn_payload_window(bytes: &[u8]) -> Result<(usize, usize)> {
    let pe = PE::parse(bytes).map_err(|err| anyhow!("parse PE image: {err}"))?;
    let section = pe
        .sections
        .iter()
        .find(|s| s.name().unwrap_or_default().trim_end_matches('\0') == SHN_SECTION_NAME)
        .ok_or_else(|| anyhow!("section {SHN_SECTION_NAME} not found"))?;
    let file_off = section.pointer_to_raw_data as usize;
    let raw_size = section.size_of_raw_data as usize;
    if file_off == 0 || raw_size == 0 || file_off + raw_size > bytes.len() {
        return Err(anyhow!("invalid {SHN_SECTION_NAME} layout"));
    }
    let slice = &bytes[file_off..file_off + raw_size];
    let start_magic = markers::shn_start_magic();
    let end_magic = markers::shn_end_magic();
    let start_len = start_magic.len();
    let end_len = end_magic.len();
    if raw_size < start_len + end_len {
        return Err(anyhow!("{} too small", SHN_SECTION_NAME));
    }
    let start_idx = slice
        .windows(start_len)
        .rposition(|window| window == *start_magic)
        .ok_or_else(|| anyhow!("start sentinel mismatch"))?;
    let end_idx = slice
        .windows(end_len)
        .rposition(|window| window == *end_magic)
        .ok_or_else(|| anyhow!("end sentinel mismatch"))?;
    if end_idx <= start_idx + start_len {
        return Err(anyhow!("sentinel order invalid"));
    }
    let payload_start = file_off + start_idx + start_len;
    let payload_end = file_off + end_idx;
    Ok((payload_start, payload_end))
}

#[cfg(not(target_os = "windows"))]
pub fn scrub_embedded_hash(bytes: &mut [u8]) -> Result<()> {
    let (start_marker, end_marker) = protected::self_hash_markers();
    let mut cursor = 0usize;
    let mut cleaned = 0usize;
    while cursor < bytes.len() {
        let Some(rel_start) = locate(&bytes[cursor..], start_marker) else {
            break;
        };
        let start = cursor + rel_start + start_marker.len();
        let rel_end = locate(&bytes[start..], end_marker)
            .ok_or_else(|| anyhow!("self-hash marker end missing"))?;
        let end = start + rel_end;
        for slot in &mut bytes[start..end] {
            let scrambled = *slot ^ REGION_PAD;
            *slot = scrambled.wrapping_sub(scrambled);
        }
        cleaned += 1;
        cursor = end + end_marker.len();
    }
    if cleaned == 0 {
        Err(anyhow!("self-hash marker start missing"))
    } else {
        Ok(())
    }
}

fn locate(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    if needle.is_empty() || haystack.len() < needle.len() {
        return None;
    }
    haystack
        .windows(needle.len())
        .position(|candidate| constant_time_eq(candidate, needle))
}

fn obfuscated_digest(bytes: &[u8]) -> String {
    let mid = bytes.len() / 2;
    let (first, second) = bytes.split_at(mid);
    let mut left = Sha256::new();
    left.update(first);
    let mut right = Sha256::new();
    right.update(second);
    let mut final_hasher = Sha256::new();
    final_hasher.update(left.finalize());
    final_hasher.update(right.finalize());
    let digest = final_hasher.finalize();
    integrity::sha256_of_bytes(digest.as_slice())
}

fn constant_time_eq(lhs: &[u8], rhs: &[u8]) -> bool {
    if lhs.len() != rhs.len() {
        return false;
    }
    let mut diff = 0u8;
    for (&l, &r) in lhs.iter().zip(rhs.iter()) {
        diff |= l ^ r;
    }
    diff == 0
}

#[cfg(all(test, not(target_os = "windows")))]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    fn mk_blob_with_regions(payloads: &[&[u8]]) -> Vec<u8> {
        let (start, end) = protected::self_hash_markers();
        let mut out = Vec::new();
        out.extend_from_slice(b"NOISE_A");
        for p in payloads {
            out.extend_from_slice(start);
            out.extend_from_slice(p);
            out.extend_from_slice(end);
            out.extend_from_slice(b"NOISE_M");
        }
        out.extend_from_slice(b"NOISE_Z");
        out
    }

    fn write_tmp_and_hash(bytes: &[u8]) -> String {
        let mut f = NamedTempFile::new().unwrap();
        f.write_all(bytes).unwrap();
        sanitized_hash_of_file(f.path()).unwrap()
    }

    #[test]
    fn mutating_inside_region_does_not_change_sanitized_hash_single_region() {
        let base = mk_blob_with_regions(&[b"AAAA"]);
        let h1 = write_tmp_and_hash(&base);

        let (start, end) = protected::self_hash_markers();
        let mut modified = base.clone();
        let s = locate(&modified, start).unwrap() + start.len();
        let e = s + locate(&modified[s..], end).unwrap();
        for b in &mut modified[s..e] {
            *b ^= 0x5a;
        }
        let h2 = write_tmp_and_hash(&modified);
        assert_eq!(h1, h2);
    }

    #[test]
    fn mutating_outside_region_changes_hash() {
        let base = mk_blob_with_regions(&[b"AAAA"]);
        let h1 = write_tmp_and_hash(&base);
        let mut modified = base.clone();
        modified[0] ^= 0x33;
        let h2 = write_tmp_and_hash(&modified);
        assert_ne!(h1, h2);
    }

    #[test]
    fn region_at_file_edges_and_empty_region_supported() {
        let (start, end) = protected::self_hash_markers();
        let mut blob = Vec::new();
        blob.extend_from_slice(start);
        blob.extend_from_slice(end);
        blob.extend_from_slice(b"MID");
        blob.extend_from_slice(start);
        blob.extend_from_slice(b"X");
        blob.extend_from_slice(end);

        let mut scrubbed = blob.clone();
        scrub_embedded_hash(&mut scrubbed).unwrap();
        assert_eq!(blob.len(), scrubbed.len());
        let offset = start.len() + end.len() + 3 + start.len();
        assert!(scrubbed[offset..offset + 1].iter().all(|&b| b == 0));
    }

    #[test]
    fn missing_start_marker_is_error() {
        let (_, end) = protected::self_hash_markers();
        let mut blob = b"NO_MARKER".to_vec();
        blob.extend_from_slice(end);
        let err = scrub_embedded_hash(&mut blob).unwrap_err();
        assert!(format!("{err}").contains("start"));
    }

    #[test]
    fn missing_end_marker_is_error() {
        let (start, _) = protected::self_hash_markers();
        let mut blob = Vec::new();
        blob.extend_from_slice(start);
        blob.extend_from_slice(b"OPEN");
        let err = scrub_embedded_hash(&mut blob).unwrap_err();
        assert!(format!("{err}").contains("end"));
    }

    #[test]
    fn constant_time_eq_correctness() {
        assert!(constant_time_eq(b"abc", b"abc"));
        assert!(!constant_time_eq(b"abc", b"abC"));
        assert!(!constant_time_eq(b"abc", b"abcd"));
    }
}
