mod caching;
pub mod errors;
pub mod exceptions;
mod filesystem;
pub mod graph;
mod graph_building;
pub mod import_parsing;
mod import_scanning;
mod log_records;
pub mod module_expressions;
mod module_finding;

use pyo3::prelude::*;

#[pymodule]
mod _rustgrimp {
    #[pymodule_export]
    use crate::graph::GraphWrapper;

    #[pymodule_export]
    use crate::graph_building::build_graph;

    #[pymodule_export]
    use crate::exceptions::{
        InvalidModuleExpression, ModuleNotPresent, NoSuchContainer, ParseError,
    };
}
