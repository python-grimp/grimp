============
Contributing
============

We welcome contributions to Grimp.

Bug reports
===========

When `reporting a bug <https://github.com/python-grimp/grimp/issues>`_ please include:

    * Your operating system name and version.
    * Any details about your local setup that might be helpful in troubleshooting.
    * Detailed steps to reproduce the bug.

Feature requests and feedback
=============================

The best way to send feedback is to file an issue at https://github.com/python-grimp/grimp/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible.
* Remember that this is a volunteer-driven project.

Submitting pull requests
========================

Before spending time working on a pull request, we highly recommend filing a Github issue and engaging with the project maintainer (David Seddon) to align on the direction you’re planning to take. This can save a lot of your precious time!

This doesn’t apply to trivial pull requests such as spelling corrections.

We recommend installing precommit, which will perform basic linting and testing whenever you commit a file.
To set this up, run ``just install-precommit``.

Before requesting a review
--------------------------

- Ensure you have included tests that cover the change. In general, aim for full test coverage at the Python level.
  Rust tests are optional.
- Update documentation when there's a new API, functionality etc.
- Add a note to ``CHANGELOG.rst`` about the changes, in the imperative mood. This should go under
  the main page title, under a ``latest`` section. If it's not there already, create it. E.g.::

      latest
      ------

      * Add new feature.

- Add yourself to ``AUTHORS.rst``.
- Run ``just full-check`` locally. (If you're a new contributor, CI checks are not run automatically.)

Development
===========

System prerequisites
--------------------

Make sure these are installed first.

- `git <https://github.com/git-guides/install-git>`_
- `uv <https://docs.astral.sh/uv/#installation>`_
- `just <https://just.systems/man/en/packages.html>`_
- Cargo (via `rustup <https://rust-lang.org/tools/install/>`_)

Setup
-----

You don't need to activate or manage a virtual environment - this is taken care in the background of by ``uv``.

To set up Grimp for local development:

1. Fork `grimp <https://github.com/python-grimp/grimp>`_
   (look for the "Fork" button).
2. Clone your fork locally::

    git clone git@github.com:your_name_here/grimp.git

3. Change into the directory you just cloned::

    cd grimp

4. Set up pre-commit. (Optional, but recommended.)::

    just install-precommit

You will now be able to run commands prefixed with ``just``, providing you're in the ``grimp`` directory.
To see available commands, run ``just help``.

Working with tests
------------------

Grimp is a mixture of Python and Rust. The majority of the tests are in Python.

If you change the Rust code, you will need to recompile it before running the Python tests.

Typical workflow (Python changes only):

1. Make a change.
2. Run ``just test-python``. This will run the Python tests using the default Python version (e.g. whatever is specified
   in a local ``.python-version`` file).

Typical workflow (changes that involve Rust):

1. Make a change to Rust code.
2. Run ``just compile-and-test``. This will compile the Rust code, then run Rust and Python tests in the default version.

You can also run tests under specific Python versions by passing the version, e.g. ``just test-python 3.14``.

Working with documentation
--------------------------

You can preview any documentation changes locally by running::

    just build-and-open-docs

It's helpful to include a screenshot of the new docs in the pull request description.

Before you push
---------------

It's a good idea to run ``just full-check`` before getting a review.
This will run linters, docs build and tests under every supported Python version.
You can automatically fix many lint errors using ``just autofix`` (or ``just autofix-python`` and ``just autofix-rust`` separately).

Adding support for a new Python version
========================================

1. In ``pyproject.toml``, add ``3.x`` to the ``Programming Language :: Python :: 3.x``
   classifiers.
2. In ``.github/workflows/main.yml``, add ``"3.x"`` and ``"3.xt"`` to the
   ``test`` job's ``python-version`` matrix.
3. In ``.github/workflows/release.yml``, add ``"3.x"`` and ``"3.xt"`` to the shared
   ``linux`` and ``musllinux`` interpreter lists. For ``windows``, add ``"3.x"`` to
   the regular interpreter lists (including the ARM64 literal list) and ``"3.xt"``
   to the free-threaded interpreter lists. For ``macos``, add ``3.x`` to the regular
   ``actions/setup-python`` list and matching ``--interpreter`` arguments, and ``3.xt``
   to the corresponding free-threaded step's list and arguments. Keep the regular and
   free-threaded installations separate on Windows/macOS to avoid binary shadowing.
4. Push a branch with this change and trigger the release workflow manually, without pushing
   a tag, to see which targets can actually build the new version::

       gh workflow run release.yml --ref <your-branch>

   Then watch it with ``gh run watch`` or in the Actions tab.
5. For any ``linux``/``musllinux`` job that fails because the build image doesn't have the
   new interpreter yet, split that target out of the shared interpreter list it was using
   (e.g. ``&full-interpreters``/``&cross-interpreters``) into its own list without the new
   version, following the pattern already used for targets that lag behind (see the comments
   above the ``linux`` and ``musllinux`` matrices for the current state). To check directly
   instead of waiting for a failed build, look up the image's available tags:

   - ``linux`` job, native targets (x86_64, x86, aarch64): `quay.io/pypa manylinux2014 tags
     <https://quay.io/repository/pypa/manylinux2014_x86_64?tab=tags>`_
   - ``linux`` job, cross targets (armv7, s390x, ppc64le): `rust-cross manylinux2014-cross
     tags <https://github.com/rust-cross/manylinux-cross/pkgs/container/manylinux2014-cross>`_
   - ``musllinux`` job (all targets): `rust-cross rust-musl-cross tags
     <https://github.com/rust-cross/rust-musl-cross/pkgs/container/rust-musl-cross>`_
   - ``windows``/``macos`` jobs use ``actions/setup-python``, which installs from
     `actions/python-versions <https://github.com/actions/python-versions/blob/main/versions-manifest.json>`_
     - these are normally available from Python's own release day, including prereleases
     (``allow-prereleases: true`` is already set).
6. For each target excluded in step 5, `open a GitHub issue
   <https://github.com/python-grimp/grimp/issues/new>`_ to track adding it once the build
   image catches up (e.g. "Add Python 3.x wheels for musllinux", one issue per image/family
   is fine if several targets share it). Add a comment directly above the relevant
   interpreter list in ``release.yml`` referencing the issue number, e.g.::

       # ghcr.io/rust-cross/rust-musl-cross doesn't yet bundle Python 3.x.
       # See https://github.com/python-grimp/grimp/issues/<n>.

   This is the only thing that makes the gap actionable later - without an issue number
   there's nothing to revisit the exclusion when the image is updated.
7. In ``justfile``, add a ``just test-python 3.x`` and ``3.xt`` lines to the ``test-all``
   recipe.
8. In ``CHANGELOG.rst``, add an entry under ``latest``: ``* Officially support Python 3.x.``
   If step 5 excluded any targets, add a second entry noting which ones, why, and linking the
   issue(s) from step 6 (see existing ``CHANGELOG.rst`` entries about missing 3.15 wheels for
   the expected wording).
9. Run ``just full-check`` to confirm everything passes.

Dropping support for a Python version
======================================

1. In ``pyproject.toml``, update ``requires-python`` and remove the ``Programming Language ::
   Python :: 3.x`` classifier.
2. In ``.github/workflows/main.yml``, remove ``"3.x"`` (and ``"3.xt"`` if present) from the
   ``test`` job's ``python-version`` matrix.
3. In ``.github/workflows/release.yml``, remove ``"3.x"`` (and ``"3.xt"``) from every
   interpreter list it appears in.
4. In ``justfile``, remove the ``just test-python 3.x`` (and ``3.xt``) line(s) from the
   ``test-all`` recipe.
5. In ``CHANGELOG.rst``, add an entry under ``latest``: ``* Drop support for Python 3.x.``
6. Run ``just modernize-python 3x`` with the new lowest version (e.g. ``just modernize-python 311``).
7. Remove any code paths or tests that exist solely to support the dropped version.
8. Run ``just full-check`` to confirm everything passes.

Benchmarking
============

Codspeed
--------

A few benchmarks are run automatically on pull requests, using `Codspeed <https://codspeed.io/>`_.
Once the benchmarks have completed, a report will be included as a comment on the pull request.

Codspeed also shows flame graphs which can help track down why a change might have impacted performance.

Local benchmarking
------------------

It's also possible to run local benchmarks, which can be helpful if you want to quickly compare performance
across different versions of the code.

To benchmark a particular version of the code, run ``just benchmark-local``. This command creates a report that will be
stored in a local file (ignored by Git).

This will display a list of all the benchmarks you've run locally, ordered from earlier to later.

Profiling
=========

Codspeed
--------

The easiest way to profile code is to look at the Codspeed flamegraph, automatically generated during benchmarking
(see above).

Profiling Rust code locally
---------------------------

Rust integration tests can be profiled using `Cargo Flamegraph <https://github.com/flamegraph-rs/flamegraph>`_
(which will need to be installed first, e.g. using ``cargo install flamegraph``).

Navigate to the ``rust`` directory in this package.

Run cargo flamegraph on the relevant test. E.g. to profile ``rust/tests/large.rs``, run:

``sudo cargo flamegraph --root --test large``

This will create a file called ``flamegraph.svg``, which you can open to view the flamegraph.

Releasing to Pypi
=================

This is only possible if you're a maintainer.

1. Choose a new version number (based on `semver <https://semver.org/>`_).
2. ``git pull origin main``
3. Update ``CHANGELOG.rst`` with the new version number.
4. Update the ``release`` variable in ``docs/conf.py`` with the new version number.
5. Update the ``__version__`` variable in ``src/grimp/__init__.py`` with the new version number.
6. Update ``project.version`` in ``pyproject.toml`` with the new version number.
7. ``uv lock`` to sync ``uv.lock`` with the new version.
8. ``git commit -am "Release v{new version number"``
9. ``git push``
10. Wait for tests to pass on CI.
11. ``git tag v{new version number}``
12. ``git push --tags``
13. This should kick start the Github ``release`` workflow, which builds wheels and releases the
    project to PyPI.
