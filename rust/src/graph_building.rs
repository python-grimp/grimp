use crate::caching::Cache;
use crate::errors::GrimpResult;
use crate::filesystem::real_file_system;
use crate::graph::{Graph, GraphWrapper};
use crate::import_scanning::{DirectImport, into_py_err, scan_for_imports_no_py};
use crate::module_finding::{FoundPackage, Module, find_package};
use pyo3::prelude::*;
use std::collections::{HashMap, HashSet};

/// Builds an import graph of the supplied packages.
///
/// This is the Rust equivalent of `grimp.application.usecases.build_graph`.
///
/// Args:
/// - packages: (name, directory) of each package. A package may have more than one directory.
/// - include_external_packages: whether to include imports of external modules.
/// - exclude_type_checking_imports: whether to exclude imports behind TYPE_CHECKING guards.
/// - cache_dir: the directory to use for caching, or None for no caching.
#[pyfunction]
pub fn build_graph(
    py: Python,
    packages: Vec<(String, String)>,
    include_external_packages: bool,
    exclude_type_checking_imports: bool,
    cache_dir: Option<String>,
) -> PyResult<GraphWrapper> {
    py.detach(|| {
        build_graph_no_py(
            &packages,
            include_external_packages,
            exclude_type_checking_imports,
            cache_dir.as_deref(),
        )
    })
    .map(GraphWrapper::from_graph)
    .map_err(|e| into_py_err(py, e))
}

fn build_graph_no_py(
    packages: &[(String, String)],
    include_external_packages: bool,
    exclude_type_checking_imports: bool,
    cache_dir: Option<&str>,
) -> GrimpResult<Graph> {
    let mut file_system = real_file_system();

    // Find the modules.
    let mut found_packages = HashSet::new();
    let mut mtimes = HashMap::new();
    for (name, directory) in packages {
        let (found_package, package_mtimes) = find_package(name, directory)?;
        found_packages.insert(found_package);
        mtimes.extend(package_mtimes);
    }

    // Read the imports of each module, from the cache if possible, otherwise from the source.
    let cache = cache_dir.map(|directory| {
        Cache::new(
            directory,
            &found_packages,
            include_external_packages,
            exclude_type_checking_imports,
        )
    });
    let mut imports_by_module = match &cache {
        Some(cache) => cache.read(&*file_system, &mtimes),
        None => HashMap::new(),
    };
    let modules_to_scan: HashSet<Module> = found_packages
        .iter()
        .flat_map(|found_package| &found_package.module_files)
        .map(|module_file| module_file.module.clone())
        .filter(|module| !imports_by_module.contains_key(module))
        .collect();
    if !modules_to_scan.is_empty() {
        imports_by_module.extend(scan_for_imports_no_py(
            &file_system,
            &found_packages,
            include_external_packages,
            &modules_to_scan,
            exclude_type_checking_imports,
        )?);
    }
    if let Some(cache) = &cache {
        cache.write(&mut *file_system, &mtimes, &imports_by_module)?;
    }

    Ok(assemble_graph(&found_packages, &imports_by_module))
}

fn assemble_graph(
    found_packages: &HashSet<FoundPackage>,
    imports_by_module: &HashMap<Module, HashSet<DirectImport>>,
) -> Graph {
    let mut graph = Graph::default();

    for found_package in found_packages {
        for namespace_package in &found_package.namespace_packages {
            graph.get_or_add_module(&namespace_package.name);
        }
    }

    let is_external = |module: &str| {
        !found_packages.iter().any(|found_package| {
            module == found_package.name || module.starts_with(&format!("{}.", found_package.name))
        })
    };
    for (module, direct_imports) in imports_by_module {
        let importer = graph.get_or_add_module(&module.name).token();
        for direct_import in direct_imports {
            // External modules are squashed.
            let imported = if is_external(&direct_import.imported) {
                graph.get_or_add_squashed_module(&direct_import.imported)
            } else {
                graph.get_or_add_module(&direct_import.imported)
            }
            .token();
            graph.add_detailed_import(
                importer,
                imported,
                direct_import.line_number as u32,
                &direct_import.line_contents,
                direct_import.is_lazy,
            );
        }
    }
    graph
}
