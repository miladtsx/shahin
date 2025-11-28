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
        expected_sha256: "7530ad45d773ce866ec107fa52912ed276d5f05d893daf3f6c2dc72cccd43983",
    },
    ProtectedModuleSpec {
        import_name: "tray_app",
        plaintext_path: "build/pyarmor/tray_app.py",
        encrypted_name: "tray_app.bin",
        expected_sha256: "e2a310408fd4d00f7d8e5105f6a856054373d574e1fba12b3dd2938d1a8e322f",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.app_logger",
        plaintext_path: "build/pyarmor/app_logger.py",
        encrypted_name: "app_logger.bin",
        expected_sha256: "5cb1261adc470ad9ef7c7cdc5382e54b79db8b58bc451dd4bd8c249ddb86e510",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.resource_path",
        plaintext_path: "build/pyarmor/resource_path.py",
        encrypted_name: "resource_path.bin",
        expected_sha256: "e7348c48b892ccd7b983a5d8336d05f2438138ed2da7c23ccc637f3167c1c862",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.license_utils",
        plaintext_path: "build/pyarmor/license_utils.py",
        encrypted_name: "license_utils.bin",
        expected_sha256: "78e912adf192fb7ce25ef1f2ea6b4e270b8e8b81d8adc95eabe56b3c13893460",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.native_guard",
        plaintext_path: "build/pyarmor/native_guard.py",
        encrypted_name: "native_guard.bin",
        expected_sha256: "9101c6e7b45e2ecf1203ee3cd8597f878ac71012abf4fc866839495f0032e142",
    },
    ProtectedModuleSpec {
        import_name: "src.detectors.plate_detector",
        plaintext_path: "build/pyarmor/plate_detector.py",
        encrypted_name: "plate_detector.bin",
        expected_sha256: "f4272a17204e1a82011f816ad858b8466c6c3fff6b7a2270cc9c219b04213ef2",
    },
    ProtectedModuleSpec {
        import_name: "src.detectors.vehicle_detector",
        plaintext_path: "build/pyarmor/vehicle_detector.py",
        encrypted_name: "vehicle_detector.bin",
        expected_sha256: "7d6d896bb3e2bcda70921edd4e7258d2f5eb74b39807b056b2f2c01b534b4055",
    },
    ProtectedModuleSpec {
        import_name: "src.preprocessor.preprocessor",
        plaintext_path: "build/pyarmor/preprocessor.py",
        encrypted_name: "preprocessor.bin",
        expected_sha256: "aeaa6b669c3871107e96e4709d6ecc64032e5a6158492436b16a2ee950b5f7b7",
    },
    ProtectedModuleSpec {
        import_name: "src.segmentation.segmentation",
        plaintext_path: "build/pyarmor/segmentation.py",
        encrypted_name: "segmentation.bin",
        expected_sha256: "a6752e32b9d15090b7aa3d528e8e410209ca7f387d210987fe8050a1e0457b52",
    },
    ProtectedModuleSpec {
        import_name: "src.selector.best_frame_selector",
        plaintext_path: "build/pyarmor/best_frame_selector.py",
        encrypted_name: "best_frame_selector.bin",
        expected_sha256: "015023066544e4b667ff6b8a163db4447d79c8f94fc8624afe23c024c9a8aa46",
    },
    ProtectedModuleSpec {
        import_name: "src.detect_vehicle",
        plaintext_path: "build/pyarmor/detect_vehicle.py",
        encrypted_name: "detect_vehicle.bin",
        expected_sha256: "0d84e8bc35e346c1f140ad7d84cd8a0fb9ad220a7215d9f3291472242b496cd1",
    },
];

pub const PROTECTED_ASSETS: &[ProtectedAssetSpec] = &[
    ProtectedAssetSpec {
        label: "pyarmor_runtime_000000/__init__.py",
        plaintext_path: "build/pyarmor/pyarmor_runtime_000000/__init__.py",
        encrypted_name: "pyarmor_runtime_000000/__init__.py.bin",
        expected_sha256: "9fc906a2be366f900e9f91fa5c852144c52009282a6b0ece19c6a7b0fa853995",
    },
    ProtectedAssetSpec {
        label: "pyarmor_runtime_000000/pyarmor_runtime.pyd",
        plaintext_path: "build/pyarmor/pyarmor_runtime_000000/pyarmor_runtime.pyd",
        encrypted_name: "pyarmor_runtime_000000/pyarmor_runtime.pyd.bin",
        expected_sha256: "fc9e7f0c1217dbad0ec603ef009b3061838b5a0f082ea9775d123ca391ff927d",
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
