use crate::errors::{GrimpError, GrimpResult};
use crate::filesystem::FileSystem;
use crate::import_scanning::DirectImport;
use crate::log_records::LogRecord;
use crate::module_finding::{FoundPackage, Module};
use blake2::Blake2bVar;
use blake2::digest::{Update, VariableOutput};
use std::collections::{HashMap, HashSet};

const LOGGER: &str = "grimp.adaptors.caching";

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

/// Why the contents of a cache file can't be used.
enum Unusable {
    Corrupt,
    /// The file was written by a different version of Grimp.
    DifferentVersion,
}

/// Parses the contents of a data file.
fn parse_json_to_map(json_str: &str) -> Result<HashMap<Module, HashSet<DirectImport>>, Unusable> {
    let value: serde_json::Value = serde_json::from_str(json_str).map_err(|_| Unusable::Corrupt)?;

    if value.get("version").and_then(|v| v.as_u64()) != Some(CACHE_SCHEMA_VERSION as u64) {
        return Err(Unusable::DifferentVersion);
    }

    let raw_map: HashMap<String, Vec<(String, bool, usize, String)>> =
        serde_json::from_value(value.get("imports_by_module").cloned().unwrap_or_default())
            .map_err(|_| Unusable::Corrupt)?;

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

/// Reads and parses a cache file, logging what happened.
///
/// Returns None if the file can't be used.
fn read_cache_file<T>(
    file_system: &dyn FileSystem,
    file: &str,
    kind: &str,
    parse: impl FnOnce(&str) -> Result<T, Unusable>,
    log: &mut Vec<LogRecord>,
) -> Option<T> {
    let unusable = match file_system.read(file) {
        Ok(contents) => match parse(&contents) {
            Ok(value) => {
                log.push(LogRecord::info(
                    LOGGER,
                    format!("Used cache {kind} file {file}."),
                ));
                return Some(value);
            }
            Err(unusable) => unusable,
        },
        Err(GrimpError::FileNotFound(_)) => {
            log.push(LogRecord::info(LOGGER, format!("No cache file: {file}.")));
            return None;
        }
        Err(_) => Unusable::Corrupt,
    };
    log.push(match unusable {
        Unusable::Corrupt => {
            LogRecord::warning(LOGGER, format!("Could not use corrupt cache file {file}."))
        }
        Unusable::DifferentVersion => LogRecord::info(
            LOGGER,
            format!("Cache file {file} was written by a different version of Grimp; rebuilding."),
        ),
    });
    None
}

/// A cache of the imports of each module, for building a graph.
///
/// The file names and formats must not change without good reason, so that caches written by
/// earlier versions of Grimp can still be used.
pub struct Cache<'a> {
    directory: &'a str,
    found_packages: &'a HashSet<FoundPackage>,
    data_file_name: String,
}

impl<'a> Cache<'a> {
    pub fn new(
        directory: &'a str,
        found_packages: &'a HashSet<FoundPackage>,
        include_external_packages: bool,
        exclude_type_checking_imports: bool,
    ) -> Self {
        // The data file is specific to the packages and options used.
        let mut package_names: Vec<&str> = found_packages.iter().map(|p| p.name.as_str()).collect();
        package_names.sort();
        let mut identifier = package_names.join(",");
        if include_external_packages {
            identifier += ":external";
        }
        if exclude_type_checking_imports {
            identifier += ":no_type_checking";
        }
        // Hash the identifier to avoid filenames that are too long for the filesystem.
        let mut hasher = Blake2bVar::new(20).unwrap();
        hasher.update(identifier.as_bytes());
        let mut hash = [0; 20];
        hasher.finalize_variable(&mut hash).unwrap();
        let hex_hash: String = hash.iter().map(|byte| format!("{byte:02x}")).collect();

        Self {
            directory,
            found_packages,
            data_file_name: format!("{hex_hash}.data.json"),
        }
    }

    /// Reads the imports of the modules that haven't been modified since they were cached.
    ///
    /// Anything that can't be read (e.g. the cache doesn't exist yet) is treated as a cache miss.
    ///
    /// Args:
    /// - mtimes: the current modification time of each module, by module name.
    /// - log: anything to be logged is added to this.
    pub fn read(
        &self,
        file_system: &dyn FileSystem,
        mtimes: &HashMap<String, f64>,
        log: &mut Vec<LogRecord>,
    ) -> HashMap<Module, HashSet<DirectImport>> {
        let mut cached_mtimes: HashMap<String, f64> = HashMap::new();
        for found_package in self.found_packages {
            let meta_file = self.file_path(file_system, &meta_file_name(found_package));
            let parse = |contents: &str| {
                serde_json::from_str::<HashMap<String, f64>>(contents)
                    .map_err(|_| Unusable::Corrupt)
            };
            cached_mtimes.extend(
                read_cache_file(file_system, &meta_file, "meta", parse, log).unwrap_or_default(),
            );
        }

        let data_file = self.file_path(file_system, &self.data_file_name);
        let imports_by_module =
            read_cache_file(file_system, &data_file, "data", parse_json_to_map, log)
                .unwrap_or_default();

        imports_by_module
            .into_iter()
            .filter(|(module, _)| {
                cached_mtimes
                    .get(&module.name)
                    .is_some_and(|cached| mtimes.get(&module.name) == Some(cached))
            })
            .collect()
    }

    pub fn write(
        &self,
        file_system: &mut dyn FileSystem,
        mtimes: &HashMap<String, f64>,
        imports_by_module: &HashMap<Module, HashSet<DirectImport>>,
        log: &mut Vec<LogRecord>,
    ) -> GrimpResult<()> {
        for (file_name, contents) in MARKER_FILES {
            let path = self.file_path(file_system, file_name);
            if !file_system.exists(&path) {
                file_system.write(&path, contents)?;
            }
        }

        let data_file = self.file_path(file_system, &self.data_file_name);
        file_system.write(&data_file, &serialize_imports_by_module(imports_by_module))?;
        log.push(LogRecord::info(
            LOGGER,
            format!("Wrote data cache file {data_file}."),
        ));

        for found_package in self.found_packages {
            let package_mtimes: HashMap<&str, f64> = found_package
                .module_files
                .iter()
                .map(|module_file| {
                    let name = module_file.module.name.as_str();
                    (name, mtimes[name])
                })
                .collect();
            let meta_file = self.file_path(file_system, &meta_file_name(found_package));
            let contents = serde_json::to_string(&package_mtimes).expect("Failed to serialize");
            file_system.write(&meta_file, &contents)?;
            log.push(LogRecord::info(
                LOGGER,
                format!("Wrote meta cache file {meta_file}."),
            ));
        }
        Ok(())
    }

    fn file_path(&self, file_system: &dyn FileSystem, file_name: &str) -> String {
        file_system.join(vec![self.directory.to_string(), file_name.to_string()])
    }
}

fn meta_file_name(found_package: &FoundPackage) -> String {
    format!("{}.meta.json", found_package.name)
}

const MARKER_FILES: [(&str, &str); 2] = [
    (".gitignore", "# Automatically created by Grimp.\n*"),
    (
        "CACHEDIR.TAG",
        "Signature: 8a477f597d28d172789f06886806bc55\n\
         # This file is a cache directory tag automatically created by Grimp.\n\
         # For information about cache directory tags see https://bford.info/cachedir/",
    ),
];
