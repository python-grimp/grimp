use crate::errors::{GrimpError, GrimpResult};
use regex::Regex;
use std::fs;
use std::fs::File;
use std::io::prelude::*;
use std::path::{Path, PathBuf};
use std::sync::LazyLock;

static ENCODING_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^[ \t\f]*#.*?coding[:=][ \t]*([-_.a-zA-Z0-9]+)").unwrap());

/// An encoding named in a Python source file's encoding declaration.
enum Encoding {
    /// True Latin-1 (ISO-8859-1): a straight byte-to-code-point mapping. This is handled
    /// specially because encoding_rs follows the WHATWG standard, under which the `iso-8859-1`
    /// label resolves to the Windows-1252 decoder instead (the two differ in the 0x80..=0x9f
    /// range), and because Windows-1252 has undefined bytes that true Latin-1 decodes fine.
    Latin1,
    /// Any other encoding, delegated to encoding_rs.
    Other(&'static encoding_rs::Encoding),
}

/// Look up the encoding named in a Python source file's encoding declaration.
///
/// encoding_rs only knows the WHATWG labels, but Python accepts other spellings too, such as
/// `latin-1`, `utf_8`, `utf-8-sig` or `euc_jp`.
fn lookup_encoding(name: &str) -> Option<Encoding> {
    // Normalize the name like Python does: see `_get_normal_name` in Lib/tokenize.py, which
    // special cases UTF-8 and Latin-1. Python's codec lookup also ignores the difference
    // between underscores and hyphens.
    //
    // We check these special cases before deferring to encoding_rs, because some of the Latin-1
    // aliases (e.g. `iso-8859-1`) are WHATWG labels that encoding_rs would otherwise resolve to
    // the Windows-1252 decoder.
    let normalized = name.to_ascii_lowercase().replace('_', "-");
    let is_spelling_of = |canonical: &str| {
        normalized == canonical || normalized.starts_with(&format!("{canonical}-"))
    };
    if ["latin-1", "iso-8859-1", "iso-latin-1"]
        .into_iter()
        .any(is_spelling_of)
    {
        return Some(Encoding::Latin1);
    }
    if is_spelling_of("utf-8") {
        return encoding_rs::Encoding::for_label(b"utf-8").map(Encoding::Other);
    }
    // Try the name as given, then its normalized form.
    encoding_rs::Encoding::for_label(name.as_bytes())
        .or_else(|| encoding_rs::Encoding::for_label(normalized.as_bytes()))
        .map(Encoding::Other)
}

pub trait FileSystem: Send + Sync {
    fn join(&self, components: Vec<String>) -> String;

    fn split(&self, file_name: &str) -> (String, String);

    fn exists(&self, file_name: &str) -> bool;

    fn read(&self, file_name: &str) -> GrimpResult<String>;

    fn write(&mut self, file_name: &str, contents: &str) -> GrimpResult<()>;
}

/// A file system that actually reads and writes files.
struct RealFileSystem {}

impl FileSystem for RealFileSystem {
    fn join(&self, components: Vec<String>) -> String {
        let mut path = PathBuf::new();
        for component in components {
            path.push(component);
        }
        path.to_str()
            .expect("Path components should be valid unicode")
            .to_string()
    }

    fn split(&self, file_name: &str) -> (String, String) {
        let path = Path::new(file_name);

        // Get the "tail" part (the file name or last directory)
        let tail = match path.file_name() {
            Some(name) => PathBuf::from(name),
            None => PathBuf::new(), // If there's no file name (e.g., path is a root), return empty
        };

        // Get the "head" part (the parent directory)
        let head = match path.parent() {
            Some(parent_path) => parent_path.to_path_buf(),
            None => PathBuf::new(), // If there's no parent (e.g., just a filename), return empty
        };

        (
            head.to_str()
                .expect("Path components should be valid unicode")
                .to_string(),
            tail.to_str()
                .expect("Path components should be valid unicode")
                .to_string(),
        )
    }

    fn exists(&self, file_name: &str) -> bool {
        Path::new(file_name).is_file()
    }

    fn read(&self, file_name: &str) -> GrimpResult<String> {
        // Python files are assumed UTF-8 by default (PEP 686), but they can specify an alternative
        // encoding, which we need to take into account here.
        // See https://peps.python.org/pep-0263/

        // This method was authored primarily by an LLM.

        let path = Path::new(file_name);
        let bytes = fs::read(path).map_err(|e| {
            GrimpError::FileNotFound(format!("Failed to read file {file_name}: {e}"))
        })?;

        let s = String::from_utf8_lossy(&bytes);

        let mut detected_encoding: Option<String> = None;

        // Coding specification needs to be in the first two lines, or it's ignored.
        for line in s.lines().take(2) {
            if let Some(captures) = ENCODING_RE.captures(line)
                && let Some(encoding_name) = captures.get(1)
            {
                detected_encoding = Some(encoding_name.as_str().to_string());
                break;
            }
        }

        if let Some(enc_name) = detected_encoding {
            let encoding = lookup_encoding(&enc_name).ok_or_else(|| {
                GrimpError::UndecodableFile(format!(
                    "Failed to decode file {file_name} (unknown encoding '{enc_name}')"
                ))
            })?;
            match encoding {
                // True Latin-1 maps every byte to the code point of the same value and so can
                // never fail.
                Encoding::Latin1 => Ok(bytes.iter().map(|&b| b as char).collect()),
                Encoding::Other(encoding) => {
                    let (decoded_s, _, had_errors) = encoding.decode(&bytes);
                    if had_errors {
                        Err(GrimpError::UndecodableFile(format!(
                            "Failed to decode file {file_name} with encoding '{enc_name}'"
                        )))
                    } else {
                        Ok(decoded_s.into_owned())
                    }
                }
            }
        } else {
            // Default to UTF-8 if no encoding is specified
            String::from_utf8(bytes).map_err(|e| {
                GrimpError::UndecodableFile(format!(
                    "Failed to decode file {file_name} as UTF-8: {e}"
                ))
            })
        }
    }

    fn write(&mut self, file_name: &str, contents: &str) -> GrimpResult<()> {
        let file_path: PathBuf = file_name.into();
        if let Some(patent_dir) = file_path.parent() {
            fs::create_dir_all(patent_dir)?;
        }
        File::create(file_path)?.write_all(contents.as_bytes())?;
        Ok(())
    }
}

pub fn real_file_system() -> Box<dyn FileSystem + Send + Sync> {
    Box::new(RealFileSystem {})
}
