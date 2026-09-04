use crate::errors::{GrimpError, GrimpResult};
use crate::filesystem::get_file_system_boxed;
use crate::import_scanning::{DirectImport, imports_by_module_to_py};
use crate::module_finding::Module;
use pyo3::types::PyAnyMethods;
use pyo3::types::{PyDict, PySet};
use pyo3::types::{PyDictMethods, PySetMethods};
use pyo3::{Borrowed, Bound, FromPyObject, PyAny, PyErr, PyResult, Python, pyfunction};
use std::collections::{HashMap, HashSet};

/// Writes the cache file containing all the imports for a given package.
/// Args:
/// - filename: str
/// - imports_by_module: dict[Module, Set[DirectImport]]
/// - file_system: The file system interface to use. (A BasicFileSystem.)
#[pyfunction]
pub fn write_cache_data_map_file<'py>(
    filename: &str,
    imports_by_module: Bound<'py, PyDict>,
    file_system: Bound<'py, PyAny>,
) -> PyResult<()> {
    let mut file_system_boxed = get_file_system_boxed(&file_system)?;

    let ImportsByModule(imports_by_module_rust) = imports_by_module.extract()?;

    let file_contents = serialize_imports_by_module(&imports_by_module_rust);

    file_system_boxed.write(filename, &file_contents)?;

    Ok(())
}

/// Reads the cache file containing all the imports for a given package.
/// Args:
/// - filename: str
/// - file_system: The file system interface to use. (A BasicFileSystem.)
/// Returns Dict[Module, Set[DirectImport]]
#[pyfunction]
pub fn read_cache_data_map_file<'py>(
    py: Python<'py>,
    filename: &str,
    file_system: Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyDict>> {
    let file_system_boxed = get_file_system_boxed(&file_system)?;

    let file_contents = file_system_boxed.read(filename)?;

    let imports_by_module = parse_json_to_map(&file_contents, filename)?;

    Ok(imports_by_module_to_py(py, imports_by_module))
}

/// A newtype wrapper for HashMap<Module, HashSet<DirectImport>> that implements FromPyObject.
pub struct ImportsByModule(pub HashMap<Module, HashSet<DirectImport>>);

impl<'a, 'py> FromPyObject<'a, 'py> for ImportsByModule {
    type Error = PyErr;

    fn extract(ob: Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        let py_dict = ob.cast::<PyDict>()?;
        let mut imports_by_module_rust = HashMap::new();

        for (py_key, py_value) in py_dict.iter() {
            let module: Module = py_key.extract()?;
            let py_set = py_value.cast::<PySet>()?;
            let mut hashset: HashSet<DirectImport> = HashSet::new();
            for element in py_set.iter() {
                let direct_import: DirectImport = element.extract()?;
                hashset.insert(direct_import);
            }
            imports_by_module_rust.insert(module, hashset);
        }

        Ok(ImportsByModule(imports_by_module_rust))
    }
}

/// The version of the data cache file format.
///
/// Bump this whenever the serialized structure changes. On read, a file with a
/// different (or missing) version is treated as a version mismatch and rebuilt,
/// rather than being mistaken for a corrupt file.
const CACHE_SCHEMA_VERSION: u32 = 2;

fn serialize_imports_by_module(
    imports_by_module: &HashMap<Module, HashSet<DirectImport>>,
) -> String {
    // Fields are ordered to match the `get_import_details` dict (`imported`, `is_lazy`,
    // `line_number`, `line_contents`); `importer` is the map key.
    let raw_map: HashMap<&str, Vec<(&str, bool, usize, &str)>> = imports_by_module
        .iter()
        .map(|(module, imports)| {
            let imports_vec: Vec<(&str, bool, usize, &str)> = imports
                .iter()
                .map(|import| {
                    (
                        import.imported.as_str(),
                        import.is_lazy,
                        import.line_number,
                        import.line_contents.as_str(),
                    )
                })
                .collect();
            (module.name.as_str(), imports_vec)
        })
        .collect();

    let envelope = serde_json::json!({
        "version": CACHE_SCHEMA_VERSION,
        "imports_by_module": raw_map,
    });

    serde_json::to_string(&envelope).expect("Failed to serialize to JSON")
}

pub fn parse_json_to_map(
    json_str: &str,
    filename: &str,
) -> GrimpResult<HashMap<Module, HashSet<DirectImport>>> {
    // Parse into a generic value first, so we can distinguish genuinely corrupt
    // JSON from a cache file written by a different format version (e.g. by an
    // older Grimp). The latter should be silently rebuilt, not warned about.
    let value: serde_json::Value = serde_json::from_str(json_str)
        .map_err(|_| GrimpError::CorruptCache(filename.to_string()))?;

    let version = value.get("version").and_then(|v| v.as_u64());
    if version != Some(CACHE_SCHEMA_VERSION as u64) {
        return Err(GrimpError::CacheVersionMismatch(filename.to_string()));
    }

    let raw_map: HashMap<String, Vec<(String, bool, usize, String)>> =
        serde_json::from_value(value.get("imports_by_module").cloned().unwrap_or_default())
            .map_err(|_| GrimpError::CorruptCache(filename.to_string()))?;

    let mut parsed_map: HashMap<Module, HashSet<DirectImport>> = HashMap::new();

    for (module_name, imports) in raw_map {
        let module = Module {
            name: module_name.clone(),
        };
        let import_set: HashSet<DirectImport> = imports
            .into_iter()
            .map(
                |(imported, is_lazy, line_number, line_contents)| DirectImport {
                    importer: module_name.clone(),
                    imported,
                    line_number,
                    line_contents,
                    is_lazy,
                },
            )
            .collect();
        parsed_map.insert(module, import_set);
    }

    Ok(parsed_map)
}
