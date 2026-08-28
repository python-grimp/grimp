# Grimp

Grimp builds a queryable graph of the imports within one or more Python packages. It's a
hybrid Python/Rust project: the public API and orchestration are in Python
(`src/grimp/`), and the import scanning and graph algorithms are implemented in Rust
(`rust/`) as a PyO3 extension module (`grimp._rustgrimp`), built with maturin.

## Architecture

`src/grimp/` follows a layered/hexagonal architecture, enforced by Import Linter itself
(see `.importlinter`):

- `domain/` — core types (`valueobjects.py`, `analysis.py`), no dependencies on other layers.
- `application/` — use cases and ports (`usecases.py`, `graph.py`, `scanning.py`, `config.py`).
- `adaptors/` — implementations of application ports (filesystem, module/package finding,
  caching, timing).
- `main.py` — top-level entry point (`grimp.build_graph`), wires adaptors to use cases.
- `exceptions.py` — shared exceptions, importable from any layer.

Respect this layering: `domain` must not import from `application` or `adaptors`, etc. Run
`just lint-python` (which includes `lint-imports`) to check.

The Rust side (`rust/src/`) does the heavy lifting: import parsing (via `ruff`'s parser),
module/import scanning, and graph algorithms (`rust/src/graph/`: pathfinding, cycle
detection, hierarchy queries, etc.).

## Setup

Prerequisites: `git`, [`uv`](https://docs.astral.sh/uv/), [`just`](https://just.systems/),
and Rust via [`rustup`](https://rust-lang.org/tools/install/). No virtualenv management is
needed — `uv` handles it. Run `just install-precommit` once to set up pre-commit hooks.

Run `just help` (or `just --list`) to see all available recipes.

## Common commands

- `just compile` — build the Rust extension for development (via `maturin develop`). Needed
  after any change to `rust/`.
- `just test-python` — run Python tests (default Python version). Pass a version to target
  another, e.g. `just test-python 3.14`.
- `just test-rust` — run Rust tests.
- `just compile-and-test` — compile Rust, then run Rust and Python tests. Use this after
  touching Rust code.
- `just lint` — ruff format check, ruff check, mypy, and `lint-imports` for Python; `cargo
  fmt --check` and `cargo clippy` for Rust.
- `just autofix` — autofix both Python (ruff) and Rust (clippy --fix) issues.
- `just build-and-open-docs` — build Sphinx docs and open them locally.
- `just full-check` — lint + docs build + tests across all supported Python versions. Run
  this before requesting a review.

## Working with tests

Most tests are Python (`tests/`); Rust tests are optional for a change unless you touched
Rust internals. Aim for full test coverage at the Python level. Snapshot tests use Syrupy —
regenerate with `just update-snapshots` when a snapshot legitimately needs to change, and
review the diff.

Important principle: even if the implementation is in Rust, write the tests in Python.
The Python tests are regression tests, the Rust tests are there purely to aid development / debugging
in certain cases, and are optional. 

## Conventions

- Add a `CHANGELOG.rst` entry (imperative mood) under the `latest` section at the top for
  any user-facing change; create the section if it doesn't exist.
- Add yourself to `AUTHORS.rst` for a first contribution.
- For non-trivial changes, prefer discussing direction in a GitHub issue before large PRs
  (see `CONTRIBUTING.rst`).
- Update documentation (`docs/`) when adding or changing public API/functionality.

## Full contributor guide

`CONTRIBUTING.rst` has the complete guide, including benchmarking (Codspeed and local),
profiling, and the PyPI release process.
