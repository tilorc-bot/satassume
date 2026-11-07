//! Reads section 9's offline data file, once at load. It's written by `gen_offline_data.py`, which is not ported.
//! Refuses the file on any hash or format mismatch: nothing here falls back to a guess.
//!
//! The JSON reader and the SHA-256 are local because the crate takes no dependency for them, and the input is this one
//! canonical form: ASCII, no spaces, objects in file order. `Json::write` gives the same bytes back, which is how the
//! round-trip test shows the whole file was read.
use std::fmt::Write as _;

pub const FORMAT: i64 = 1;

#[derive(Clone, Debug, PartialEq)]
pub enum Json {
    Null,
    Bool(bool),
    Int(i64),
    Str(String),
    List(Vec<Json>),
    /// In file order, which is the mapping's insertion order in Python.
    Obj(Vec<(String, Json)>),
}

impl Json {
    pub fn get(&self, key: &str) -> Option<&Json> {
        match self {
            Json::Obj(items) => items.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }

    pub fn as_str(&self) -> Option<&str> {
        match self {
            Json::Str(s) => Some(s),
            _ => None,
        }
    }

    pub fn as_int(&self) -> Option<i64> {
        match self {
            Json::Int(i) => Some(*i),
            _ => None,
        }
    }

    pub fn as_list(&self) -> Option<&[Json]> {
        match self {
            Json::List(l) => Some(l),
            _ => None,
        }
    }

    pub fn write(&self, out: &mut String) {
        match self {
            Json::Null => out.push_str("null"),
            Json::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
            Json::Int(i) => {
                let _ = write!(out, "{i}");
            }
            Json::Str(s) => write_str(s, out),
            Json::List(l) => {
                out.push('[');
                for (i, x) in l.iter().enumerate() {
                    if i > 0 {
                        out.push(',');
                    }
                    x.write(out);
                }
                out.push(']');
            }
            Json::Obj(items) => {
                out.push('{');
                for (i, (k, v)) in items.iter().enumerate() {
                    if i > 0 {
                        out.push(',');
                    }
                    write_str(k, out);
                    out.push(':');
                    v.write(out);
                }
                out.push('}');
            }
        }
    }
}

/// As Python's `json.dumps` with `ensure_ascii=True`.
fn write_str(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            c if (c as u32) < 0x20 || (c as u32) >= 0x7f => {
                let mut b = [0u16; 2];
                for u in c.encode_utf16(&mut b) {
                    let _ = write!(out, "\\u{:04x}", u);
                }
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

struct Reader<'a> {
    b: &'a [u8],
    i: usize,
}

impl Reader<'_> {
    fn err<T>(&self, what: &str) -> Result<T, String> {
        Err(format!("{what} at byte {}", self.i))
    }

    fn value(&mut self) -> Result<Json, String> {
        match self.b.get(self.i) {
            None => self.err("end of input"),
            Some(b'n') => self.word("null", Json::Null),
            Some(b't') => self.word("true", Json::Bool(true)),
            Some(b'f') => self.word("false", Json::Bool(false)),
            Some(b'"') => Ok(Json::Str(self.string()?)),
            Some(b'[') => {
                self.i += 1;
                let mut l = Vec::new();
                if self.b.get(self.i) == Some(&b']') {
                    self.i += 1;
                    return Ok(Json::List(l));
                }
                loop {
                    l.push(self.value()?);
                    match self.b.get(self.i) {
                        Some(b',') => self.i += 1,
                        Some(b']') => {
                            self.i += 1;
                            return Ok(Json::List(l));
                        }
                        _ => return self.err("expected , or ]"),
                    }
                }
            }
            Some(b'{') => {
                self.i += 1;
                let mut items = Vec::new();
                if self.b.get(self.i) == Some(&b'}') {
                    self.i += 1;
                    return Ok(Json::Obj(items));
                }
                loop {
                    let k = self.string()?;
                    if self.b.get(self.i) != Some(&b':') {
                        return self.err("expected :");
                    }
                    self.i += 1;
                    items.push((k, self.value()?));
                    match self.b.get(self.i) {
                        Some(b',') => self.i += 1,
                        Some(b'}') => {
                            self.i += 1;
                            return Ok(Json::Obj(items));
                        }
                        _ => return self.err("expected , or }"),
                    }
                }
            }
            Some(c) if *c == b'-' || c.is_ascii_digit() => {
                let start = self.i;
                self.i += 1;
                while self.b.get(self.i).is_some_and(|c| c.is_ascii_digit()) {
                    self.i += 1;
                }
                let text = std::str::from_utf8(&self.b[start..self.i]).map_err(|e| e.to_string())?;
                text.parse().map(Json::Int).map_err(|_| format!("not an i64: {text}"))
            }
            Some(_) => self.err("unexpected byte"),
        }
    }

    fn word(&mut self, w: &str, v: Json) -> Result<Json, String> {
        if self.b[self.i..].starts_with(w.as_bytes()) {
            self.i += w.len();
            Ok(v)
        } else {
            self.err("bad word")
        }
    }

    fn hex4(&mut self) -> Result<u32, String> {
        let end = self.i + 4;
        let h = self.b.get(self.i..end).ok_or("short \\u")?;
        let v = std::str::from_utf8(h).ok().and_then(|h| u32::from_str_radix(h, 16).ok()).ok_or("bad \\u")?;
        self.i = end;
        Ok(v)
    }

    fn string(&mut self) -> Result<String, String> {
        if self.b.get(self.i) != Some(&b'"') {
            return self.err("expected a string");
        }
        self.i += 1;
        let mut s = String::new();
        loop {
            let c = *self.b.get(self.i).ok_or("open string")?;
            self.i += 1;
            match c {
                b'"' => return Ok(s),
                b'\\' => {
                    let e = *self.b.get(self.i).ok_or("open escape")?;
                    self.i += 1;
                    match e {
                        b'"' => s.push('"'),
                        b'\\' => s.push('\\'),
                        b'/' => s.push('/'),
                        b'n' => s.push('\n'),
                        b'r' => s.push('\r'),
                        b't' => s.push('\t'),
                        b'b' => s.push('\u{8}'),
                        b'f' => s.push('\u{c}'),
                        b'u' => {
                            let mut u = self.hex4()?;
                            if (0xd800..0xdc00).contains(&u) {
                                if self.b.get(self.i..self.i + 2) != Some(b"\\u") {
                                    return self.err("lone surrogate");
                                }
                                self.i += 2;
                                u = 0x10000 + ((u - 0xd800) << 10) + (self.hex4()? - 0xdc00);
                            }
                            s.push(char::from_u32(u).ok_or("bad code point")?);
                        }
                        _ => return self.err("bad escape"),
                    }
                }
                c if c < 0x80 => s.push(c as char),
                _ => return self.err("not ASCII"),
            }
        }
    }
}

pub fn parse(b: &[u8]) -> Result<Json, String> {
    let mut r = Reader { b, i: 0 };
    let v = r.value()?;
    if r.i != b.len() {
        return r.err("trailing bytes");
    }
    Ok(v)
}

const K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98,
    0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8,
    0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819,
    0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
    0xc67178f2,
];

/// SHA-256, as lowercase hex.
pub fn sha256(data: &[u8]) -> String {
    let mut h: [u32; 8] =
        [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
    let mut msg = data.to_vec();
    msg.push(0x80);
    while msg.len() % 64 != 56 {
        msg.push(0);
    }
    msg.extend_from_slice(&((data.len() as u64) * 8).to_be_bytes());
    let mut w = [0u32; 64];
    for chunk in msg.chunks_exact(64) {
        for (i, b) in chunk.chunks_exact(4).enumerate() {
            w[i] = u32::from_be_bytes([b[0], b[1], b[2], b[3]]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16].wrapping_add(s0).wrapping_add(w[i - 7]).wrapping_add(s1);
        }
        let mut v = h;
        for i in 0..64 {
            let s1 = v[4].rotate_right(6) ^ v[4].rotate_right(11) ^ v[4].rotate_right(25);
            let ch = (v[4] & v[5]) ^ (!v[4] & v[6]);
            let t1 = v[7].wrapping_add(s1).wrapping_add(ch).wrapping_add(K[i]).wrapping_add(w[i]);
            let s0 = v[0].rotate_right(2) ^ v[0].rotate_right(13) ^ v[0].rotate_right(22);
            let maj = (v[0] & v[1]) ^ (v[0] & v[2]) ^ (v[1] & v[2]);
            let t2 = s0.wrapping_add(maj);
            v = [t1.wrapping_add(t2), v[0], v[1], v[2], v[3].wrapping_add(t1), v[4], v[5], v[6]];
        }
        for i in 0..8 {
            h[i] = h[i].wrapping_add(v[i]);
        }
    }
    let mut out = String::with_capacity(64);
    for x in h {
        let _ = write!(out, "{x:08x}");
    }
    out
}

pub struct OfflineData {
    pub body: Json,
    pub header: Json,
    body_text_len: usize,
}

impl OfflineData {
    /// `sources_root`: the tree holding the sources the file names, each of which must still hash as recorded.
    /// `sympy`: this process's SymPy version, since some of the data came from SymPy.
    pub fn load(path: &str, sources_root: &str, sympy: &str) -> Result<OfflineData, String> {
        let bytes = std::fs::read(path).map_err(|e| format!("{path}: {e}"))?;
        let nl = bytes.iter().position(|c| *c == b'\n').ok_or("no header line")?;
        let rest = &bytes[nl + 1..];
        let text = rest.strip_suffix(b"\n").ok_or("no final newline")?;
        let header = parse(&bytes[..nl])?;
        let field = |k: &str| header.get(k).ok_or_else(|| format!("header has no {k}"));
        if field("format")?.as_int() != Some(FORMAT) {
            return Err(format!("format is not {FORMAT}"));
        }
        let made_by = field("sympy")?.as_str().ok_or("sympy is not text")?;
        if made_by != sympy {
            return Err(format!("written under SymPy {made_by}, running {sympy}"));
        }
        if field("body_sha256")?.as_str() != Some(sha256(text).as_str()) {
            return Err("body hash mismatch".to_string());
        }
        let sources = field("sources")?;
        let mut listed = String::new();
        sources.write(&mut listed);
        if field("sources_sha256")?.as_str() != Some(sha256(listed.as_bytes()).as_str()) {
            return Err("sources hash mismatch".to_string());
        }
        for row in sources.as_list().ok_or("sources is not a list")? {
            let row = row.as_list().ok_or("bad source row")?;
            let rel = row.first().and_then(Json::as_str).ok_or("bad source row")?;
            let want = row.get(1).and_then(Json::as_str).ok_or("bad source row")?;
            let got = std::fs::read(format!("{sources_root}/{rel}")).map_err(|e| format!("{rel}: {e}"))?;
            if sha256(&got) != want {
                return Err(format!("{rel} has changed since the file was written"));
            }
        }
        Ok(OfflineData { body: parse(text)?, header, body_text_len: text.len() })
    }

    /// The body written back: the same bytes as the file's, if everything was read.
    pub fn roundtrip(&self) -> String {
        let mut s = String::with_capacity(self.body_text_len);
        self.body.write(&mut s);
        s
    }

    /// The basis predicates in `BASIS_INDEX` order, for a component that needs them.
    pub fn basis(&self) -> Option<Vec<&str>> {
        self.body.get("rules")?.get("BASIS")?.as_list()?.iter().map(Json::as_str).collect()
    }
}
