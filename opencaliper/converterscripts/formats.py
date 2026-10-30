"""Format registry: add an adapter here without changing the GUI or core model.

Module names are relative to this package. Readers expose read(path) -> Recording;
writers expose write(recording, path, overwrite=False). None means unsupported.
Detection uses the case-insensitive filename suffix; readers validate contents.
Dependencies are imported only when the selected adapter is used.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Format:
    name: str
    reader: str | None
    writer: str | None = None


FORMATS = {
    '.mat': Format('MAT', 'matconvert', 'matexport'),
    '.mdf': Format('MDF 3', 'mdfconvert', 'mdfexport'),
    '.mf4': Format('MDF 4', 'mdfconvert', 'mdfexport'),
    '.raw': Format('LTspice RAW', 'rawconvert', 'rawexport'),
    '.wvf': Format('Yokogawa WVF', 'wvfconvert', 'wvfexport'),
    '.bin': Format('Keysight BIN', 'binconvert'),
    '.npy': Format('NumPy columns', 'npyconvert'),
    '.h5': Format('Keysight HDF5', 'h5convert'),
    '.hdf5': Format('Keysight HDF5', 'h5convert'),
    '.s2p': Format('Touchstone 2-port', 'touchstoneconvert'),
    '.s4p': Format('Touchstone 4-port', 'touchstoneconvert'),
}


def input_filter():
    """Qt file picker filter generated from registered readers."""
    patterns = ' '.join(f'*{ext} *{ext.upper()}' for ext, fmt in FORMATS.items() if fmt.reader)
    return f'Measurements ({patterns});;All files (*)'


def output_filter():
    """Qt file picker filter generated from registered writers."""
    return ';;'.join(f'{fmt.name} (*{ext})' for ext, fmt in FORMATS.items() if fmt.writer)
