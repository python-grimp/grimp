use crate::errors::{GrimpError, GrimpResult};
use crate::filesystem::get_file_system_boxed;
use crate::import_scanning::{DirectImport, imports_by_module_to_py};
use crate::module_finding::Module;
use pyo3::types::PyAnyMethods;
use pyo3::types::{PyDict, PySet};
use pyo3::types::{PyDictMethods, PySetMethods};
use pyo3::{Bound, PyAny, PyResult, Python, pyfunction};
use std::collections::{HashMap, HashSet};
use serde_json;

/// Writes the cache file containing all the imports for a given package.
/// Args:
/// - filename: str
/// - imports_by_module: dict[Module, Set[DirectImport]]
/// - file_system: The file system interface to use. (A BasicFileSystem.)
#[pyfunction]
pub fn write_cache_data_map_file<'py>(
    py: Python<'py>,
    filename: &str,
    imports_by_module: Bound<'py, PyDict>,
    file_system: Bound<'py, PyAny>,
) -> PyResult<()> {
    eprintln!("About to clone for write.");
    let mut file_system_boxed = get_file_system_boxed(&file_system)?;

    let imports_by_module_rust = imports_by_module_to_rust(imports_by_module);

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
    eprintln!("About to clone for read.");
    let file_system_boxed = get_file_system_boxed(&file_system)?;

    let file_contents = file_system_boxed.read(filename)?;

    let imports_by_module = parse_json_to_map(&file_contents, filename)?;

    Ok(imports_by_module_to_py(py, imports_by_module))
}

#[allow(unused_variables)]
fn imports_by_module_to_rust(
    imports_by_module_py: Bound<PyDict>,
) -> HashMap<Module, HashSet<DirectImport>> {
    let mut imports_by_module_rust = HashMap::new();

    for (py_key, py_value) in imports_by_module_py.iter() {
        let module: Module = py_key.extract().unwrap();
        let py_set = py_value
            .downcast::<PySet>()
            .expect("Expected value to be a Python set.");
        let mut hashset: HashSet<DirectImport> = HashSet::new();
        for element in py_set.iter() {
            let direct_import: DirectImport = element
                .extract()
                .expect("Expected value to be DirectImport.");
            hashset.insert(direct_import);
        }
        imports_by_module_rust.insert(module, hashset);
    }

    imports_by_module_rust
}

#[allow(unused_variables)]
fn serialize_imports_by_module(
    imports_by_module: &HashMap<Module, HashSet<DirectImport>>,
) -> String {
    let raw_map: HashMap<&str, Vec<(&str, usize, &str)>> = imports_by_module
        .iter()
        .map(|(module, imports)| {
            let imports_vec: Vec<(&str, usize, &str)> = imports
                .iter()
                .map(|import| {
                    (
                        import.imported.as_str(),
                        import.line_number,
                        import.line_contents.as_str(),
                    )
                })
                .collect();
            (module.name.as_str(), imports_vec)
        })
        .collect();

    serde_json::to_string(&raw_map).expect("Failed to serialize to JSON")
}

pub fn parse_json_to_map(
    json_str: &str,
    filename: &str,
) -> GrimpResult<HashMap<Module, HashSet<DirectImport>>> {
    let raw_map: HashMap<String, Vec<(String, usize, String)>> = serde_json::from_str(json_str)
        .map_err(|_| GrimpError::CorruptCache(filename.to_string()))?;

    let mut parsed_map: HashMap<Module, HashSet<DirectImport>> = HashMap::new();

    for (module_name, imports) in raw_map {
        let module = Module {
            name: module_name.clone(),
        };
        let import_set: HashSet<DirectImport> = imports
            .into_iter()
            .map(|(imported, line_number, line_contents)| DirectImport {
                importer: module_name.clone(),
                imported,
                line_number,
                line_contents,
            })
            .collect();
        parsed_map.insert(module, import_set);
    }

    Ok(parsed_map)
}
