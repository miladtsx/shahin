use std::sync::atomic::{AtomicBool, Ordering};

static DEBUGGER_DETECTED: AtomicBool = AtomicBool::new(false);

pub fn debugger_detected() -> bool {
    if DEBUGGER_DETECTED.load(Ordering::Relaxed) {
        return true;
    }
    let detected = platform_debugger_check();
    if detected {
        DEBUGGER_DETECTED.store(true, Ordering::Relaxed);
    }
    detected
}

#[cfg(target_os = "windows")]
fn platform_debugger_check() -> bool {
    unsafe { is_debugger_present() }
}

#[cfg(target_os = "windows")]
unsafe fn is_debugger_present() -> bool {
    extern "system" {
        fn IsDebuggerPresent() -> i32;
    }
    IsDebuggerPresent() != 0
}

#[cfg(any(target_os = "linux", target_os = "android"))]
fn platform_debugger_check() -> bool {
    tracer_pid_from_status() > 0
}

#[cfg(any(target_os = "linux", target_os = "android"))]
fn tracer_pid_from_status() -> i32 {
    use std::fs;

    if let Ok(status) = fs::read_to_string("/proc/self/status") {
        for line in status.lines() {
            if let Some(rest) = line.strip_prefix("TracerPid:") {
                return rest.trim().parse::<i32>().unwrap_or(0);
            }
        }
    }
    0
}

#[cfg(not(any(
    target_os = "linux",
    target_os = "android",
    target_os = "macos",
    target_os = "windows"
)))]
fn platform_debugger_check() -> bool {
    false
}
