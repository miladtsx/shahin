use rand::{rngs::SmallRng, Rng, SeedableRng};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

static ENGINE: OnceLock<BeaconEngine> = OnceLock::new();

const VERIFIER_PAYLOADS: [&[u8]; 4] = [
    b"perimeter-scout-alpha",
    b"perimeter-scout-beta",
    b"aux-stationary-node",
    b"telemetry-anchor-v3",
];

const VERIFIER_HASHES: [&str; 4] = [
    "b1c6fa5b68380c808717c732a0f83a074160705d8f4486ee5cb0d20b114779d6",
    "b22f20b0df2a1e8eaeb602e82abe6bd38eb67aa62120b7e76fed9c7823022139",
    "c3fbb88ba90a858df92b3c6d3f423c1bdb61c88f206f9f1b6ccc11a79f3d097b",
    "2ed8a642911b3759442ee6bdc9fe246786b74f0491385ea25cbafa70fcc4c610",
];

pub struct BeaconEngine {
    rng: Mutex<SmallRng>,
    tripped: AtomicBool,
}

impl BeaconEngine {
    fn new() -> Self {
        let seed = seed_from_entropy();
        Self {
            rng: Mutex::new(SmallRng::seed_from_u64(seed)),
            tripped: AtomicBool::new(false),
        }
    }

    fn should_probe(&self, label: &str) -> bool {
        let mut rng = match self.rng.lock() {
            Ok(guard) => guard,
            Err(poisoned) => poisoned.into_inner(),
        };
        let base_roll: u8 = rng.random_range(0..100);
        let entropy = label_entropy(label) as u8;
        base_roll < 35 || entropy.wrapping_add(base_roll) % 3 == 0
    }

    fn verify_constant(&self, label: &str) -> bool {
        let entropy = label_entropy(label) as usize;
        let mut rng = match self.rng.lock() {
            Ok(guard) => guard,
            Err(poisoned) => poisoned.into_inner(),
        };
        let roll = rng.random_range(0..VERIFIER_PAYLOADS.len());
        let idx = (roll + entropy) % VERIFIER_PAYLOADS.len();
        let payload = VERIFIER_PAYLOADS[idx];
        let expected = VERIFIER_HASHES[idx];
        crate::sha256_hex(payload).eq_ignore_ascii_case(expected)
    }

    pub fn probe(&self, label: &str) -> bool {
        if self.is_tripped() {
            return false;
        }
        if !self.should_probe(label) {
            return true;
        }
        let ok = self.verify_constant(label);
        if !ok {
            self.tripped.store(true, Ordering::Relaxed);
        }
        ok
    }

    pub fn is_tripped(&self) -> bool {
        self.tripped.load(Ordering::Relaxed)
    }
}

pub fn global() -> &'static BeaconEngine {
    ENGINE.get_or_init(BeaconEngine::new)
}

#[cfg(test)]
impl BeaconEngine {
    pub fn force_trip(&self) {
        self.tripped.store(true, Ordering::Relaxed);
    }

    pub fn reset(&self) {
        self.tripped.store(false, Ordering::Relaxed);
    }
}

fn seed_from_entropy() -> u64 {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos() as u64)
        .unwrap_or(0);
    let pid = std::process::id() as u64;
    nanos ^ (pid.rotate_left(13))
}

fn label_entropy(label: &str) -> u64 {
    let mut hasher = DefaultHasher::new();
    label.hash(&mut hasher);
    hasher.finish()
}
