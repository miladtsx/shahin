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
        plaintext_path: "build/pyarmor/main.py",
        encrypted_name: "main.bin",
        expected_sha256: "fc71f4dcacb0111385005a40e2d83f8bbb1bf2c0b993b4712ad51c0d8e024e5a",
    },
    ProtectedModuleSpec {
        import_name: "tray_app",
        plaintext_path: "build/pyarmor/tray_app.py",
        encrypted_name: "tray_app.bin",
        expected_sha256: "369e4c29e6bc65ba3d1b9c1e0115e845abb16bf4c679fdf8b82b74f97d994692",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.app_logger",
        plaintext_path: "build/pyarmor/app_logger.py",
        encrypted_name: "app_logger.bin",
        expected_sha256: "74ecddfb1c2ed3abdf8f7b392f4742414e79b8db131fea48a5b8c6b57b070d8b",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.resource_path",
        plaintext_path: "build/pyarmor/resource_path.py",
        encrypted_name: "resource_path.bin",
        expected_sha256: "8009c548b646e254335e5f55000b6ced6293d6161d04c2b2802b2af2481f2bcc",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.license_utils",
        plaintext_path: "build/pyarmor/license_utils.py",
        encrypted_name: "license_utils.bin",
        expected_sha256: "88b7a40fb660114b3dc9f5dc3a1f854feed3a809a392e39c5343fe515bb05e05",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.native_guard",
        plaintext_path: "build/pyarmor/native_guard.py",
        encrypted_name: "native_guard.bin",
        expected_sha256: "1e5161d971908c3ec6f5be8c0492826bf2f8c5d7cd3490ab8bac7a9cc8448776",
    },
    ProtectedModuleSpec {
        import_name: "src.detectors.plate_detector",
        plaintext_path: "build/pyarmor/plate_detector.py",
        encrypted_name: "plate_detector.bin",
        expected_sha256: "1d91cb97d9fcad42b283f4ea85dca45be715f10d1b5c0f71fc5291abaee5dc77",
    },
    ProtectedModuleSpec {
        import_name: "src.detectors.vehicle_detector",
        plaintext_path: "build/pyarmor/vehicle_detector.py",
        encrypted_name: "vehicle_detector.bin",
        expected_sha256: "22436b29d4587048ed19e561b41f6cddbf0eaa4988ca2f9be0530e08675dc29e",
    },
    ProtectedModuleSpec {
        import_name: "src.preprocessor.preprocessor",
        plaintext_path: "build/pyarmor/preprocessor.py",
        encrypted_name: "preprocessor.bin",
        expected_sha256: "17173e87edc00d983ac39dbd812db0c4473af633ca9d46875c8f874566acc798",
    },
    ProtectedModuleSpec {
        import_name: "src.segmentation.segmentation",
        plaintext_path: "build/pyarmor/segmentation.py",
        encrypted_name: "segmentation.bin",
        expected_sha256: "1264094cc6b671faff9024761ee84ef26f692b99bdeed7283d7010fb4632f09d",
    },
    ProtectedModuleSpec {
        import_name: "src.selector.best_frame_selector",
        plaintext_path: "build/pyarmor/best_frame_selector.py",
        encrypted_name: "best_frame_selector.bin",
        expected_sha256: "772748777d2edbb9ac6c37be003ed2bfcb337737ccf8d10f656179d0d32a2bce",
    },
    ProtectedModuleSpec {
        import_name: "src.detect_vehicle",
        plaintext_path: "build/pyarmor/detect_vehicle.py",
        encrypted_name: "detect_vehicle.bin",
        expected_sha256: "fc9dd1d9af5cef009c74361a2ec4ba8cb05fcb1e690c46f0eec2a82f585508a2",
    },
];

pub const PROTECTED_ASSETS: &[ProtectedAssetSpec] = &[
    ProtectedAssetSpec {
        label: "pyarmor_runtime_000000/__init__.py",
        plaintext_path: "build/pyarmor/pyarmor_runtime_000000/__init__.py",
        encrypted_name: "pyarmor_runtime_000000/__init__.py.bin",
        expected_sha256: "ee16716c410b60e3aff1a7a0bcf58e0bac98a4b4018982f5dc4697a9fda06c0b",
    },
    ProtectedAssetSpec {
        label: "pyarmor_runtime_000000/pyarmor_runtime.pyd",
        plaintext_path: "build/pyarmor/pyarmor_runtime_000000/pyarmor_runtime.pyd",
        encrypted_name: "pyarmor_runtime_000000/pyarmor_runtime.pyd.bin",
        expected_sha256: "aaeb83fbcacbc3c95108ef1603f25304169148a5fa1a954b8ca7b3fa2c2353ac",
    },
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
