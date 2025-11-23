use anyhow::{anyhow, bail, Context, Result};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use core_native::crypto::ModuleKeySource;
use core_native::{
    client_key, core_native_py, crypto, integrity, key_manifest, protected, selfhash,
};
use pyo3::types::PyByteArray;
use pyo3::{
    prelude::*,
    types::{PyDict, PyList, PyModule},
};
use rand::{rng, RngCore};
use std::{
    collections::HashMap,
    env, fs,
    path::{Path, PathBuf},
    process, thread,
    time::Duration,
};
use sysinfo::{Pid, ProcessRefreshKind, RefreshKind, System};
use walkdir::WalkDir;

const MEMORY_IMPORTER: &str = r#"
import importlib.abc
import importlib.machinery
import os
import sys

_FINDER = None
_TOKEN_ENV = "SHAHIN_LAUNCH_TOKEN"


def _zeroize(buf):
    if buf is None:
        return
    mv = memoryview(buf)
    try:
        for idx in range(len(mv)):
            mv[idx] = 0
    finally:
        mv.release()


class _MemoryLoader(importlib.abc.Loader):
    def __init__(self, fullname, payload):
        self.fullname = fullname
        self._payload = payload

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        if self._payload is None:
            raise ImportError(f"{self.fullname} payload already consumed", name=self.fullname)
        module.__file__ = f"<protected>/{self.fullname.replace('.', '/')}.py"
        module.__loader__ = self
        payload = self._payload
        self._payload = None
        try:
            code = compile(payload, module.__file__, "exec")
        finally:
            _zeroize(payload)
        exec(code, module.__dict__)

    def get_source(self, fullname):
        raise OSError("protected module; source unavailable")

    def get_data(self, path):
        raise OSError("protected module; data unavailable")


class _MemoryFinder(importlib.abc.MetaPathFinder):
    def __init__(self, modules, token):
        self.modules = modules
        self.token = token

    def _authorized(self):
        return os.environ.get(_TOKEN_ENV) == self.token

    def find_spec(self, fullname, path, target=None):
        if fullname not in self.modules:
            return None
        if not self._authorized():
            raise ImportError("protected loader requires launcher", name=fullname)
        payload = self.modules.pop(fullname, None)
        if payload is not None:
            loader = _MemoryLoader(fullname, payload)
            return importlib.machinery.ModuleSpec(fullname, loader, is_package=False)
        return None


def install_memory_importer(modules, token):
    env_token = os.environ.get(_TOKEN_ENV)
    if env_token is None or env_token != token:
        raise RuntimeError("protected loader can only be installed by the launcher")
    global _FINDER
    finder = _MemoryFinder(modules, token)
    if _FINDER in sys.meta_path:
        sys.meta_path.remove(_FINDER)
    _FINDER = finder
    sys.meta_path.insert(0, finder)
"#;

fn main() {
    if let Err(err) = run() {
        eprintln!("shahin launcher: {err:?}");
        env::set_var("SHAHIN_ERROR", format!("shahin launcher: {err:?}"));

        std::process::exit(1);
    }
}

fn run() -> Result<()> {
    let args = LaunchArgs::from_env()?;
    let exe_path = env::current_exe().context("locate current executable")?;
    let actual_hash = verify_self_hash(&exe_path)?;
    env::set_var("WIN_ENTRY", &exe_path);
    env::set_var("WIN_INTEGRITY", &actual_hash);
    let bundle_roots = candidate_payload_roots(&exe_path);
    let manifest = locate_key_manifest(&bundle_roots)?;
    let key_source = determine_key_source(manifest.as_ref(), &actual_hash)?;
    crypto::initialize_module_key(key_source)?;

    if let Some(expected) = protected::expected_self_hash() {
        spawn_integrity_beacon(exe_path.clone(), expected.to_ascii_lowercase());
    }

    let (mut modules, payload_root) = load_protected_modules(&bundle_roots)?;
    if let Some(root) = payload_root.as_ref() {
        env::set_var("WIN_PD", root);
    }
    let (models_dir, pyarmor_root, _cache_guard) = stage_protected_assets(&bundle_roots)?;
    env::set_var("WIN_MDL", models_dir.to_string_lossy().as_ref());
    if let Some(runtime_root) = pyarmor_root {
        env::set_var("WIN_PYARMOR", runtime_root.to_string_lossy().as_ref());
    }

    let importer_token = generate_launch_token();
    env::set_var("SHAHIN_LAUNCH_TOKEN", &importer_token);

    // Expose the bundled core_native module to the embedded interpreter so
    // Python imports succeed even when no external .pyd is available.
    pyo3::append_to_inittab!(core_native_py);
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| bootstrap_python(py, &mut modules, &args, &exe_path, &importer_token))
        .map_err(|err| anyhow!(err.to_string()))?;
    Ok(())
}

fn verify_self_hash(exe_path: &Path) -> Result<String> {
    let actual = selfhash::sanitized_hash_of_file(exe_path)?;
    if let Some(expected) = protected::expected_self_hash() {
        let actual_lc = actual.to_ascii_lowercase();
        let expected_lc = expected.to_ascii_lowercase();
        if !constant_time_hex_eq(&actual_lc, &expected_lc) {
            bail!("self-integrity mismatch (expected {expected_lc}, got {actual_lc})");
        }
        return Ok(actual_lc);
    }
    eprintln!("[dev] expected self hash missing; continuing without enforcement");
    Ok(actual.to_ascii_lowercase())
}

fn spawn_integrity_beacon(exe_path: PathBuf, expected_hash: String) {
    thread::Builder::new()
        .name("integrity-beacon".into())
        .spawn(move || {
            let cadence = Duration::from_secs(75);
            loop {
                thread::sleep(cadence);
                if let Err(err) = beacon_tick(&exe_path, &expected_hash) {
                    eprintln!("integrity beacon tripped: {err:?}");
                    process::exit(2);
                }
            }
        })
        .expect("spawn integrity beacon thread");
}

fn beacon_tick(exe_path: &Path, expected_hash: &str) -> Result<()> {
    let current = selfhash::sanitized_hash_of_file(exe_path)?;
    let current_lc = current.to_ascii_lowercase();
    if !constant_time_hex_eq(&current_lc, expected_hash) {
        bail!("runtime self-hash mismatch");
    }

    Python::with_gil(|py| -> Result<()> {
        let license_module = py.import_bound("src.common_utils.license_utils")?;
        let status = license_module.call_method1("license_status", ())?;
        enforce_license(&status).map_err(|err| anyhow!(err.to_string()))?;
        Ok(())
    })?;

    Ok(())
}

fn enforce_license(status: &Bound<'_, PyAny>) -> PyResult<()> {
    let valid = status.getattr("valid")?.extract::<bool>()?;
    if valid {
        return Ok(());
    }

    let reason = status
        .getattr("reason")?
        .extract::<String>()
        .unwrap_or_else(|_| "unknown".to_string());
    if reason == "missing_license" {
        eprintln!("[launcher] no license installed; continuing to activation flow");
        return Ok(());
    }

    Err(PyErr::new::<pyo3::exceptions::PyPermissionError, _>(
        format!("license invalid: {reason}"),
    ))
}

fn constant_time_hex_eq(lhs: &str, rhs: &str) -> bool {
    if lhs.len() != rhs.len() {
        return false;
    }
    lhs.as_bytes()
        .iter()
        .zip(rhs.as_bytes())
        .fold(0u8, |acc, (&l, &r)| acc | (l ^ r))
        == 0
}

fn load_protected_modules(
    bundle_roots: &[PathBuf],
) -> Result<(HashMap<String, Vec<u8>>, Option<PathBuf>)> {
    let mut modules = HashMap::new();
    let mut resolved_root: Option<PathBuf> = None;

    for spec in protected::PROTECTED_MODULES {
        let encrypted = locate_encrypted_payload(bundle_roots, spec.encrypted_name);
        let plaintext = match encrypted {
            Ok((bytes, root)) => {
                if resolved_root.is_none() {
                    resolved_root = root;
                }
                crypto::decrypt_scoped(&bytes, spec.import_name)
                    .with_context(|| format!("decrypt {}", spec.import_name))?
            }
            Err(err) => return Err(err),
        };

        let digest = integrity::sha256_of_bytes(&plaintext);
        if !digest.eq_ignore_ascii_case(spec.expected_sha256) {
            bail!(
                "{}: digest mismatch (expected {}, got {})",
                spec.import_name,
                spec.expected_sha256,
                digest
            );
        }
        std::str::from_utf8(&plaintext)
            .map_err(|_| anyhow!("{} is not valid UTF-8 source", spec.import_name))?;
        modules.insert(spec.import_name.to_string(), plaintext);
    }

    ensure_package_stubs(&mut modules);

    Ok((modules, resolved_root))
}

fn ensure_package_stubs(modules: &mut HashMap<String, Vec<u8>>) {
    use std::collections::{HashMap as Map, HashSet};

    let mut tree: Map<String, HashSet<String>> = Map::new();
    for name in modules.keys() {
        let mut cursor = name.as_str();
        while let Some(idx) = cursor.rfind('.') {
            let parent = &cursor[..idx];
            let child = &cursor[idx + 1..];
            if parent.is_empty() {
                break;
            }
            tree.entry(parent.to_string())
                .or_default()
                .insert(child.to_string());
            cursor = parent;
        }
    }

    for (package, children) in tree {
        modules.entry(package).or_insert_with(|| {
            let mut body = String::from("__all__ = [\n");
            for child in &children {
                body.push_str("    \"");
                body.push_str(child);
                body.push_str("\",\n");
            }
            body.push_str("]\n");
            body.push_str("from pkgutil import extend_path\n");
            body.push_str("if '__path__' in globals():\n");
            body.push_str("    __path__ = extend_path(__path__, __name__)\n");
            body.push_str("else:\n");
            body.push_str("    __path__ = extend_path([], __name__)\n");
            body.into_bytes()
        });
    }
}

fn locate_encrypted_payload(
    roots: &[PathBuf],
    encrypted_name: &str,
) -> Result<(Vec<u8>, Option<PathBuf>)> {
    for root in roots {
        if !root.exists() {
            continue;
        }
        let candidate = root.join(encrypted_name);
        if candidate.exists() {
            let data = fs::read(&candidate)
                .with_context(|| format!("read {}", candidate.to_string_lossy()))?;
            let found_root = candidate
                .parent()
                .map(|p| p.to_path_buf())
                .or_else(|| Some(root.to_path_buf()));
            return Ok((data, found_root));
        }
        for entry in WalkDir::new(root)
            .into_iter()
            .filter_map(|entry| entry.ok())
        {
            if entry.file_name() == encrypted_name {
                let data = fs::read(entry.path())
                    .with_context(|| format!("read {}", entry.path().to_string_lossy()))?;
                let found_root = entry
                    .path()
                    .parent()
                    .map(|p| p.to_path_buf())
                    .or_else(|| Some(root.to_path_buf()));
                return Ok((data, found_root));
            }
        }
    }
    Err(anyhow!(
        "encrypted payload {} not found in {:?}",
        encrypted_name,
        roots
    ))
}

fn candidate_payload_roots(exe_path: &Path) -> Vec<PathBuf> {
    let mut roots = Vec::new();
    if let Ok(custom) = env::var("WIN_PD") {
        roots.push(PathBuf::from(custom));
    }
    if let Some(dir) = exe_path.parent() {
        roots.push(dir.join(protected::PROTECTED_SUBDIR));
        roots.push(dir.to_path_buf());
        if let Some(parent) = dir.parent() {
            roots.push(parent.join("Resources").join(protected::PROTECTED_SUBDIR));
        }
    }
    roots.push(Path::new(protected::SOURCE_ROOT).join("build/protected"));
    roots
}

fn locate_key_manifest(roots: &[PathBuf]) -> Result<Option<key_manifest::KeyManifest>> {
    for root in roots {
        match key_manifest::read_manifest(root) {
            Ok(Some(manifest)) => return Ok(Some(manifest)),
            Ok(None) => continue,
            Err(err) => {
                return Err(
                    err.context(format!("load key manifest from {}", root.to_string_lossy()))
                );
            }
        }
    }
    Ok(None)
}

fn determine_key_source<'a>(
    manifest: Option<&'a key_manifest::KeyManifest>,
    launcher_hash: &'a str,
) -> Result<ModuleKeySource<'a>> {
    match manifest.map(|m| &m.encryption) {
        Some(key_manifest::EncryptionMode::ClientKey { key_id, .. }) => {
            let client_id = key_id
                .as_deref()
                .ok_or_else(|| anyhow!("client manifest missing key_id"))?;
            let key = client_key::derive_runtime_key(launcher_hash, client_id)?;
            Ok(ModuleKeySource::Direct(key))
        }
        _ => Ok(ModuleKeySource::LauncherHash(launcher_hash)),
    }
}

fn bootstrap_python(
    py: Python<'_>,
    modules: &mut HashMap<String, Vec<u8>>,
    args: &LaunchArgs,
    exe_path: &Path,
    token: &str,
) -> PyResult<()> {
    install_memory_importer(py, modules, token)?;

    let sys = py.import_bound("sys")?;
    inherit_bundle_sys_path(py, &sys)?;
    let argv = PyList::new_bound(py, args.argv(exe_path));
    sys.setattr("argv", &argv)?;
    sys.setattr("executable", exe_path.to_string_lossy().as_ref())?;
    sys.setattr("frozen", true)?;

    if let Ok(pyarmor_root) = env::var("WIN_PYARMOR") {
        let sys_path = sys.getattr("path")?.downcast_into::<PyList>()?;
        sys_path.insert(0, pyarmor_root)?;
    }

    // Ensure dev paths remain importable for optional modules.
    if cfg!(debug_assertions) {
        let sys_path = sys.getattr("path")?.downcast_into::<PyList>()?;
        sys_path.insert(
            0,
            Path::new(protected::SOURCE_ROOT).to_string_lossy().as_ref(),
        )?;
    }

    let license_module = py.import_bound("src.common_utils.license_utils")?;
    let status = license_module.call_method1("license_status", ())?;
    enforce_license(&status)?;

    let tray_app = py.import_bound("tray_app")?;

    let args_dict = args.to_pydict(py)?;
    eprintln!(
        "[launcher] invoking tray_app.main (mode={}, host={}, port={})",
        args.mode, args.host, args.port
    );
    tray_app.call_method1("main", (args_dict.as_any(),))?;
    eprintln!("[launcher] tray_app.main returned");
    Ok(())
}

fn install_memory_importer<'py>(
    py: Python<'py>,
    modules: &mut HashMap<String, Vec<u8>>,
    token: &str,
) -> PyResult<()> {
    let module =
        PyModule::from_code_bound(py, MEMORY_IMPORTER, "memory_loader.py", "memory_loader")?;
    let install = module.getattr("install_memory_importer")?;
    let payloads = PyDict::new_bound(py);
    for (name, source) in modules.iter_mut() {
        let py_bytes = PyByteArray::new_bound(py, source.as_slice());
        for b in source.iter_mut() {
            *b = 0;
        }
        payloads.set_item(name, &py_bytes)?;
    }
    modules.clear();
    install.call1((payloads.as_any(), token))?;
    Ok(())
}

fn generate_launch_token() -> String {
    let mut buf = [0u8; 32];
    let mut rng = rng();
    rng.fill_bytes(&mut buf);
    URL_SAFE_NO_PAD.encode(buf)
}

fn inherit_bundle_sys_path(_py: Python<'_>, sys: &Bound<'_, PyModule>) -> PyResult<()> {
    let sys_path = sys.getattr("path")?.downcast_into::<PyList>()?;
    // Prefer paths handed over by the PyInstaller stub so the embedded interpreter
    // can see the same vendored modules. When running the launcher directly in a
    // dev checkout (no WIN_SYSPATH), fall back to the source root so imports like
    // `src.detect_vehicle` and `frontend.app` still resolve.
    if let Ok(raw) = env::var("WIN_SYSPATH") {
        if !raw.trim().is_empty() {
            for path in env::split_paths(&raw) {
                if path.as_os_str().is_empty() {
                    continue;
                }
                let value = path.to_string_lossy();
                sys_path.insert(0, value.as_ref())?;
            }
            return Ok(());
        }
    }

    let source_root = Path::new(protected::SOURCE_ROOT);
    if source_root.exists() {
        sys_path.insert(0, source_root.to_string_lossy().as_ref())?;
    }

    Ok(())
}

#[derive(Debug, Clone)]
struct LaunchArgs {
    mode: String,
    host: String,
    port: u16,
    debug: bool,
    no_autostart: bool,
    no_browser: bool,
    dashboard_url: Option<String>,
    raw: Vec<String>,
}

impl LaunchArgs {
    fn from_env() -> Result<Self> {
        let raw: Vec<String> = env::args().collect();
        let mut args = LaunchArgs {
            mode: "tray".into(),
            host: "127.0.0.1".into(),
            port: 5000,
            debug: false,
            no_autostart: false,
            no_browser: false,
            dashboard_url: None,
            raw,
        };
        args.parse()?;
        Ok(args)
    }

    fn parse(&mut self) -> Result<()> {
        let mut iter = self.raw.iter().skip(1);
        while let Some(arg) = iter.next() {
            match arg.as_str() {
                "--mode" => self.mode = next_value(arg, &mut iter)?,
                "--host" => self.host = next_value(arg, &mut iter)?,
                "--port" => {
                    let value = next_value(arg, &mut iter)?;
                    self.port = value
                        .parse::<u16>()
                        .map_err(|_| anyhow!("--port expects an integer, got {value}"))?;
                }
                "--debug" => self.debug = true,
                "--no-autostart" => self.no_autostart = true,
                "--no-browser" => self.no_browser = true,
                "--dashboard-url" => self.dashboard_url = Some(next_value(arg, &mut iter)?),
                unknown if unknown.starts_with('-') => {
                    return Err(anyhow!("unrecognized argument {unknown}"));
                }
                positional => {
                    return Err(anyhow!("unexpected positional argument {positional}"));
                }
            }
        }
        Ok(())
    }

    fn argv(&self, exe_path: &Path) -> Vec<String> {
        if self.raw.len() > 1 {
            return self.raw.clone();
        }
        let mut argv = vec![exe_path.to_string_lossy().to_string()];
        argv.push("--mode".into());
        argv.push(self.mode.clone());
        argv.push("--host".into());
        argv.push(self.host.clone());
        argv.push("--port".into());
        argv.push(self.port.to_string());
        if self.debug {
            argv.push("--debug".into());
        }
        if self.no_autostart {
            argv.push("--no-autostart".into());
        }
        if self.no_browser {
            argv.push("--no-browser".into());
        }
        if let Some(url) = &self.dashboard_url {
            argv.push("--dashboard-url".into());
            argv.push(url.clone());
        }
        argv
    }

    fn to_pydict<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let dict = PyDict::new_bound(py);
        dict.set_item("mode", &self.mode)?;
        dict.set_item("host", &self.host)?;
        dict.set_item("port", self.port)?;
        dict.set_item("debug", self.debug)?;
        dict.set_item("no_autostart", self.no_autostart)?;
        dict.set_item("no_browser", self.no_browser)?;
        if let Some(url) = &self.dashboard_url {
            dict.set_item("dashboard_url", url)?;
        } else {
            dict.set_item("dashboard_url", py.None())?;
        }
        Ok(dict)
    }
}

fn stage_protected_assets(roots: &[PathBuf]) -> Result<(PathBuf, Option<PathBuf>, CacheGuard)> {
    // Use a stable shared cache so multiple launcher processes reuse the same assets.
    let cache_dir = env::temp_dir().join("win_mlds_shared");
    fs::create_dir_all(&cache_dir)?;
    cleanup_stale_markers(&cache_dir);
    let cache_guard = CacheGuard::new(&cache_dir)?;
    let mut pyarmor_root: Option<PathBuf> = None;

    for spec in protected::PROTECTED_ASSETS {
        let encrypted = locate_encrypted_payload(roots, spec.encrypted_name);
        let plaintext = match encrypted {
            Ok((bytes, _)) => crypto::decrypt_scoped(&bytes, spec.label)
                .with_context(|| format!("decrypt asset {}", spec.label))?,
            Err(err) => return Err(err),
        };
        let digest = integrity::sha256_of_bytes(&plaintext);
        if !digest.eq_ignore_ascii_case(spec.expected_sha256) {
            bail!("asset digest mismatch",);
        }
        let filename = Path::new(spec.plaintext_path)
            .file_name()
            .ok_or_else(|| anyhow!("asset {} missing file name", spec.label))?;
        let target_path = if let Some(stripped) = spec.plaintext_path.strip_prefix("build/pyarmor/")
        {
            pyarmor_root.get_or_insert_with(|| cache_dir.clone());
            cache_dir.join(stripped)
        } else {
            cache_dir.join(filename)
        };
        if let Some(parent) = target_path.parent() {
            fs::create_dir_all(parent)?;
        }
        write_if_missing(&target_path, &plaintext, spec.expected_sha256)?;
    }

    Ok((cache_dir, pyarmor_root, cache_guard))
}

fn write_if_missing(target_path: &Path, contents: &[u8], expected_hash: &str) -> Result<()> {
    // If the existing file matches the expected hash, reuse it to avoid races between processes.
    if target_path.exists() {
        if let Ok(existing) = fs::read(target_path) {
            let digest = integrity::sha256_of_bytes(&existing);
            if digest.eq_ignore_ascii_case(expected_hash) {
                return Ok(());
            }
        }
    }

    let mut last_err = None;
    for _ in 0..4 {
        match fs::write(target_path, contents) {
            Ok(_) => return Ok(()),
            Err(err) => {
                last_err = Some(err);
                thread::sleep(Duration::from_millis(120));
            }
        }
    }

    Err(anyhow!("write {}", target_path.to_string_lossy())
        .context(last_err.map(|e| e.to_string()).unwrap_or_default()))
}

struct CacheGuard {
    cache_dir: PathBuf,
    owner_marker: PathBuf,
}

impl CacheGuard {
    fn new(cache_dir: &Path) -> Result<Self> {
        let owner_marker = cache_dir.join(format!(".owner_{}", process::id()));
        fs::write(&owner_marker, b"")?;
        Ok(Self {
            cache_dir: cache_dir.to_path_buf(),
            owner_marker,
        })
    }
}

impl Drop for CacheGuard {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.owner_marker);
        cleanup_stale_markers(&self.cache_dir);
        // Only remove the cache if no other owners are present.
        if let Ok(entries) = fs::read_dir(&self.cache_dir) {
            let others = entries
                .flatten()
                .any(|e| e.file_name().to_string_lossy().starts_with(".owner_"));
            if !others {
                let _ = fs::remove_dir_all(&self.cache_dir);
            }
        }
    }
}

fn cleanup_stale_markers(cache_dir: &Path) {
    let kind = RefreshKind::new().with_processes(ProcessRefreshKind::everything());
    let mut sys = System::new_with_specifics(kind);
    if let Ok(entries) = fs::read_dir(cache_dir) {
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();
            if !name.starts_with(".owner_") {
                continue;
            }
            let pid_str = name.trim_start_matches(".owner_");
            if let Ok(pid) = pid_str.parse::<u32>() {
                sys.refresh_process(Pid::from_u32(pid));
                if sys.process(Pid::from_u32(pid)).is_none() {
                    let _ = fs::remove_file(entry.path());
                }
            } else {
                let _ = fs::remove_file(entry.path());
            }
        }
    }
}

fn next_value<'a, I>(flag: &str, iter: &mut I) -> Result<String>
where
    I: Iterator<Item = &'a String>,
{
    iter.next()
        .map(|s| s.to_string())
        .ok_or_else(|| anyhow!("{flag} expects a value"))
}
