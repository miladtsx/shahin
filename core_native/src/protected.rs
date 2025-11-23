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
        expected_sha256: "f1bd51630f8923a8d5aa2172c8b0d02bc820d9814b6818e39aab3573d1c6999b",
    },
    ProtectedModuleSpec {
        import_name: "tray_app",
        plaintext_path: "build/pyarmor/tray_app.py",
        encrypted_name: "tray_app.bin",
        expected_sha256: "13d6c539da6e4152b5ff6dfd37b74c18c4c6f3b8248d495d47fdb7c1bf87e030",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.app_logger",
        plaintext_path: "build/pyarmor/app_logger.py",
        encrypted_name: "app_logger.bin",
        expected_sha256: "bec3cbf591bf0fce64a5dc2dcde83ffdd5deb7bf1c48bc13df0f57a5bb839e34",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.resource_path",
        plaintext_path: "build/pyarmor/resource_path.py",
        encrypted_name: "resource_path.bin",
        expected_sha256: "ea97cf3532031d0bdff811bc46476b4ccb2cbe29c660eca2ab32b2761cba841d",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.license_utils",
        plaintext_path: "build/pyarmor/license_utils.py",
        encrypted_name: "license_utils.bin",
        expected_sha256: "cb39b85580214620300b005057a650826175d70baaaa69d8ec6b3cd1325647e5",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.native_guard",
        plaintext_path: "build/pyarmor/native_guard.py",
        encrypted_name: "native_guard.bin",
        expected_sha256: "fc394c7ae36ee04fb9f922c44d4778bf1d4a26cac32365e52f2f0cbb413d3ee3",
    },
    ProtectedModuleSpec {
        import_name: "src.detectors.plate_detector",
        plaintext_path: "build/pyarmor/plate_detector.py",
        encrypted_name: "plate_detector.bin",
        expected_sha256: "dea3c855297c46061b92dc2828d58c20bea8a1de3549d0dca5beeff8ba13bca5",
    },
    ProtectedModuleSpec {
        import_name: "src.detectors.vehicle_detector",
        plaintext_path: "build/pyarmor/vehicle_detector.py",
        encrypted_name: "vehicle_detector.bin",
        expected_sha256: "28cae4fc32a737f61330140726533dad477ac5829cd007b665dd530229727bcf",
    },
    ProtectedModuleSpec {
        import_name: "src.preprocessor.preprocessor",
        plaintext_path: "build/pyarmor/preprocessor.py",
        encrypted_name: "preprocessor.bin",
        expected_sha256: "44fa89c351e2313c6b1a103729f3331dd77876f256ef16fc7395236c2119f968",
    },
    ProtectedModuleSpec {
        import_name: "src.segmentation.segmentation",
        plaintext_path: "build/pyarmor/segmentation.py",
        encrypted_name: "segmentation.bin",
        expected_sha256: "392d2f43ea58666974bbb1c413e1f620d51e2820cd0e2c27233b740d8c580f57",
    },
    ProtectedModuleSpec {
        import_name: "src.selector.best_frame_selector",
        plaintext_path: "build/pyarmor/best_frame_selector.py",
        encrypted_name: "best_frame_selector.bin",
        expected_sha256: "151bf1c0e2ee836e4c37c5aceb66d77d12b3c423148e06744be5d85904f12a0e",
    },
    ProtectedModuleSpec {
        import_name: "src.detect_vehicle",
        plaintext_path: "build/pyarmor/detect_vehicle.py",
        encrypted_name: "detect_vehicle.bin",
        expected_sha256: "e44ae07bf7eb1bd16d2ce5a6591fed3af12ad03652aa7fdd0e70b9bd24e11431",
    },
];

pub const PROTECTED_ASSETS: &[ProtectedAssetSpec] = &[
    ProtectedAssetSpec {
        label: "pyarmor_runtime_000000/__init__.py",
        plaintext_path: "build/pyarmor/pyarmor_runtime_000000/__init__.py",
        encrypted_name: "pyarmor_runtime_000000/__init__.py.bin",
        expected_sha256: "a618769167c2706c844ff13a78ef6761e2a35ba129964d6c40c9dfe4d99b7ca4",
    },
    ProtectedAssetSpec {
        label: "pyarmor_runtime_000000/pyarmor_runtime.pyd",
        plaintext_path: "build/pyarmor/pyarmor_runtime_000000/pyarmor_runtime.pyd",
        encrypted_name: "pyarmor_runtime_000000/pyarmor_runtime.pyd.bin",
        expected_sha256: "dca3a32b3b91ae6642491f83a115a78bcf4c6d52e68a0720d7b2dbca58bdc5c4",
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
