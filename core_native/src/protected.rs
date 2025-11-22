pub struct ProtectedModuleSpec {
    pub import_name: &'static str,
    pub plaintext_path: &'static str,
    pub encrypted_name: &'static str,
    pub expected_sha256: &'static str,
}

pub struct ProtectedAssetSpec {
    pub label: &'static str,
    pub plaintext_path: &'static str,
    pub encrypted_name: &'static str,
    pub expected_sha256: &'static str,
}

pub const PROTECTED_MODULES: &[ProtectedModuleSpec] = &[
    ProtectedModuleSpec {
        import_name: "main",
        plaintext_path: "main.py",
        encrypted_name: "main.bin",
        expected_sha256: "955458ebf937ac0dc0993e9fd96fefb9fa8e899ade85f44ff37df44d401c9902",
    },
    ProtectedModuleSpec {
        import_name: "tray_app",
        plaintext_path: "tray_app.py",
        encrypted_name: "tray_app.bin",
        expected_sha256: "c81097704ef7e2c6dc21fc3c986fee94fa9c2837bbd7dbd3303a3a70c9abc014",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.app_logger",
        plaintext_path: "src/common_utils/app_logger.py",
        encrypted_name: "app_logger.bin",
        expected_sha256: "077ce75888edc8ae13fc5c039e7bea678350039102e1d494192b3721a6f7bdd8",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.resource_path",
        plaintext_path: "src/common_utils/resource_path.py",
        encrypted_name: "resource_path.bin",
        expected_sha256: "d1e89dc903794a03e2f85a8d301c90211b56577951870b94a3ae2cf57484611c",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.license_utils",
        plaintext_path: "src/common_utils/license_utils.py",
        encrypted_name: "license_utils.bin",
        expected_sha256: "44a24b915d0ccb02ff18a1d9f710ab470e67307c1cbd33eab3e7c932ee4576f7",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.native_guard",
        plaintext_path: "src/common_utils/native_guard.py",
        encrypted_name: "native_guard.bin",
        expected_sha256: "71f97f5aeb6a50f93de24fdafd131752c0eb6b79e1275965bdffa22a9d493526",
    },
];

pub const PROTECTED_ASSETS: &[ProtectedAssetSpec] = &[
    ProtectedAssetSpec {
        label: "alphabet_classifier_yolov8n.pt",
        plaintext_path: "res/models/alphabet_classifier_yolov8n.pt",
        encrypted_name: "models/alphabet_classifier_yolov8n.pt.bin",
        expected_sha256: "ad1939e8f7478cf50ed30e21d8785b211a2ee76d4ab43cd53697a2443e89e420",
    },
    ProtectedAssetSpec {
        label: "base_classifier_yolov8n-cls.pt",
        plaintext_path: "res/models/base_classifier_yolov8n-cls.pt",
        encrypted_name: "models/base_classifier_yolov8n-cls.pt.bin",
        expected_sha256: "3c13760a5e1594c0070005d2510e4accd79aa1f86ee55c1580db69c852a4b146",
    },
    ProtectedAssetSpec {
        label: "digit_classifier_yolov8n.pt",
        plaintext_path: "res/models/digit_classifier_yolov8n.pt",
        encrypted_name: "models/digit_classifier_yolov8n.pt.bin",
        expected_sha256: "526e302e10cd9d4fa4d85ec1e3271a33c56396f98bc1064241fb9efce6f05a51",
    },
    ProtectedAssetSpec {
        label: "license_plate_detector.pt",
        plaintext_path: "res/models/license_plate_detector.pt",
        encrypted_name: "models/license_plate_detector.pt.bin",
        expected_sha256: "8ec3b254a6c87610f037a90957462cafa11a9c03224e33a28c6a1d1ac2ac51b0",
    },
    ProtectedAssetSpec {
        label: "vehicle_detector_yolov11n.pt",
        plaintext_path: "res/models/vehicle_detector_yolov11n.pt",
        encrypted_name: "models/vehicle_detector_yolov11n.pt.bin",
        expected_sha256: "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1",
    },
];

#[cfg(not(target_os = "windows"))]
pub const SELF_HASH_MARKER_START: &str = "__WIN_INTEGRITY_BEGIN__";
#[cfg(not(target_os = "windows"))]
pub const SELF_HASH_MARKER_END: &str = "__WIN_INTEGRITY_END__";

#[cfg(not(target_os = "windows"))]
#[used]
#[link_section = ".rodata.sha_guard"]
static SELF_HASH_PROBE: &str = concat!(
    "__WIN_INTEGRITY_BEGIN__",
    include_str!("../protected/self.sha256"),
    "__WIN_INTEGRITY_END__",
);

pub const PROTECTED_SUBDIR: &str = "protected";
pub const SOURCE_ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/..");

#[cfg(target_os = "windows")]
pub fn expected_self_hash() -> Option<&'static str> {
    let raw = std::str::from_utf8(crate::markers::shn_payload()).expect("hash payload utf-8");
    let trimmed = raw.trim_matches('\0').trim();
    if trimmed.is_empty() || trimmed.eq_ignore_ascii_case("development") {
        None
    } else {
        Some(trimmed)
    }
}

#[cfg(not(target_os = "windows"))]
pub fn expected_self_hash() -> Option<&'static str> {
    let start = SELF_HASH_PROBE.find(SELF_HASH_MARKER_START)? + SELF_HASH_MARKER_START.len();
    let tail = &SELF_HASH_PROBE[start..];
    let end = tail.find(SELF_HASH_MARKER_END)?;
    let hash = tail[..end].trim();
    if hash.is_empty() || hash.eq_ignore_ascii_case("development") {
        None
    } else {
        Some(hash)
    }
}

#[cfg(not(target_os = "windows"))]
pub fn self_hash_markers() -> (&'static [u8], &'static [u8]) {
    (
        SELF_HASH_MARKER_START.as_bytes(),
        SELF_HASH_MARKER_END.as_bytes(),
    )
}

#[cfg(target_os = "windows")]
pub fn self_hash_markers() -> (&'static [u8], &'static [u8]) {
    (
        crate::markers::shn_start_magic(),
        crate::markers::shn_end_magic(),
    )
}
