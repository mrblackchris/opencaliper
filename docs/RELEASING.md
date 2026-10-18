# Preparing a release

## Source and rights review

- Confirm that you have the right to publish the included source, contributions, documentation and images. Work created under an employment, customer or other agreement may require the rights holder's approval.
- Retain `LICENSE`, `NOTICE`, and `THIRD_PARTY_NOTICES.md`. The project is prepared as GPL-3.0-only because it integrates GPL-covered software. Recheck dependencies when changing imports or packaging.
- Use only synthetic or explicitly publishable recordings and screenshots. Private data, local acquisition scripts, credentials and development environments are excluded by the repository ignore rules.
- Review `git diff --cached`, `git status --short` and the staged file list before publishing. Ignore rules do not remove files already tracked by Git and do not protect a directory uploaded manually.
- Check project-name and branding rights for the jurisdictions where you plan to distribute. Preparing release files does not constitute trademark clearance or a legal opinion.

## Validate a clean checkout

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m unittest discover -s tests -v
python examples/example.py --output demo.mat
opencaliper info demo.mat
opencaliper gui demo.mat
python -m build
```

Inspect the source archive and wheel. They should contain OpenCaliper code, documentation and license notices, with no private recordings, virtual environment, proprietary binaries or local configuration. Test installation of the wheel in a clean environment and verify `opencaliper --help` and the GUI.

The application CI workflow runs tests and builds Python package artifacts but does not publish to a package index or create a public release. Running CI is not a legal or security certification.

## Validate documentation

Install Doxygen and Graphviz as described in the [Doxygen guide](DOXYGEN.md), then run from the repository root:

```bash
doxygen Doxyfile
```

Check that `docs-api/warnings.log` is empty. Open `docs-api/html/index.html` and inspect the landing page, linked API/source entries and the three curated architecture drawings. Check that changes to behavior and ownership are reflected in the user guide, architecture guide and API docstrings.

The source archive should include `Doxyfile`, the Markdown guides and `docs/doxygen/*.dox`, so readers can regenerate the reference. It should exclude generated `docs-api/` content and `measFiles/`; the bundled `examples/example.mat` is the public synthetic exception to measurement-file exclusions. A wheel carries installable application code and notices; use the repository or source archive for the complete guides and documentation build inputs.

The separate documentation workflow uploads generated HTML as `opencaliper-api-reference`. Download and extract the artifact and open its `index.html` to review it. It does not publish a website. If distributing an HTML archive separately, preserve the complete generated directory so stylesheets, diagrams and source links continue to work.

## GitHub repository

Suggested repository name: `OpenCaliper`.

Suggested description: **Open-source data viewer and analyzer for recorded signals, FFT spectra, cursor measurements and file conversion.**

Suggested topics: `python`, `data-viewer`, `signal-analysis`, `waveform`, `fft`, `measurement`, `pyside6`.

When creating the repository, use the existing GPL license file rather than adding a conflicting license. Enable issues and, if you can maintain it, private vulnerability reporting in the repository settings. Do not claim vendor endorsement or universal compatibility with a file extension.

Update the version in `pyproject.toml` and the release notes in `CHANGELOG.md` before tagging a release. Use the README as the feature description and document known limits. Do not make measurement-accuracy or safety guarantees that have not been validated.

## Binary bundles and installers

A Python source distribution/wheel is different from an executable that bundles dependencies. Before distributing an executable or installer, inventory the exact included components, preserve their license texts and notices, and satisfy their applicable source and redistribution requirements, including GPL and Qt/LGPL obligations. Do not bundle proprietary vendor libraries without appropriate rights.

These checks reduce identifiable publication risks but do not guarantee the absence of legal issues. Get qualified advice if ownership, license compatibility or distribution rights remain unclear.
