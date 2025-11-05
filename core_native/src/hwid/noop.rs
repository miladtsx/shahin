use super::HwidCollector;

#[derive(Default)]
pub struct NoopCollector;

impl HwidCollector for NoopCollector {
    fn collect(&self) -> Vec<String> {
        Vec::new()
    }
}
