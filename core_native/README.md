# core_native

## Hardened build packaging

Release builds of the native extension are pinned through `build.rs`, which
injects the following linker arguments automatically during `cargo build --release`:

- `-Wl,-s` (strip unused symbol/debug tables)
- `-Wl,--gc-sections` (drop unreferenced sections)
- `-Wl,--icf=safe` (identical code folding to normalize `.text`)
- `-Wl,--build-id=none` on Linux or `-Wl,-dead_strip` on macOS to keep
  deterministic section layouts

To reproduce the same packing steps manually (e.g., when inspecting CI
artifacts), run the explicit strip/normalization commands below from the repo
root after a release build finishes:

```bash
cargo build --release -p core_native
llvm-s        trip --strip-unneeded target/release/libcore_native.so
llvm- objcopy --remove-section .comment --remove-section .note target/release/libcore_native.so
```

Use `strip`/`objcopy` from `binutils` if the LLVM variants are unavailable.

Set `CORE_NATIVE_DISABLE_PACKING=1` in the environment to skip the automatic
linker flags for local debugging builds.

## Client-specific sealing

`core_native/build.ps1` accepts `-ClientId` (and optionally an explicit
`-ClientKeyHex`/`-ClientKeyFile`). When `-ClientId` is provided the build
automatically creates or reuses a random 32-byte secret stored at
`.keys/client-<id>.key` (this path sits at the repo root and is ignored by git).
That key both encrypts the Python/asset payloads and gets embedded—after
obfuscation—into the Rust launcher via `embedkey`, so nothing outside Rust ever
sees the raw material. The `protect` helper still writes
`protected/key_manifest.json` noting whether payloads expect launcher-hash
derivation or a client key; keeping the `.keys/client-*.key` files lets you
repackage updates for that client later without changing their decryption key.
