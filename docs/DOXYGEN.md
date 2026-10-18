# Doxygen API reference

Doxygen generates a browsable HTML reference from Python source and docstrings. It complements the [architecture guide](ARCHITECTURE.md) and [developer walkthrough](DEVELOPMENT.md): use those for intent and workflows, and the generated reference for classes, functions, arguments and source links.

## Install the documentation tools

Doxygen and Graphviz are documentation tools, not application runtime dependencies. They are not installed by the OpenCaliper launchers or by pip installing the project.

On Debian/Ubuntu:

```bash
sudo apt install doxygen graphviz
```

On Windows, install Doxygen and Graphviz using their installers and make `doxygen` and `dot` available on PATH. Reopen your terminal after changing PATH. The [Doxygen download page](https://www.doxygen.nl/download.html) and [Graphviz download page](https://graphviz.org/download/) provide installers and other platform options.

Check the installation:

```text
doxygen --version
dot -V
```

Doxygen 1.9.8 is the configuration's local validation version. Newer versions can be used, but review build warnings when changing versions.

## Generate and open the reference

Run from the **repository root**, where `Doxyfile` is located:

```bash
doxygen Doxyfile
```

Then open `docs-api/html/index.html` in a browser. For example:

```bash
# Linux desktop
xdg-open docs-api/html/index.html
```

```bat
rem Windows Command Prompt
start "" "docs-api\html\index.html"
```

No server, Python environment activation or application imports are required to generate or view the reference. Graphviz must be installed to produce its drawings. Output stays under the ignored `docs-api/` directory; commit the source comments, configuration and diagram definitions rather than generated HTML. Regenerate after source changes.

## What is included

- Public data models and format entry points with units, return values and validation rules.
- Numerical analysis documentation covering amplitude normalization, intervals and interpolation.
- GUI classes and key controller methods with state ownership and thread boundaries.
- Acquisition helpers, RAW writing, CLI dispatch, example generation and startup code.
- Linked source listings and class/inheritance views inferred by Doxygen.
- A curated architecture page with Graphviz component, ownership and loading-flow drawings.

The curated drawings live in `docs/doxygen/architecture.dox`. They explicitly describe dynamic ownership that automatic Python analysis cannot reliably infer. Automatic class graphs are useful navigation, not a complete runtime call graph. Global call/caller graphs are disabled to avoid implying exhaustive dynamic Python analysis.

Only `opencaliper/`, `scripts/`, the public generator and `docs/doxygen/` are scanned. `measFiles/`, `.venv`, private recordings and tests are not scanned. The generated reference has its own short landing page; the extended Markdown guides remain in the repository instead of being duplicated into generated pages with different diagram/link behavior.

## GitHub Actions

The documentation workflow builds this reference for pushes and pull requests, checks the warning log, and uploads `opencaliper-api-reference` as a workflow artifact. Download and extract that artifact, then open `index.html` locally. The workflow does not publish a public documentation website or enable GitHub Pages.

## Documenting code

The configuration uses `PYTHON_DOCSTRING = NO`, so ordinary Python docstrings are interpreted as Doxygen markup. Keep them readable in an editor as well:

```python
def operation(signal, start=None):
    """Compute a result from physical samples.

    @param signal Source Signal with timestamps in seconds.
    @param start Inclusive lower time bound, or None.
    @return Description of the result and its units.
    @exception ValueError Describe the rejected input condition.

    Explain numerical assumptions and side effects here.
    """
```

Describe what a caller must know, especially time/frequency units, array shape, scaling, mutation, missing metadata and unsupported inputs. A one-line description is enough for a simple internal action; public numerical or file APIs need their contracts explained. Update related architecture drawings if ownership or execution changes.

Inspect terminal warnings and `docs-api/warnings.log` after generation. Extraction includes undocumented symbols so readers can still navigate existing code; this does not mean every method has a detailed contract. Parameter documentation checks remain enabled. Doxygen does not verify mathematical correctness; use the numerical and parser tests described in [Development](DEVELOPMENT.md).

Reference: [Doxygen's Python documentation conventions](https://www.doxygen.nl/manual/docblocks.html) and [configuration options](https://www.doxygen.nl/manual/config.html).
