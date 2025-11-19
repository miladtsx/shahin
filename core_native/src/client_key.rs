use anyhow::{anyhow, Result};
use once_cell::sync::OnceCell;

const KEY_MARKER_START: &[u8] = b"__S_C_K_BEGIN__";
const KEY_MARKER_END: &[u8] = b"__S_C_K_END__";
const KEY_PLACEHOLDER_HEX: &str = "0000000000000000000000000000000000000000000000000000000000000000";
const OBFUSCATION_MASK: [u8; 32] = [
    0x4a, 0x9f, 0x33, 0xb1, 0x07, 0xd5, 0x5c, 0x2e, 0x61, 0x9c, 0x86, 0xda, 0x1b, 0x42, 0xfe, 0x20,
    0xaf, 0x5e, 0x17, 0xca, 0x94, 0x01, 0x7d, 0xe2, 0x38, 0xbd, 0x6c, 0x0a, 0x53, 0xf4, 0x8b, 0x79,
];
static EMBEDDED_KEY: OnceCell<Option<[u8; 32]>> = OnceCell::new();

#[cfg_attr(not(target_os = "windows"), link_section = ".rodata.client_key")]
#[used]
static CLIENT_KEY_SENTINEL: &str =
    "__S_C_K_BEGIN__0000000000000000000000000000000000000000000000000000000000000000__S_C_K_END__";

pub fn embedded_key_bytes() -> Result<Option<[u8; 32]>> {
    EMBEDDED_KEY.get_or_try_init(|| load_embedded_key()).map(|opt| *opt)
}

pub fn obfuscate_key(key_bytes: &[u8; 32]) -> [u8; 32] {
    xor_with_mask(key_bytes)
}

pub fn deobfuscate_key(obfuscated_hex: &[u8]) -> Result<[u8; 32]> {
    if obfuscated_hex.len() != KEY_PLACEHOLDER_HEX.len() {
        return Err(anyhow!(
            "obfuscated key must be {} hex chars",
            KEY_PLACEHOLDER_HEX.len()
        ));
    }
    let decoded = hex::decode(obfuscated_hex)
        .map_err(|err| anyhow!("invalid embedded key payload: {err}"))?;
    if decoded.len() != 32 {
        return Err(anyhow!(
            "embedded key payload must decode to 32 bytes, got {}",
            decoded.len()
        ));
    }
    let mut buf = [0u8; 32];
    buf.copy_from_slice(&decoded);
    Ok(xor_with_mask(&buf))
}

pub fn embed_client_key_payload(bytes: &mut [u8], payload: &[u8]) -> Result<()> {
    if payload.len() != KEY_PLACEHOLDER_HEX.len() {
        return Err(anyhow!(
            "client key payload must be {} bytes",
            KEY_PLACEHOLDER_HEX.len()
        ));
    }
    mutate_region(bytes, |region| {
        if region.len() != payload.len() {
            return Err(anyhow!(
                "embedded region len mismatch (expected {}, got {})",
                payload.len(),
                region.len()
            ));
        }
        region.copy_from_slice(payload);
        Ok(())
    })
}

pub fn scrub_client_key_region(bytes: &mut [u8]) -> Result<()> {
    mutate_region(bytes, |region| {
        for slot in region {
            *slot = 0;
        }
        Ok(())
    })
}

fn load_embedded_key() -> Result<Option<[u8; 32]>> {
    let payload = raw_embedded_hex();
    if payload.trim().is_empty() || payload == KEY_PLACEHOLDER_HEX {
        return Ok(None);
    }
    deobfuscate_key(payload.as_bytes()).map(Some)
}

fn raw_embedded_hex() -> &'static str {
    let start = KEY_MARKER_START.len();
    let end = CLIENT_KEY_SENTINEL.len() - KEY_MARKER_END.len();
    &CLIENT_KEY_SENTINEL[start..end]
}

fn mutate_region(bytes: &mut [u8], mut mutator: impl FnMut(&mut [u8]) -> Result<()>) -> Result<()> {
    let (start, end) = locate_region(bytes)?;
    mutator(&mut bytes[start..end])
}

fn locate_region(bytes: &[u8]) -> Result<(usize, usize)> {
    let mut cursor = 0usize;
    let payload_len = KEY_PLACEHOLDER_HEX.len();
    while cursor < bytes.len() {
        let Some(rel_start) = locate(&bytes[cursor..], KEY_MARKER_START) else {
            break;
        };
        let start_idx = cursor + rel_start;
        let payload_start = start_idx + KEY_MARKER_START.len();
        if payload_start + payload_len <= bytes.len() {
            if bytes[payload_start + payload_len..]
                .starts_with(KEY_MARKER_END)
            {
                return Ok((payload_start, payload_start + payload_len));
            }
        }
        cursor = payload_start;
    }
    Err(anyhow!("client key sentinel region not found"))
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

fn xor_with_mask(input: &[u8; 32]) -> [u8; 32] {
    let mut out = [0u8; 32];
    for (idx, byte) in input.iter().enumerate() {
        out[idx] = byte ^ OBFUSCATION_MASK[idx];
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn obfuscation_round_trip() {
        let data = [0x11u8; 32];
        let obf = obfuscate_key(&data);
        let payload = hex::encode(obf);
        let recovered = deobfuscate_key(payload.as_bytes()).expect("decode");
        assert_eq!(recovered, data);
    }

    #[test]
    fn locate_and_embed_region() {
        let mut blob = Vec::new();
        blob.extend_from_slice(b"HEAD");
        blob.extend_from_slice(KEY_MARKER_START);
        blob.extend_from_slice(KEY_PLACEHOLDER_HEX.as_bytes());
        blob.extend_from_slice(KEY_MARKER_END);
        blob.extend_from_slice(b"TAIL");

        let payload = b"1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef";
        embed_client_key_payload(&mut blob, payload).expect("embed");
        assert!(blob
            .windows(payload.len())
            .any(|window| window == *payload));

        scrub_client_key_region(&mut blob).expect("scrub");
        let zeros = vec![0u8; payload.len()];
        assert!(blob
            .windows(payload.len())
            .any(|window| window == zeros.as_slice()));
    }
}
