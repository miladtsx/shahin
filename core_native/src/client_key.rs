use anyhow::{anyhow, Context, Result};
use sha2::{Digest, Sha256};
use std::{env, fs};

const SHARD_LEN: usize = 8;
const SHARD_COUNT: usize = 4;
const PLACEHOLDER_BYTE: u8 = 0x5B;
const START_LEN: usize = 12;
const END_LEN: usize = 9;
const ROUND_KEYS: [u64; 8] = [
    0xA93D_4F20_5E8C_B1D3,
    0x6C71_D2F4_981B_0725,
    0xF5A0_1462_C3DE_9871,
    0x0BD4_9C37_A15F_E208,
    0xCB9E_3779_B185_CA87,
    0x1F73_A4D2_C6B9_3085,
    0xD42C_17A0_E98B_2F63,
    0x3190_D8F4_B7CA_E521,
];

macro_rules! shard_bytes {
    ($($name:ident($section_win:literal, $section_unix:literal) = [$($byte:expr),+ $(,)?];)+) => {
        $(
            #[cfg_attr(target_os = "windows", link_section = $section_win)]
            #[cfg_attr(not(target_os = "windows"), link_section = $section_unix)]
            #[used]
            static $name: [u8; shard_total_len()] = [
                $($byte),+,
            ];
        )+
    };
}

const fn shard_total_len() -> usize {
    START_LEN + SHARD_LEN + END_LEN
}

shard_bytes! {
    CLIENT_KEY_SHARD0(".rdata$ks0", ".rodata.ks0") = [
        0x37, 0xE9, 0x1C, 0x54, 0x8B, 0x20, 0xA3, 0x5E, 0xC8, 0x13, 0x6D, 0xF1,
        PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE,
        PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE,
        0x5D, 0x92, 0xAE, 0x41, 0xC7, 0x1B, 0x6F, 0x28, 0x84,
    ];
    CLIENT_KEY_SHARD1(".rdata$ks1", ".rodata.ks1") = [
        0xDD, 0x4A, 0x91, 0xF7, 0x08, 0x63, 0xBC, 0x2E, 0x51, 0x99, 0x03, 0x7C,
        PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE,
        PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE,
        0x12, 0x7F, 0xE3, 0x58, 0xAD, 0x40, 0x9A, 0xC5, 0x31,
    ];
    CLIENT_KEY_SHARD2(".rdata$ks2", ".rodata.ks2") = [
        0x48, 0xB0, 0xD7, 0x29, 0x65, 0x1A, 0x8E, 0xF3, 0x54, 0xC6, 0x0D, 0x72,
        PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE,
        PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE,
        0xE1, 0x39, 0x5B, 0xA6, 0x4C, 0xF8, 0x27, 0x90, 0x13,
    ];
    CLIENT_KEY_SHARD3(".rdata$ks3", ".rodata.ks3") = [
        0xAB, 0x16, 0x4D, 0xF8, 0x32, 0xC1, 0x7E, 0x95, 0x0B, 0x6A, 0xD3, 0x4F,
        PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE,
        PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE, PLACEHOLDER_BYTE,
        0x73, 0x08, 0xDF, 0x42, 0xB6, 0x1C, 0x85, 0xEA, 0x59,
    ];
}

pub struct EmbeddedShardPattern {
    pub start: &'static [u8],
    pub end: &'static [u8],
}

pub fn embedded_shards() -> [EmbeddedShardPattern; SHARD_COUNT] {
    [
        EmbeddedShardPattern {
            start: &CLIENT_KEY_SHARD0[..START_LEN],
            end: &CLIENT_KEY_SHARD0[START_LEN + SHARD_LEN..],
        },
        EmbeddedShardPattern {
            start: &CLIENT_KEY_SHARD1[..START_LEN],
            end: &CLIENT_KEY_SHARD1[START_LEN + SHARD_LEN..],
        },
        EmbeddedShardPattern {
            start: &CLIENT_KEY_SHARD2[..START_LEN],
            end: &CLIENT_KEY_SHARD2[START_LEN + SHARD_LEN..],
        },
        EmbeddedShardPattern {
            start: &CLIENT_KEY_SHARD3[..START_LEN],
            end: &CLIENT_KEY_SHARD3[START_LEN + SHARD_LEN..],
        },
    ]
}

pub fn scatter_fragments_for_embedding(
    base_key: &[u8; 32],
    sanitize_hash: &str,
) -> Result<[[u8; SHARD_LEN]; SHARD_COUNT]> {
    let mut words = key_words(base_key);
    obscure_words(&mut words);
    xor_with_mask(&mut words, sanitize_hash)?;
    Ok(words_to_fragments(&words))
}

pub fn derive_runtime_key(actual_hash: &str, client_id: &str) -> Result<[u8; 32]> {
    let base = recover_embedded_key(actual_hash)?;
    Ok(finalize_key_material(&base, client_id))
}

pub fn finalize_key_material(base_key: &[u8; 32], client_id: &str) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(mask_client_id(client_id));
    hasher.update(base_key);
    let digest = hasher.finalize();
    let mut out = [0u8; 32];
    out.copy_from_slice(&digest);
    out
}

pub fn scrub_client_key_region(bytes: &mut [u8]) -> Result<()> {
    for pattern in embedded_shards() {
        scrub_shard(bytes, pattern.start, pattern.end)?;
    }
    Ok(())
}

fn scrub_shard(bytes: &mut [u8], start: &[u8], end: &[u8]) -> Result<()> {
    let mut cursor = 0usize;
    while cursor < bytes.len() {
        let Some(rel_start) = locate(&bytes[cursor..], start) else {
            break;
        };
        let payload_start = cursor + rel_start + start.len();
        let Some(rel_end) = locate(&bytes[payload_start..], end) else {
            return Err(anyhow!("client key shard end marker missing"));
        };
        let payload_end = payload_start + rel_end;
        if payload_end - payload_start == SHARD_LEN {
            for slot in &mut bytes[payload_start..payload_end] {
                *slot = 0;
            }
            return Ok(());
        }
        cursor = payload_start + rel_end;
    }
    Err(anyhow!("client key shard marker sequence missing"))
}

fn recover_embedded_key(actual_hash: &str) -> Result<[u8; 32]> {
    let mut words = shard_payloads()?;
    xor_with_mask(&mut words, actual_hash)?;
    recover_words(&mut words);
    Ok(words_to_bytes(&words))
}

fn shard_payloads() -> Result<[u64; SHARD_COUNT]> {
    if let Some(words) = load_payloads_from_exe()? {
        return Ok(words);
    }

    let shards = [
        payload_from_static(&CLIENT_KEY_SHARD0),
        payload_from_static(&CLIENT_KEY_SHARD1),
        payload_from_static(&CLIENT_KEY_SHARD2),
        payload_from_static(&CLIENT_KEY_SHARD3),
    ];
    if shards
        .iter()
        .all(|block| block.iter().all(|&b| b == PLACEHOLDER_BYTE))
    {
        return Err(anyhow!("client key shards still placeholders"));
    }

    let mut out = [0u64; SHARD_COUNT];
    for (idx, block) in shards.into_iter().enumerate() {
        out[idx] = u64::from_le_bytes(block);
    }
    Ok(out)
}

fn load_payloads_from_exe() -> Result<Option<[u64; SHARD_COUNT]>> {
    let exe = env::current_exe().context("locate current executable")?;
    let bytes = fs::read(&exe).with_context(|| format!("read {}", exe.display()))?;
    if let Some(payloads) = payloads_from_blob(&bytes) {
        let mut out = [0u64; SHARD_COUNT];
        for (idx, block) in payloads.into_iter().enumerate() {
            out[idx] = u64::from_le_bytes(block);
        }
        return Ok(Some(out));
    }
    Ok(None)
}

fn payloads_from_blob(bytes: &[u8]) -> Option<[[u8; SHARD_LEN]; SHARD_COUNT]> {
    let mut payloads = [[0u8; SHARD_LEN]; SHARD_COUNT];
    for (idx, pattern) in embedded_shards().iter().enumerate() {
        let rel_start = locate(bytes, pattern.start)?;
        let payload_start = rel_start + pattern.start.len();
        let rel_end = locate(&bytes[payload_start..], pattern.end)?;
        let payload_end = payload_start + rel_end;
        if payload_end - payload_start != SHARD_LEN {
            return None;
        }
        payloads[idx].copy_from_slice(&bytes[payload_start..payload_end]);
    }
    Some(payloads)
}

fn payload_from_static(block: &[u8]) -> [u8; SHARD_LEN] {
    let mut payload = [0u8; SHARD_LEN];
    payload.copy_from_slice(&block[START_LEN..START_LEN + SHARD_LEN]);
    payload
}

fn xor_with_mask(words: &mut [u64; SHARD_COUNT], hash_hex: &str) -> Result<()> {
    let mask = derive_mask(hash_hex)?;
    let mask_words = key_words(&mask);
    for (idx, word) in words.iter_mut().enumerate() {
        *word ^= mask_words[idx];
    }
    Ok(())
}

fn key_words(bytes: &[u8; 32]) -> [u64; SHARD_COUNT] {
    let mut out = [0u64; SHARD_COUNT];
    for (idx, chunk) in bytes.chunks_exact(SHARD_LEN).enumerate() {
        out[idx] = u64::from_le_bytes(chunk.try_into().unwrap());
    }
    out
}

fn words_to_bytes(words: &[u64; SHARD_COUNT]) -> [u8; 32] {
    let mut out = [0u8; 32];
    for (idx, word) in words.iter().enumerate() {
        out[idx * SHARD_LEN..(idx + 1) * SHARD_LEN].copy_from_slice(&word.to_le_bytes());
    }
    out
}

fn words_to_fragments(words: &[u64; SHARD_COUNT]) -> [[u8; SHARD_LEN]; SHARD_COUNT] {
    let mut out = [[0u8; SHARD_LEN]; SHARD_COUNT];
    for (idx, word) in words.iter().enumerate() {
        out[idx].copy_from_slice(&word.to_le_bytes());
    }
    out
}

fn obscure_words(words: &mut [u64; SHARD_COUNT]) {
    for round in 0..ROUND_KEYS.len() {
        let src = round % SHARD_COUNT;
        let dst = (round + 1) % SHARD_COUNT;
        let mix = feistel(words[dst], ROUND_KEYS[round]);
        words[src] ^= mix;
        words.swap(src, dst);
    }
}

fn recover_words(words: &mut [u64; SHARD_COUNT]) {
    for round in (0..ROUND_KEYS.len()).rev() {
        let src = round % SHARD_COUNT;
        let dst = (round + 1) % SHARD_COUNT;
        words.swap(src, dst);
        let mix = feistel(words[dst], ROUND_KEYS[round]);
        words[src] ^= mix;
    }
}

fn feistel(value: u64, key: u64) -> u64 {
    let mut x = value.wrapping_add(key);
    x ^= x.rotate_left(((key >> 11) as u32 & 0x1F) + 1);
    x = x.wrapping_mul(key ^ 0x9E37_79B1_85EB_CA87);
    x.rotate_left(7) ^ (x >> 3)
}

fn derive_mask(hash_hex: &str) -> Result<[u8; 32]> {
    if hash_hex.len() != 64 {
        return Err(anyhow!("launcher hash must be 64 hex characters"));
    }
    let seed = hex::decode(hash_hex).map_err(|err| anyhow!("invalid launcher hash hex: {err}"))?;
    let mut state = u64::from_le_bytes(seed[0..8].try_into().unwrap());
    let mut mask = [0u8; 32];
    for idx in 0..mask.len() {
        state = xorshift(state ^ ROUND_KEYS[idx % ROUND_KEYS.len()]);
        let byte = (state >> ((idx % 8) * 8)) as u8 ^ seed[idx % seed.len()];
        mask[idx] = byte;
    }
    Ok(mask)
}

fn xorshift(mut state: u64) -> u64 {
    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    state
}

fn mask_client_id(client_id: &str) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(client_id.as_bytes());
    hasher.update(b"\xA5\x5C\x92\xb4");
    let digest = hasher.finalize();
    let mut out = [0u8; 32];
    out.copy_from_slice(&digest);
    out
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scatter_and_recover_round_trip() {
        let base = [0x11u8; 32];
        let fragments = scatter_fragments_for_embedding(
            &base,
            "00553b2459c656889fc038d899ed162042272a9327efc9b448ed73fe421b4ffc",
        )
        .expect("scatter");
        // Emulate runtime path
        let mut words = [0u64; SHARD_COUNT];
        for (idx, frag) in fragments.iter().enumerate() {
            words[idx] = u64::from_le_bytes(*frag);
        }
        xor_with_mask(
            &mut words,
            "00553b2459c656889fc038d899ed162042272a9327efc9b448ed73fe421b4ffc",
        )
        .expect("mask");
        recover_words(&mut words);
        assert_eq!(words_to_bytes(&words), base);
    }
}
