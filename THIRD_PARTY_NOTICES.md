# Third-party software

OpenCaliper uses the following direct dependencies. Their authors retain their respective copyrights. The project's GPL-3.0-only license does not replace the licenses of those dependencies.

| Dependency | Purpose | Upstream license | Upstream source |
| --- | --- | --- | --- |
| NumPy | Numeric arrays and FFT | BSD-3-Clause | https://github.com/numpy/numpy |
| SciPy | MATLAB file I/O | BSD-3-Clause | https://github.com/scipy/scipy |
| hdf5storage | HDF5/MATLAB v7.3 I/O | BSD-2-Clause | https://github.com/frejanordsiek/hdf5storage |
| asammdf | MDF/MF4 import and export | LGPL-3.0-or-later | https://github.com/danielhrisca/asammdf |
| spicelib | RAW input | GPL-3.0 | https://github.com/nunobrum/spicelib |
| pyqtgraph | Interactive plots | MIT | https://github.com/pyqtgraph/pyqtgraph |
| PySide6-Essentials / Qt | Desktop interface | LGPL-3.0 / GPL alternatives; see upstream terms | https://code.qt.io/pyside/pyside-setup.git/ |

This is an inventory of direct dependencies, not a complete inventory of every transitive or binary component. Installed dependency distributions contain their own license and attribution files. NumPy/SciPy binary wheels, Qt distributions, HDF5 components and other transitive dependencies may include further third-party software and notices. Review the exact distributions included in any binary release.

The integrated RAW reader uses GPL-licensed spicelib, and OpenCaliper is distributed under GPL version 3. PySide6-Essentials is used for QtCore, QtGui, QtWidgets and QtTest; upstream Qt module and third-party licensing terms continue to apply. See [Qt for Python licensing](https://doc.qt.io/qtforpython-6/licenses.html).

## Distribution

The source repository and standard wheel contain OpenCaliper code; dependency libraries are installed separately by the package manager. No proprietary instrument libraries or vendor executables are bundled.

If distributing an application bundle or installer, include the relevant license texts and copyright notices for every redistributed component and meet its source-code and other distribution obligations. GPL-covered distributions require corresponding source as applicable. Qt's LGPL option has additional conditions, including users' ability to replace the covered libraries. A dependency list or a link to this document alone is not a substitute for those obligations.

Names of products and manufacturers in the format documentation identify compatibility only. OpenCaliper is an independent project and is not endorsed by those manufacturers. File-format compatibility does not grant permission to redistribute their software, documentation, logos or recordings.
