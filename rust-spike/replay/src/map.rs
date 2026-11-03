//! The hash map of the memos: std's SipHash in the first honest port, a multiplicative hash with `--features fxhash`.
#[cfg(not(feature = "fxhash"))]
pub type Map<K, V> = std::collections::HashMap<K, V>;

#[cfg(feature = "fxhash")]
pub type Map<K, V> = std::collections::HashMap<K, V, std::hash::BuildHasherDefault<Fx>>;

#[cfg(feature = "fxhash")]
#[derive(Default)]
pub struct Fx(u64);

#[cfg(feature = "fxhash")]
impl std::hash::Hasher for Fx {
    fn write(&mut self, bytes: &[u8]) {
        for c in bytes.chunks(8) {
            let mut b = [0u8; 8];
            b[..c.len()].copy_from_slice(c);
            self.write_u64(u64::from_le_bytes(b));
        }
    }
    fn write_u64(&mut self, x: u64) {
        self.0 = (self.0.rotate_left(5) ^ x).wrapping_mul(0x517c_c1b7_2722_0a95);
    }
    fn write_u128(&mut self, x: u128) {
        self.write_u64(x as u64);
        self.write_u64((x >> 64) as u64);
    }
    fn write_i32(&mut self, x: i32) {
        self.write_u64(x as u32 as u64);
    }
    fn finish(&self) -> u64 {
        self.0
    }
}
