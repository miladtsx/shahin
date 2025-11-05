use std::fs;
use std::io::Read;
use std::path::Path;

use super::HwidCollector;

#[derive(Default)]
pub struct LinuxCollector;

impl HwidCollector for LinuxCollector {
    fn collect(&self) -> Vec<String> {
        vec![machine_id(), product_uuid(), macs_joined()]
    }
}

fn machine_id() -> String {
    read_trimmed("/etc/machine-id")
}

fn product_uuid() -> String {
    read_trimmed("/sys/class/dmi/id/product_uuid")
}

fn macs_joined() -> String {
    let paths = match fs::read_dir("/sys/class/net") {
        Ok(entries) => entries,
        Err(_) => return String::new(),
    };

    let mut macs = Vec::new();

    for entry in paths.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }

        if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
            if name == "lo" {
                continue;
            }
        }

        let address_path = path.join("address");
        let mac = read_trimmed_path(&address_path);
        if !mac.is_empty() {
            macs.push(mac);
        }
    }

    if macs.is_empty() {
        String::new()
    } else {
        macs.join(",")
    }
}

fn read_trimmed(path: &str) -> String {
    read_trimmed_path(Path::new(path))
}

fn read_trimmed_path(path: &Path) -> String {
    let mut file = match fs::File::open(path) {
        Ok(f) => f,
        Err(_) => return String::new(),
    };

    let mut contents = String::new();
    if file.read_to_string(&mut contents).is_err() {
        return String::new();
    }

    contents.trim().to_owned()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn collects_expected_signal_count() {
        let collector = LinuxCollector::default();
        let signals = collector.collect();
        assert_eq!(signals.len(), 3);
    }

    #[test]
    fn read_trimmed_path_strips_whitespace() {
        let temp_path = std::env::temp_dir().join(format!(
            "hwid_test_trimmed_{}_{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::SystemTime::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));

        fs::write(&temp_path, "value-with-newline\n").expect("write temp file");
        let read_back = read_trimmed_path(&temp_path);
        fs::remove_file(&temp_path).ok();

        assert_eq!(read_back, "value-with-newline");
    }
}
