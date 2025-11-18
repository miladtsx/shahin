# Issue: Refactor Application Entry Point to Rust for Enhanced Security and Python Module Protection

## Goal
To establish the `core_native` Rust module as the unbypassable primary entry point, performing robust integrity and license checks, and ensuring critical Python modules cannot be executed independently by encrypting them and having Rust handle their decryption and in-memory loading.

## Expected Behavior:
- The application launches exclusively via a single Rust executable (e.g., `shahin.exe` on Windows).
- Upon launch, the Rust executable performs the following critical checks before any significant Python code is executed:
  1.  Self-Integrity Check: Verifies the SHA256 hash of its own executable against a hardcoded, expected hash.
  2.  Critical Python Module Integrity Checks: After decrypting/de-obfuscating, verifies the SHA256 hashes of essential Python modules (e.g., `tray_app.py`, `src/common_utils/license_utils.py`, `src/common_utils/native_guard.py`) against hardcoded, expected hashes.
  3.  License Validation: Performs the primary license validation using the `core_native` Rust licensing functions.
- If all integrity and license checks pass, the Rust executable decrypts/de-obfuscates critical Python modules, initializes the Python interpreter, sets up the necessary environment, and then loads these modules directly into memory before invoking `tray_app.main()`.
- If any integrity or license checks fail, the Rust executable terminates immediately with a clear, concise error message, preventing the Python application from running.
- Critical Python modules (e.g., `tray_app.py`, `src/common_utils/license_utils.py`) will be bundled in an encrypted/obfuscated format, making them unusable if run directly by a standard Python interpreter.
- The overall user experience (tray icon functionality, dashboard, backend processes) remains unchanged for legitimate, untampered installations.

---

## Step-by-Step Plan for Software Engineer
### Phase 1: Prepare `core_native` for Binary Execution, Python Embedding, and Encryption

1.  Modify `core_native/Cargo.toml`:
    - Change the crate-type to ["cdylib", "bin"] to allow building both a shared library (for pyo3 module functions) and an executable.
    - Add pyo3 as a dependency with features = ["extension-module"].
    - Add sha2 = "0.10" and hex = "0.4" for cryptographic hashing.
    - Add walkdir = "2.3" for traversing directories to find Python files within the bundled application.
    - Add anyhow = "1.0" for simplified error handling.
    - Add serde_json = "1.0" and serde = { version = "1.0", features = ["derive"] } for potential JSON serialization/deserialization if needed for arguments.
    - Add a robust symmetric encryption library, e.g., `aes-gcm = "0.10"` or `chacha20poly1305 = "0.10"`, for Python module encryption/decryption.
    - Add `rand = "0.8"` for generating secure random nonces/IVs.
2.  Create `core_native/src/integrity.rs`:
    - Implement a Rust function calculate_bytes_sha256(data: &[u8]) -> String that takes a byte slice and returns its SHA256 hash
      as a hexadecimal string. This will be used for decrypted content.
    - Implement calculate_file_sha256(file_path: &str) -> PyResult<String> as before, for hashing files on disk (e.g., the Rust
      executable itself, or encrypted Python data files).
3.  Create `core_native/src/crypto.rs`:
    - Implement encrypt_data(data: &[u8], key: &[u8]) -> anyhow::Result<Vec<u8>> and decrypt_data(encrypted_data: &[u8], key:
      &[u8]) -> anyhow::Result<Vec<u8>> functions using the chosen symmetric encryption library.
    - Embed the encryption key directly into this Rust module as a `const` byte array. This key must be securely generated and
      kept secret.
4.  Update `core_native/src/lib.rs`:
    - Include the new integrity and crypto modules: mod integrity; mod crypto;
    - Expose integrity::calculate_file_sha256 to Python.
    - (Optional but recommended) Expose integrity::calculate_bytes_sha256 to Python if needed for debugging or testing.
5.  Create `core_native/src/main.rs`:
    - This will be the new Rust application entry point.
    - It will parse command-line arguments using Rust's std::env::args().
6.  Create a build.sh to Generate Initial Expected Hashes and Encrypted Files:
    - Perform a preliminary build of core_native to get the executable.
    - Calculate the SHA256 hash of the core_native executable.
    - For tray_app.py, src/common_utils/license_utils.py, and src/common_utils/native_guard.py:
      - Calculate their original SHA256 hashes (these will be the expected hashes for the decrypted content).
      - Encrypt their content using the Rust crypto::encrypt_data function and the embedded key.
      - Save these encrypted contents to temporary files.
    - These hashes and encrypted contents will be hardcoded or bundled as data in later steps.

### Phase 2: Implement Rust-Anchored Integrity, Licensing, and Python Module Protection

1.  Implement Self-Integrity Check in `core_native/src/main.rs`:
    - At the very beginning of the main function, get the path to the currently running executable.
    - Call integrity::calculate_file_sha256 to get its hash.
    - Compare this hash against the hardcoded expected hash for the core_native executable.
    - If hashes do not match, print an error message to stderr and exit the process with a non-zero status code.
2.  Implement Python Module Decryption and Integrity Checks in `core_native/src/main.rs`:
    - Define a list of critical Python modules (e.g., tray_app, src.common_utils.license_utils, src.common_utils.native_guard)
      and their corresponding hardcoded expected SHA256 hashes of their decrypted content.
    - For each critical module:
      - Locate its encrypted content within the PyInstaller bundle (it will be bundled as a data file).
      - Read the encrypted bytes.
      - Call crypto::decrypt_data to decrypt the content.
      - Call integrity::calculate_bytes_sha256 on the decrypted content.
      - Compare this hash against the hardcoded expected hash for that module.
      - If any hash mismatch, print an error and exit.
      - Store the decrypted Python source/bytecode in a HashMap<String, Vec<u8>> for later in-memory loading.
3.  Implement License Validation in `core_native/src/main.rs`:
    - Acquire the Python GIL (Python::with_gil(|py| { ... })).
    - Import the core_native Python module (which exposes the Rust licensing functions).
    - Call core_native.licensing.license_status() (or a new Rust-only license check if preferred) directly from Rust.
    - If the license status indicates invalidity, print an error and exit.
4.  Launch Python Application from `core_native/src/main.rs`:
    - If all checks pass, proceed to launch the Python application.
    - Initialize the Python interpreter.
    - Implement a Custom Python Importer (in Rust): Create a Rust function that acts as a Python sys.meta_path importer. This
      importer will:
      - Intercept module import requests for the critical Python modules.
      - Retrieve the decrypted source/bytecode from the HashMap prepared earlier.
      - Create a Python module object from this in-memory data.
      - Add this custom importer to sys.meta_path in the Python interpreter.
    - Set up sys.path within the Python interpreter to ensure other non-critical Python modules (which can still be bundled
      normally) can be found.
    - Import the tray_app Python module (which will now be loaded via the custom importer from decrypted memory).
    - Call tray_app.main() from Rust, passing the command-line arguments collected earlier.
    - Handle any Python exceptions that might occur during tray_app.main() execution, printing them and exiting gracefully.

### Phase 3: Adapt Python Code and Build Process

1.  Modify `tray_app.py`:
    - Remove the argparse logic from the main() function, as arguments will now be parsed and passed by the Rust entry point. The
      main function should accept arguments directly (e.g., def main(args_dict):).
    - Remove the if **name** == "**main**": block, as main() will be called directly by the Rust host.
    - Adjust build_command if it's used for spawning sub-processes (backend/dashboard) to ensure it correctly points to the new
      Rust executable as the primary launcher.
2.  Update PyInstaller Spec File (`Shahin.spec`):
    - Change Entry Point: Configure PyInstaller to use the compiled Rust executable (core_native binary) as the main entry point
      instead of tray_app.py. This will likely involve modifying the EXE section or using a custom main script that launches the
      Rust binary.
    - Bundle Rust Executable: Ensure the core_native Rust executable is correctly bundled and placed in the appropriate location
      within the PyInstaller output.
    - Bundle Encrypted Python Modules: Crucially, configure PyInstaller to not bundle tray_app.py,
      src/common_utils/license_utils.py, src/common_utils/native_guard.py (and any other critical modules) as plain Python files
      or standard bytecode. Instead, bundle their encrypted versions as data files (e.g., using datas =
      [('path/to/encrypted_tray_app.bin', 'tray_app.bin')]). This will require custom PyInstaller hooks to perform the encryption
      during the build process.
    - Bundle Other Python Environment: Verify that all non-critical Python modules, standard library, and the core_native shared
      library (used by Python for pyo3 functions) are correctly bundled and accessible to the Rust executable at runtime. This
      might require custom datas entries or hiddenimports.
    - Hooks: Develop custom PyInstaller hooks to manage the encryption of Python files during the build and their inclusion as
      data files.
3.  Testing and Verification:
    - Build and Run: Perform a full PyInstaller build and test the application launch.
    - Integrity Test: Intentionally modify the core_native executable, or the encrypted Python data files, and verify that the
      Rust integrity checks detect the tampering and prevent the application from launching.
    - Direct Python Execution Test: Attempt to run python tray_app.py (or any other critical Python module) directly from the
      bundled output. It should fail or be unusable due to encryption.
    - License Test: Verify that the application correctly handles valid and invalid licenses.
    - Functionality Test: Ensure all application features (tray icon, backend, dashboard, etc.) work as expected after the
      refactor.

---
