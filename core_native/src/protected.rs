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
        expected_sha256: "7975acb1af6a8d5852fc8fc5223d19f0352235c73f74b1a8b23d9ec64d0aa21f",
    },
    ProtectedModuleSpec {
        import_name: "tray_app",
        plaintext_path: "build/pyarmor/tray_app.py",
        encrypted_name: "tray_app.bin",
        expected_sha256: "da1248e62ddc97a5c989a11899c5fd5698aab74a7e1357f2c45e3abf804f22dc",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.app_logger",
        plaintext_path: "build/pyarmor/app_logger.py",
        encrypted_name: "app_logger.bin",
        expected_sha256: "86b0c86f2f951e8478e027217f19f2ee33d6c74a82c3709b3fcefcd6d949c253",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.resource_path",
        plaintext_path: "build/pyarmor/resource_path.py",
        encrypted_name: "resource_path.bin",
        expected_sha256: "1950e9ea0299fa25dce102242009f636ecd31cde68dab4f16dc01762b6388cb8",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.license_utils",
        plaintext_path: "build/pyarmor/license_utils.py",
        encrypted_name: "license_utils.bin",
        expected_sha256: "20a875b6b14a107d59e2c7ea461bd16ac00c4a7cba53c00266aa47662e039cff",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.native_guard",
        plaintext_path: "build/pyarmor/native_guard.py",
        encrypted_name: "native_guard.bin",
        expected_sha256: "92093109e7d75afccf6b0e684294bbf0b91613b1b41b7fb4895c20611102a093",
    },
    ProtectedModuleSpec {
        import_name: "src.detectors.plate_detector",
        plaintext_path: "build/pyarmor/plate_detector.py",
        encrypted_name: "plate_detector.bin",
        expected_sha256: "2c435f6371b8f661c86963ba4e5c5b44abb2444c8d7256f958d6d23e3d7d7ae5",
    },
    ProtectedModuleSpec {
        import_name: "src.detectors.vehicle_detector",
        plaintext_path: "build/pyarmor/vehicle_detector.py",
        encrypted_name: "vehicle_detector.bin",
        expected_sha256: "2e95b291608e5f6e7e856fd35c7f1254f876a67c1e60bfca5916803bb323f8f9",
    },
    ProtectedModuleSpec {
        import_name: "src.preprocessor.preprocessor",
        plaintext_path: "build/pyarmor/preprocessor.py",
        encrypted_name: "preprocessor.bin",
        expected_sha256: "eee68516c388eee3010d5c6f0a11a6b31b0a9cdbeeb5a8b8e049ab70a59505fa",
    },
    ProtectedModuleSpec {
        import_name: "src.segmentation.segmentation",
        plaintext_path: "build/pyarmor/segmentation.py",
        encrypted_name: "segmentation.bin",
        expected_sha256: "8f55020a3b292db5532ede671682f18b91a6856404902c1dab7f0d90530a4daa",
    },
    ProtectedModuleSpec {
        import_name: "src.selector.best_frame_selector",
        plaintext_path: "build/pyarmor/best_frame_selector.py",
        encrypted_name: "best_frame_selector.bin",
        expected_sha256: "ad16c6eee2a024c1a86a2f4a26e5f6427cc679ed04496c6a123094b11867c0fe",
    },
    ProtectedModuleSpec {
        import_name: "src.detect_vehicle",
        plaintext_path: "build/pyarmor/detect_vehicle.py",
        encrypted_name: "detect_vehicle.bin",
        expected_sha256: "6c3e63f751298f85ac6fdfc097dd0089ceba2a888f30329139b8ebed8c130460",
    },
];

pub const PROTECTED_ASSETS: &[ProtectedAssetSpec] = &[
    ProtectedAssetSpec {
        label: "pyarmor_runtime_000000/__init__.py",
        plaintext_path: "build/pyarmor/pyarmor_runtime_000000/__init__.py",
        encrypted_name: "pyarmor_runtime_000000/__init__.py.bin",
        expected_sha256: "88dafd1e125f9034663af4d14b7f5150eec96e72e3e5342bfc0b5eda030029bd",
    },
    ProtectedAssetSpec {
        label: "pyarmor_runtime_000000/pyarmor_runtime.pyd",
        plaintext_path: "build/pyarmor/pyarmor_runtime_000000/pyarmor_runtime.pyd",
        encrypted_name: "pyarmor_runtime_000000/pyarmor_runtime.pyd.bin",
        expected_sha256: "befecc52559898c92f386269487a01e89c3532b81787e62ce1a2034f8dc4fdb3",
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
