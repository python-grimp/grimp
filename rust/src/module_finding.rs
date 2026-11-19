use crate::errors::GrimpResult;
use pyo3::{prelude::*, types::PyFrozenSet};
use std::collections::{BTreeSet, HashMap};
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::UNIX_EPOCH;

#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord, FromPyObject)]
pub struct ModuleFile {
    pub module: Module,
}

/// A Python module.
/// The string is the importable name, e.g. "mypackage.foo".
#[derive(Debug, Clone, PartialEq, PartialOrd, Ord, Eq, Hash, FromPyObject)]
pub struct Module {
    pub name: String,
}

impl fmt::Display for Module {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{}", self.name)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
/// Set of modules found under a single package, together with metadata.
pub struct FoundPackage {
    pub name: String,
    pub directory: String,
    // BTreeSet rather than HashSet is necessary to make FoundPackage hashable.
    pub module_files: BTreeSet<ModuleFile>,
    pub namespace_packages: BTreeSet<Module>,
}

/// Implements conversion from a Python 'FoundPackage' object to the Rust 'FoundPackage' struct.
/// It extracts 'name', 'directory', and converts the 'module_files' frozenset into a Rust BTreeSet.
impl<'a, 'py> FromPyObject<'a, 'py> for FoundPackage {
    type Error = PyErr;

    fn extract(ob: Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        let name: String = ob.getattr("name")?.extract()?;
        // Extract the 'directory' attribute.
        let directory: String = ob.getattr("directory")?.extract()?;

        // Access the 'module_files' attribute.
        let module_files_py = ob.getattr("module_files")?;
        // Downcast the PyAny object to a PyFrozenSet, as Python 'FrozenSet' maps to 'PyFrozenSet'.
        let module_files_frozenset = module_files_py.cast::<PyFrozenSet>()?;

        let mut module_files = BTreeSet::new();
        // Iterate over the Python frozenset.
        for py_module_file_any in module_files_frozenset.iter() {
            // Extract each element (PyAny) into a Rust 'ModuleFile'.
            let module_file: ModuleFile = py_module_file_any.extract()?;
            module_files.insert(module_file);
        }

        // Access the 'namespace_packages' attribute.
        let namespace_packages_py = ob.getattr("namespace_packages")?;
        // Downcast the PyAny object to a PyFrozenSet, as Python 'FrozenSet' maps to 'PyFrozenSet'.
        let namespace_packages_frozenset = namespace_packages_py.cast::<PyFrozenSet>()?;

        let mut namespace_packages = BTreeSet::new();
        // Iterate over the Python frozenset.
        for py_namespace_any in namespace_packages_frozenset.iter() {
            // Extract each element (PyAny) into a Rust 'ModuleFile'.
            let namespace_package: String = py_namespace_any.extract()?;
            namespace_packages.insert(Module {
                name: namespace_package,
            });
        }

        Ok(FoundPackage {
            name,
            directory,
            module_files,
            namespace_packages,
        })
    }
}

/// Finds the modules and namespace packages inside a package directory.
///
/// This is a port of `grimp.adaptors.modulefinder.ModuleFinder`.
///
/// Also returns the mtime of each module's file (keyed by module name), in the same form as
/// Python's `os.path.getmtime`, so that it's interchangeable with the Python cache.
pub fn find_package(
    name: &str,
    directory: &str,
) -> GrimpResult<(FoundPackage, HashMap<String, f64>)> {
    let mut python_files = vec![];
    let mut namespace_dirs = vec![];
    walk(
        Path::new(directory),
        false,
        &mut python_files,
        &mut namespace_dirs,
    )?;

    let module_name = |path: &Path| -> String {
        let relative_path = path.strip_prefix(directory).unwrap();
        let mut components = vec![name.to_string()];
        components.extend(
            relative_path
                .iter()
                .map(|c| c.to_string_lossy().into_owned()),
        );
        if components.last().unwrap() == "__init__" {
            components.pop();
        }
        components.join(".")
    };

    let mut module_files = BTreeSet::new();
    let mut mtimes = HashMap::new();
    for path in &python_files {
        let module = Module {
            name: module_name(&path.with_extension("")),
        };
        mtimes.insert(module.name.clone(), mtime(path)?);
        module_files.insert(ModuleFile { module });
    }
    let namespace_packages = namespace_dirs
        .iter()
        .map(|dir| Module {
            name: module_name(dir),
        })
        .collect();

    let found_package = FoundPackage {
        name: name.to_string(),
        directory: directory.to_string(),
        module_files,
        namespace_packages,
    };
    Ok((found_package, mtimes))
}

/// Recursively collects the Python files and namespace directories within a directory.
///
/// A directory is a namespace directory if it isn't (within) a regular package, but does
/// contain Python files somewhere below it.
fn walk(
    directory: &Path,
    in_regular_package: bool,
    python_files: &mut Vec<PathBuf>,
    namespace_dirs: &mut Vec<PathBuf>,
) -> GrimpResult<()> {
    let mut file_names = vec![];
    let mut subdirectories = vec![];
    for entry in fs::read_dir(directory)? {
        let entry = entry?;
        let Ok(name) = entry.file_name().into_string() else {
            continue;
        };
        // Follow symlinks to directories, like os.walk(followlinks=True) did.
        let file_type = entry.file_type()?;
        if file_type.is_dir() || (file_type.is_symlink() && entry.path().is_dir()) {
            subdirectories.push((name, entry.path()));
        } else {
            file_names.push(name);
        }
    }

    let has_init = file_names.iter().any(|name| name == "__init__.py");
    if in_regular_package && !has_init {
        // Don't drill down into directories that aren't packages.
        return Ok(());
    }
    let in_regular_package = in_regular_package || has_init;

    let python_files_before = python_files.len();
    python_files.extend(
        file_names
            .iter()
            .filter(|name| is_python_file(name))
            .map(|name| directory.join(name)),
    );
    for (name, path) in &subdirectories {
        if is_identifier(name) {
            walk(path, in_regular_package, python_files, namespace_dirs)?;
        }
    }

    if !in_regular_package && python_files.len() > python_files_before {
        namespace_dirs.push(directory.to_path_buf());
    }
    Ok(())
}

/// Files like `some.module.py` and hidden files aren't treated as Python files.
fn is_python_file(name: &str) -> bool {
    name.ends_with(".py") && !name.starts_with('.') && name.matches('.').count() == 1
}

/// Equivalent to Python's `str.isidentifier`.
fn is_identifier(name: &str) -> bool {
    let mut chars = name.chars();
    chars
        .next()
        .is_some_and(|c| c == '_' || unicode_ident::is_xid_start(c))
        && chars.all(unicode_ident::is_xid_continue)
}

/// Equivalent to Python's `os.path.getmtime`, including the floating point arithmetic.
fn mtime(path: &Path) -> GrimpResult<f64> {
    let since_epoch = fs::metadata(path)?
        .modified()?
        .duration_since(UNIX_EPOCH)
        .map_err(std::io::Error::other)?;
    Ok(since_epoch.as_secs() as f64 + 1e-9 * since_epoch.subsec_nanos() as f64)
}
