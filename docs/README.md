# OpenCaliper documentation

Start here depending on what you want to do:

| Goal | Guide |
| --- | --- |
| Install and open the application | [Project README: easy start](../README.md#easy-start-on-windows-and-linux) |
| Learn the viewer with a synthetic recording | [User guide](USER_GUIDE.md) |
| Understand components, state and execution | [Architecture](ARCHITECTURE.md) |
| Generate a browsable API reference and architecture drawings | [Doxygen](DOXYGEN.md) |
| Run the Python API, debug or implement a change | [Developer guide](DEVELOPMENT.md) |
| Create compatible input files | [MAT format](MAT_FORMAT.md) and [example generator](../examples/example.py) |
| Contribute a fix | [Contributing](../CONTRIBUTING.md) |
| Prepare a distribution | [Releasing](RELEASING.md) |

For a first contribution, read the architecture overview, follow the developer walkthrough, then use the Doxygen reference to navigate the relevant APIs and source. The test map in the developer guide points to examples of expected behavior.

## Two ways to explore the architecture

The [architecture guide](ARCHITECTURE.md) explains data flow and design decisions with Mermaid diagrams rendered directly on GitHub. The [Doxygen reference](DOXYGEN.md) provides linked APIs, source listings and Graphviz drawings for components, GUI ownership and file loading. Automatically inferred class diagrams are incomplete for dynamic Python; the curated drawings explain runtime relationships explicitly.

After installing Doxygen and Graphviz, run `doxygen Doxyfile` from the repository root and open `docs-api/html/index.html`. Generated HTML is local and ignored by Git. GitHub Actions also offers the generated reference as a downloadable workflow artifact. See the Doxygen guide for exact setup and viewing instructions.

The extended guides remain readable in the repository and source archive. Doxygen scans the application, startup script, public example generator and dedicated documentation pages; it does not ingest private recordings or the entire documentation folder.
