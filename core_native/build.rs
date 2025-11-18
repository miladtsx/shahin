fn main() {
    println!("cargo:rerun-if-env-changed=CORE_NATIVE_DISABLE_PACKING");
    if std::env::var_os("CORE_NATIVE_DISABLE_PACKING").is_some() {
        return;
    }

    let profile = std::env::var("PROFILE").unwrap_or_default();
    if profile != "release" {
        return;
    }

    let os = std::env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    let target = std::env::var("CARGO_CFG_TARGET_ENV").unwrap_or_default(); // "msvc" | "gnu" | "musl" | "none"
    if target == "msvc" {
        emit_any_link_arg("/Brepro");
        emit_any_link_arg("/INCREMENTAL:NO");
        emit_any_link_arg("/OPT:REF");
        emit_any_link_arg("/OPT:ICF");
        emit_any_link_arg("/DEBUG:NONE"); // only if you truly want zero PDBs
        if os == "windows" {
            emit_any_link_arg("/SECTION:.shn,R");
        }
    } else {
        emit_cdylib_link_arg("-Wl,-s");
        emit_cdylib_link_arg("-Wl,--gc-sections");
        emit_cdylib_link_arg("-Wl,--icf=safe");
        if os == "linux" {
            emit_cdylib_link_arg("-Wl,--build-id=none");
        } else if os == "macos" {
            emit_cdylib_link_arg("-Wl,-dead_strip");
        } else if os == "windows" {
            emit_cdylib_link_arg("-Wl,--section=.shn,R");
        }
    }
}

fn emit_any_link_arg(arg: &str) {
    // affects all crate types (bin, cdylib, etc.)
    println!("cargo:rustc-link-arg={arg}");
}

fn emit_cdylib_link_arg(arg: &str) {
    println!("cargo:rustc-cdylib-link-arg={arg}");
}
