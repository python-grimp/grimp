use crate::errors::{GrimpError, GrimpResult};
use crate::graph::{
    EMPTY_IMPORT_DETAILS, EMPTY_MODULE_TOKENS, ExtendWithDescendants, Graph, ModuleIterator,
    ModuleToken, PyImportDetails,
};
use crate::module_expressions::ModuleExpression;
use rustc_hash::FxHashSet;

impl Graph {
    pub fn count_imports(&self) -> usize {
        self.imports.values().map(|imports| imports.len()).sum()
    }

    pub fn direct_import_exists(
        &self,
        importer: ModuleToken,
        imported: ModuleToken,
        as_packages: bool,
    ) -> GrimpResult<bool> {
        let mut importers: FxHashSet<_> = importer.into();
        let mut importeds: FxHashSet<_> = imported.into();
        if as_packages {
            importers.extend_with_descendants(self);
            importeds.extend_with_descendants(self);
            if !(&importers & &importeds).is_empty() {
                return Err(GrimpError::SharedDescendants);
            }
        }

        let direct_imports = importers
            .iter()
            .flat_map(|importer_module| self.imports.get(*importer_module).unwrap().iter().cloned())
            .collect::<FxHashSet<ModuleToken>>();

        Ok(!(&direct_imports & &importeds).is_empty())
    }

    pub fn find_direct_imports_between(
        &self,
        importer: ModuleToken,
        imported: ModuleToken,
        as_packages: bool,
    ) -> GrimpResult<FxHashSet<(ModuleToken, ModuleToken)>> {
        let mut all_imports: FxHashSet<(ModuleToken, ModuleToken)> = FxHashSet::default();

        let mut importers: FxHashSet<_> = importer.into();
        let mut importeds: FxHashSet<_> = imported.into();
        if as_packages {
            importers.extend_with_descendants(self);
            importeds.extend_with_descendants(self);
            if !(&importers & &importeds).is_empty() {
                return Err(GrimpError::SharedDescendants);
            }
        }

        for importer_module in importers.iter() {
            if let Some(all_imports_imported_by_this_one) = self.imports.get(*importer_module) {
                let imports_of_supplied_package: FxHashSet<_> = all_imports_imported_by_this_one
                    .iter()
                    .filter(|candidate| importeds.contains(*candidate))
                    .map(|imported_module| (*importer_module, *imported_module))
                    .collect();
                all_imports.extend(imports_of_supplied_package);
            }
        }

        Ok(all_imports)
    }

    /// Find the modules directly imported by the module.
    ///
    /// If `as_package` is true, the module is treated as a package: the result is the modules
    /// directly imported by it or any of its descendants, excluding modules within the package.
    pub fn modules_directly_imported_by(
        &self,
        importer: ModuleToken,
        as_package: bool,
    ) -> FxHashSet<ModuleToken> {
        let mut importers: FxHashSet<_> = importer.into();
        if as_package {
            importers.extend_with_descendants(self);
        }

        let mut imported_modules: FxHashSet<_> = importers
            .iter()
            .flat_map(|importer| self.imports.get(*importer).unwrap_or(&EMPTY_MODULE_TOKENS))
            .cloned()
            .collect();
        if as_package {
            imported_modules.retain(|imported| !importers.contains(imported));
        }
        imported_modules
    }

    /// Find the modules that directly import the module.
    ///
    /// If `as_package` is true, the module is treated as a package: the result is the modules
    /// that directly import it or any of its descendants, excluding modules within the package.
    pub fn modules_that_directly_import(
        &self,
        imported: ModuleToken,
        as_package: bool,
    ) -> FxHashSet<ModuleToken> {
        let mut importeds: FxHashSet<_> = imported.into();
        if as_package {
            importeds.extend_with_descendants(self);
        }

        let mut importers: FxHashSet<_> = importeds
            .iter()
            .flat_map(|imported| {
                self.reverse_imports
                    .get(*imported)
                    .unwrap_or(&EMPTY_MODULE_TOKENS)
            })
            .cloned()
            .collect();
        if as_package {
            importers.retain(|importer| !importeds.contains(importer));
        }
        importers
    }

    pub fn get_import_details(
        &self,
        importer: ModuleToken,
        imported: ModuleToken,
    ) -> &FxHashSet<PyImportDetails> {
        match self.import_details.get(&(importer, imported)) {
            Some(import_details) => import_details,
            None => &EMPTY_IMPORT_DETAILS,
        }
    }

    pub fn find_matching_direct_imports(
        &self,
        importer_expression: &ModuleExpression,
        imported_expression: &ModuleExpression,
    ) -> FxHashSet<(ModuleToken, ModuleToken)> {
        let importers: FxHashSet<ModuleToken> = self
            .find_matching_modules(importer_expression)
            .tokens()
            .collect();
        let importeds: FxHashSet<ModuleToken> = self
            .find_matching_modules(imported_expression)
            .tokens()
            .collect();

        importers
            .iter()
            .flat_map(|importer| {
                self.modules_directly_imported_by(*importer, false)
                    .into_iter()
                    .filter(|imported| importeds.contains(imported))
                    .map(move |imported| (*importer, imported))
            })
            .collect()
    }
}

#[cfg(test)]
mod test {
    use super::*;

    #[test]
    fn test_modules_directly_imported_by() {
        let mut graph = Graph::default();

        let animals = graph.get_or_add_module("pkg.animals").token;
        let dog = graph.get_or_add_module("pkg.animals.dog").token;
        let cat = graph.get_or_add_module("pkg.animals.cat").token;
        let food = graph.get_or_add_module("pkg.food").token;
        let chicken = graph.get_or_add_module("pkg.food.chicken").token;
        let tesco = graph.get_or_add_module("pkg.shops.tesco").token;

        graph.add_import(dog, chicken);
        graph.add_import(cat, food);
        // An import within the package.
        graph.add_import(dog, cat);
        // An import of the package, not by it.
        graph.add_import(tesco, animals);

        // Without as_package, only the module itself is looked at.
        assert_eq!(
            graph.modules_directly_imported_by(animals, false),
            FxHashSet::default()
        );
        assert_eq!(
            graph.modules_directly_imported_by(dog, false),
            FxHashSet::from_iter([chicken, cat])
        );
        // With as_package, descendants are looked at too, but modules within the package
        // are excluded.
        assert_eq!(
            graph.modules_directly_imported_by(animals, true),
            FxHashSet::from_iter([chicken, food])
        );
    }

    #[test]
    fn test_modules_that_directly_import() {
        let mut graph = Graph::default();

        let animals = graph.get_or_add_module("pkg.animals").token;
        let dog = graph.get_or_add_module("pkg.animals.dog").token;
        let cat = graph.get_or_add_module("pkg.animals.cat").token;
        let chicken = graph.get_or_add_module("pkg.food.chicken").token;
        let shops = graph.get_or_add_module("pkg.shops").token;
        let tesco = graph.get_or_add_module("pkg.shops.tesco").token;

        graph.add_import(tesco, animals);
        graph.add_import(shops, cat);
        // An import within the package.
        graph.add_import(dog, cat);
        // An import by the package, not of it.
        graph.add_import(dog, chicken);

        // Without as_package, only the module itself is looked at.
        assert_eq!(
            graph.modules_that_directly_import(animals, false),
            FxHashSet::from_iter([tesco])
        );
        assert_eq!(
            graph.modules_that_directly_import(cat, false),
            FxHashSet::from_iter([shops, dog])
        );
        // With as_package, descendants are looked at too, but modules within the package
        // are excluded.
        assert_eq!(
            graph.modules_that_directly_import(animals, true),
            FxHashSet::from_iter([tesco, shops])
        );
    }

    #[test]
    fn test_find_matching_direct_imports() {
        let mut graph = Graph::default();

        let _ = graph.get_or_add_module("pkg.animals").token;
        let dog = graph.get_or_add_module("pkg.animals.dog").token;
        let cat = graph.get_or_add_module("pkg.animals.cat").token;
        let _ = graph.get_or_add_module("pkg.food").token;
        let chicken = graph.get_or_add_module("pkg.food.chicken").token;
        let fish = graph.get_or_add_module("pkg.food.fish").token;
        let _ = graph.get_or_add_module("pkg.colors").token;
        let golden = graph.get_or_add_module("pkg.colors.golden").token;
        let ginger = graph.get_or_add_module("pkg.colors.ginger").token;
        let _ = graph.get_or_add_module("pkg.shops").token;
        let tesco = graph.get_or_add_module("pkg.shops.tesco").token;
        let coop = graph.get_or_add_module("pkg.shops.coop").token;

        // Should match
        graph.add_import(dog, chicken);
        graph.add_import(cat, fish);
        // Should not match: Imported does not match
        graph.add_import(dog, golden);
        graph.add_import(cat, ginger);
        // Should not match: Importer does not match
        graph.add_import(tesco, chicken);
        graph.add_import(coop, fish);

        let importer_expression = "pkg.animals.*".parse().unwrap();
        let imported_expression = "pkg.food.*".parse().unwrap();
        let matching_imports =
            graph.find_matching_direct_imports(&importer_expression, &imported_expression);

        assert_eq!(
            matching_imports,
            FxHashSet::from_iter([(dog, chicken), (cat, fish)])
        );
    }

    #[test]
    fn test_find_matching_direct_imports_with_and_without_wildcards() {
        let mut graph = Graph::default();

        let dog = graph.get_or_add_module("pkg.animals.dog").token;
        let cat = graph.get_or_add_module("pkg.animals.cat").token;
        let chicken = graph.get_or_add_module("pkg.food.chicken").token;
        let fish = graph.get_or_add_module("pkg.food.fish").token;
        let golden = graph.get_or_add_module("pkg.colors.golden").token;
        let tesco = graph.get_or_add_module("pkg.shops.tesco").token;
        graph.get_or_add_module("pkg.shops.coop");

        graph.add_import(dog, chicken);
        graph.add_import(dog, golden);
        graph.add_import(cat, fish);
        graph.add_import(tesco, chicken);

        let find = |importer_expression: &str, imported_expression: &str| {
            graph.find_matching_direct_imports(
                &importer_expression.parse().unwrap(),
                &imported_expression.parse().unwrap(),
            )
        };

        // Neither side has wildcards.
        assert_eq!(
            find("pkg.animals.dog", "pkg.food.chicken"),
            FxHashSet::from_iter([(dog, chicken)])
        );
        // Only the importer is a single module.
        assert_eq!(
            find("pkg.animals.dog", "pkg.*.*"),
            FxHashSet::from_iter([(dog, chicken), (dog, golden)])
        );
        // Only the imported is a single module.
        assert_eq!(
            find("pkg.*.*", "pkg.food.chicken"),
            FxHashSet::from_iter([(dog, chicken), (tesco, chicken)])
        );
        // Both sides have wildcards.
        assert_eq!(
            find("pkg.shops.*", "pkg.food.*"),
            FxHashSet::from_iter([(tesco, chicken)])
        );
        // A module with no imports.
        assert!(find("pkg.shops.coop", "pkg.*.*").is_empty());
        // A module that has no importers.
        assert!(find("pkg.*.*", "pkg.shops.coop").is_empty());
        // Modules that aren't in the graph.
        assert!(find("pkg.animals.missing", "pkg.*.*").is_empty());
        assert!(find("pkg.*.*", "pkg.food.missing").is_empty());
        assert!(find("pkg.animals.missing", "pkg.food.missing").is_empty());
        // Wildcards that match nothing.
        assert!(find("pkg.nothing.*", "pkg.*.*").is_empty());
    }
}
