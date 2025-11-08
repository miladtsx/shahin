pub mod anti_debug;
pub mod beacon;

pub fn guard_operation(label: &str) -> bool {
    if anti_debug::debugger_detected() {
        return false;
    }
    beacon::global().probe(label)
}
