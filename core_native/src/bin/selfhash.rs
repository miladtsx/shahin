use std::env;
use std::path::PathBuf;
use std::process;

/// Tiny CLI wrapper around `selfhash::sanitized_hash_of_file`.
///
/// Usage:
/// ```text
/// selfhash <path-to-exe>
/// ```
///
/// This tool prints the stabilized hash we embed into `self.sha256`. Running it
/// manually is a good sanity check when the build script reports mismatched
/// pre/post hashes.
fn usage() -> ! {
    eprintln!("usage: selfhash <path-to-executable>");
    process::exit(2);
}

fn main() {
    let exe_path = env::args().nth(1).unwrap_or_else(|| usage());
    let path = PathBuf::from(exe_path);

    match core_native::selfhash::sanitized_hash_of_file(&path) {
        Ok(hash) => {
            println!("{hash}");
        }
        Err(err) => {
            eprintln!("selfhash: {err:?}");
            process::exit(1);
        }
    }
}
