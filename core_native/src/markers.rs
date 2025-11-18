#![cfg(target_os = "windows")]

/// Single `.shn` section emitting start sentinel + payload + end sentinel.
#[repr(C)]
pub struct ShnRegion {
    pub start: [u8; 16],
    pub payload: [u8; 64],
    pub end: [u8; 16],
}

#[link_section = ".shn"]
#[used]
pub static SHN_REGION: ShnRegion = ShnRegion {
    start: *b"SHAHIN\0START\0\0\0\0",
    payload: [0u8; 64],
    end: *b"SHAHIN\0END\0\0\0\0\0\0",
};

pub fn shn_start_magic() -> &'static [u8; 16] {
    &SHN_REGION.start
}

pub fn shn_payload() -> &'static [u8; 64] {
    &SHN_REGION.payload
}

pub fn shn_end_magic() -> &'static [u8; 16] {
    &SHN_REGION.end
}
