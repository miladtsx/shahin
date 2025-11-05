#[cfg(target_os = "linux")]
mod linux;
#[cfg(not(any(target_os = "linux", target_os = "windows")))]
mod noop;
#[cfg(target_os = "windows")]
mod windows;

/// Trait implemented by platform-specific collectors to fetch hardware signals.
pub trait HwidCollector {
    fn collect(&self) -> Vec<String>;
}

/// Factory object that constructs the appropriate collector for the current OS.
pub struct HwidCollectorFactory;

impl HwidCollectorFactory {
    pub fn for_current_platform() -> Box<dyn HwidCollector> {
        build_for_current_platform()
    }
}

pub fn collect_hwid_signals() -> Vec<String> {
    HwidCollectorFactory::for_current_platform().collect()
}

#[cfg(target_os = "windows")]
fn build_for_current_platform() -> Box<dyn HwidCollector> {
    Box::new(windows::WindowsCollector::default())
}

#[cfg(target_os = "linux")]
fn build_for_current_platform() -> Box<dyn HwidCollector> {
    Box::new(linux::LinuxCollector::default())
}

#[cfg(not(any(target_os = "linux", target_os = "windows")))]
fn build_for_current_platform() -> Box<dyn HwidCollector> {
    Box::new(noop::NoopCollector::default())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(target_os = "windows")]
    const EXPECTED_SIGNAL_COUNT: usize = 5;
    #[cfg(target_os = "linux")]
    const EXPECTED_SIGNAL_COUNT: usize = 3;
    #[cfg(not(any(target_os = "windows", target_os = "linux")))]
    const EXPECTED_SIGNAL_COUNT: usize = 0;

    #[test]
    fn factory_returns_platform_collector() {
        let signals = collect_hwid_signals();
        assert_eq!(signals.len(), EXPECTED_SIGNAL_COUNT);
    }
}
