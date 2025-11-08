use std::env;

fn main() {
    println!("cargo:rerun-if-env-changed=CORE_NATIVE_DISABLE_PACKING");
    if env::var_os("CORE_NATIVE_DISABLE_PACKING").is_some() {
        return;
    }

    let profile = env::var("PROFILE").unwrap_or_default();
    if profile != "release" {
        return;
    }

    emit_link_arg("-Wl,-s");
    emit_link_arg("-Wl,--gc-sections");
    emit_link_arg("-Wl,--icf=safe");

    let target = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    if target == "linux" {
        emit_link_arg("-Wl,--build-id=none");
    } else if target == "macos" {
        emit_link_arg("-Wl,-dead_strip");
    }
}

fn emit_link_arg(arg: &str) {
    println!("cargo:rustc-cdylib-link-arg={arg}");
}
