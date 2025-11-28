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
        expected_sha256: "a77ddf11789051294be87e74716ec46e5fa452dc0aef2bc49b80e276c92c5ab2",
    },
    ProtectedModuleSpec {
        import_name: "tray_app",
        plaintext_path: "build/pyarmor/tray_app.py",
        encrypted_name: "tray_app.bin",
        expected_sha256: "2b0f2fe785c8b1fc24f13977bd4f49bbe4bb23fd75ed381fce99d4e0d0942f46",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.app_logger",
        plaintext_path: "build/pyarmor/app_logger.py",
        encrypted_name: "app_logger.bin",
        expected_sha256: "7a9a0c0826b6079e590802575ab749224c6a845b7eecde5543cd4281240c158c",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.resource_path",
        plaintext_path: "build/pyarmor/resource_path.py",
        encrypted_name: "resource_path.bin",
        expected_sha256: "43e4cfd6ea53724b04262417a17857fe5a723ac8cf0a745e1f893bad6e2649a4",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.license_utils",
        plaintext_path: "build/pyarmor/license_utils.py",
        encrypted_name: "license_utils.bin",
        expected_sha256: "d788b8db3ef99a7843e587cae491b6d6449bbe4181f6fe8af54de110761f19b8",
    },
    ProtectedModuleSpec {
        import_name: "src.common_utils.native_guard",
        plaintext_path: "build/pyarmor/native_guard.py",
        encrypted_name: "native_guard.bin",
        expected_sha256: "08fc563a93ae4cf6d8d49adf08bc84577cbcbf3b48555d8deb2f0bf43ff05f35",
    },
    ProtectedModuleSpec {
        import_name: "src.detectors.plate_detector",
        plaintext_path: "build/pyarmor/plate_detector.py",
        encrypted_name: "plate_detector.bin",
        expected_sha256: "b4eb267d0e175a279aa1365f9bb42a462f180c0bc31b4b23fbeeb3a0070908b2",
    },
    ProtectedModuleSpec {
        import_name: "src.detectors.vehicle_detector",
        plaintext_path: "build/pyarmor/vehicle_detector.py",
        encrypted_name: "vehicle_detector.bin",
        expected_sha256: "f6ca4aa5fcb26ded7b80ca7f8527d7afc6323ff5873c4f6db76863ec149fdab1",
    },
    ProtectedModuleSpec {
        import_name: "src.preprocessor.preprocessor",
        plaintext_path: "build/pyarmor/preprocessor.py",
        encrypted_name: "preprocessor.bin",
        expected_sha256: "ce759da3f72016b6231450cf4d9b7a9d5383f481dedb530fa93d0e0391af09cc",
    },
    ProtectedModuleSpec {
        import_name: "src.segmentation.segmentation",
        plaintext_path: "build/pyarmor/segmentation.py",
        encrypted_name: "segmentation.bin",
        expected_sha256: "989022f1af546802cc8fa33656a5653b40ea92df079405b533fac62e810bc038",
    },
    ProtectedModuleSpec {
        import_name: "src.selector.best_frame_selector",
        plaintext_path: "build/pyarmor/best_frame_selector.py",
        encrypted_name: "best_frame_selector.bin",
        expected_sha256: "dd27cdce0376878875a5f35aff8b3986a0cb46b52528dea136a95c00a0a8ad57",
    },
    ProtectedModuleSpec {
        import_name: "src.detect_vehicle",
        plaintext_path: "build/pyarmor/detect_vehicle.py",
        encrypted_name: "detect_vehicle.bin",
        expected_sha256: "07978b8f439ab59fa9cab3ab0e5892c26c6ded1de8cb8b033a278c7f1e9e9af2",
    },
];

pub const PROTECTED_ASSETS: &[ProtectedAssetSpec] = &[
    ProtectedAssetSpec {
        label: "pyarmor_runtime_000000/__init__.py",
        plaintext_path: "build/pyarmor/pyarmor_runtime_000000/__init__.py",
        encrypted_name: "pyarmor_runtime_000000/__init__.py.bin",
        expected_sha256: "49b92696c3a7acae047640e4f1685224ff76843e57725a36a794f32be76bd2a3",
    },
    ProtectedAssetSpec {
        label: "pyarmor_runtime_000000/pyarmor_runtime.pyd",
        plaintext_path: "build/pyarmor/pyarmor_runtime_000000/pyarmor_runtime.pyd",
        encrypted_name: "pyarmor_runtime_000000/pyarmor_runtime.pyd.bin",
        expected_sha256: "dd14a41e3e935eed0d595c05100373909554a94c34dc694ac3badde48a381713",
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
