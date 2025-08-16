use crate::errors::GrimpResult;
use crate::graph::pathfinding::{find_reach, find_shortest_path};
use crate::graph::{ExtendWithDescendants, Graph, ModuleToken};
use itertools::Itertools;
use rustc_hash::{FxHashMap, FxHashSet};
use tap::Conv;

impl Graph {
    pub fn find_downstream_modules(
        &self,
        module: ModuleToken,
        as_package: bool,
    ) -> FxHashSet<ModuleToken> {
        let mut from_modules = module.conv::<FxHashSet<_>>();
        if as_package {
            from_modules.extend_with_descendants(self);
        }

        find_reach(&self.reverse_imports, &from_modules)
    }

    pub fn find_upstream_modules(
        &self,
        module: ModuleToken,
        as_package: bool,
    ) -> FxHashSet<ModuleToken> {
        let mut from_modules = module.conv::<FxHashSet<_>>();
        if as_package {
            from_modules.extend_with_descendants(self);
        }

        find_reach(&self.imports, &from_modules)
    }

    pub fn find_shortest_chain(
        &self,
        importer: ModuleToken,
        imported: ModuleToken,
        as_packages: bool,
    ) -> GrimpResult<Option<Vec<ModuleToken>>> {
        if as_packages {
            self.find_shortest_chain_with_excluded_modules_and_imports(
                &importer.conv::<FxHashSet<_>>().with_descendants(self),
                &imported.conv::<FxHashSet<_>>().with_descendants(self),
                &FxHashSet::default(),
                &FxHashMap::default(),
            )
        } else {
            self.find_shortest_chain_with_excluded_modules_and_imports(
                &importer.conv::<FxHashSet<_>>(),
                &imported.conv::<FxHashSet<_>>(),
                &FxHashSet::default(),
                &FxHashMap::default(),
            )
        }
    }

    pub(crate) fn find_shortest_chain_with_excluded_modules_and_imports(
        &self,
        from_modules: &FxHashSet<ModuleToken>,
        to_modules: &FxHashSet<ModuleToken>,
        excluded_modules: &FxHashSet<ModuleToken>,
        excluded_imports: &FxHashMap<ModuleToken, FxHashSet<ModuleToken>>,
    ) -> GrimpResult<Option<Vec<ModuleToken>>> {
        find_shortest_path(
            self,
            from_modules,
            to_modules,
            excluded_modules,
            excluded_imports,
        )
    }

    pub fn chain_exists(
        &self,
        importer: ModuleToken,
        imported: ModuleToken,
        as_packages: bool,
    ) -> GrimpResult<bool> {
        Ok(self
            .find_shortest_chain(importer, imported, as_packages)?
            .is_some())
    }

    pub fn find_shortest_chains(
        &self,
        importer: ModuleToken,
        imported: ModuleToken,
        as_packages: bool,
    ) -> GrimpResult<FxHashSet<Vec<ModuleToken>>> {
        // Shortcut the detailed implementation in the case of no chains.
        // This will be much faster!
        if !self.chain_exists(importer, imported, as_packages)? {
            return Ok(FxHashSet::default());
        }

        let mut downstream_modules = FxHashSet::from_iter([importer]);
        let mut upstream_modules = FxHashSet::from_iter([imported]);
        if as_packages {
            downstream_modules.extend_with_descendants(self);
            upstream_modules.extend_with_descendants(self);
        }

        let chains = self
            ._find_shortest_chains(
                &downstream_modules,
                &upstream_modules,
                &FxHashSet::from_iter([]),
            )?
            .into_iter()
            .collect();

        Ok(chains)
    }

    pub(crate) fn _find_shortest_chains(
        &self,
        from_modules: &FxHashSet<ModuleToken>,
        to_modules: &FxHashSet<ModuleToken>,
        excluded_modules: &FxHashSet<ModuleToken>,
    ) -> GrimpResult<Vec<Vec<ModuleToken>>> {
        let mut chains = vec![];

        // Disallow chains via these imports.
        // We'll add chains to this set as we discover them.
        let mut excluded_imports = FxHashMap::default();

        loop {
            let chain = self.find_shortest_chain_with_excluded_modules_and_imports(
                from_modules,
                to_modules,
                excluded_modules,
                &excluded_imports,
            )?;

            if chain.is_none() {
                break;
            }
            let chain = chain.unwrap();

            // Exclude this chain from further searching.
            for (importer, imported) in chain.iter().tuple_windows() {
                excluded_imports
                    .entry(*importer)
                    .or_default()
                    .insert(*imported);
            }

            chains.push(chain);
        }

        Ok(chains)
    }
}
