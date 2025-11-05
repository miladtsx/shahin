use std::process::Command;

use winreg::RegKey;
use winreg::enums::HKEY_LOCAL_MACHINE;

use super::HwidCollector;

#[derive(Default)]
pub struct WindowsCollector;

impl HwidCollector for WindowsCollector {
    fn collect(&self) -> Vec<String> {
        vec![
            win_os_install_id(),
            win_machine_guid(),
            disk_serial0(),
            cpu_id(),
            macs_joined(),
        ]
    }
}

fn win_os_install_id() -> String {
    read_reg_string(
        "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion",
        "ProductId",
    )
    .unwrap_or_default()
}

fn win_machine_guid() -> String {
    read_reg_string("SOFTWARE\\Microsoft\\Cryptography", "MachineGuid").unwrap_or_default()
}

fn disk_serial0() -> String {
    powershell_eval(
        "(Get-CimInstance -ClassName Win32_DiskDrive \
         | Select-Object -First 1 -ExpandProperty SerialNumber) -replace '\\s',''",
    )
    .unwrap_or_default()
}

fn cpu_id() -> String {
    powershell_eval(
        "(Get-CimInstance -ClassName Win32_Processor \
         | Select-Object -First 1 -ExpandProperty ProcessorId)",
    )
    .unwrap_or_default()
}

fn macs_joined() -> String {
    powershell_eval(
        "[string]::Join(',', (Get-CimInstance -ClassName Win32_NetworkAdapter \
         | Where-Object { $_.PhysicalAdapter -and $_.MACAddress } \
         | Select-Object -ExpandProperty MACAddress))",
    )
    .unwrap_or_default()
}

fn read_reg_string(path: &str, value: &str) -> Option<String> {
    let root = RegKey::predef(HKEY_LOCAL_MACHINE);
    let subkey = root.open_subkey(path).ok()?;
    subkey
        .get_value::<String, _>(value)
        .ok()
        .map(|v| v.trim().to_owned())
}

fn powershell_eval(script: &str) -> Option<String> {
    let output = Command::new("powershell.exe")
        .args(["-NoLogo", "-NoProfile", "-Command", script])
        .output()
        .ok()?;

    if !output.status.success() {
        return None;
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let trimmed = stdout.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_owned())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn collects_expected_signal_count() {
        let collector = WindowsCollector::default();
        let signals = collector.collect();
        assert_eq!(signals.len(), 5);
    }
}
