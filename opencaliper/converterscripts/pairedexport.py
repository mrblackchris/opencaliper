"""Portable SignalN_u / SignalN_t or SignalN_f MAT conversion output."""
from pathlib import Path
import os
import tempfile
from scipy.io import savemat


def write(recording, path, overwrite=False):
    """Write independent channels with safe MATLAB identifiers and original names.

    Extra domain/reference metadata retains S-parameter semantics. The paired
    reader also accepts ordinary pairs without those optional metadata fields.
    """
    from ..core import Recording, Signal
    if not isinstance(recording, Recording) or not recording.signals:
        raise ValueError('Converter must return a nonempty Recording of Signal objects')
    path = Path(path)
    if path.suffix.lower() != '.mat': raise ValueError('Paired output must use a .mat extension')
    if path.exists() and not overwrite: raise FileExistsError(path)
    data = {'recording_timestamp': recording.timestamp.isoformat()}
    for i, signal in enumerate(recording.signals, 1):
        if not isinstance(signal, Signal): raise TypeError('Recording.signals must contain Signal objects')
        # Validate mutable models again at the extension boundary.
        checked = Signal(signal.name, signal.time, signal.values, signal.unit,
                         signal.domain, signal.reference_impedance)
        if checked.domain != 'time' and (checked.time < 0).any():
            raise ValueError(f'{checked.name}: frequency coordinates must be nonnegative')
        key = f'Signal{i}'
        data[key+'_u'] = checked.values
        data[key+('_t' if checked.domain == 'time' else '_f')] = checked.time
        data[key+'_name'] = checked.name; data[key+'_unit'] = checked.unit
        data[key+'_domain'] = checked.domain
        if checked.reference_impedance is not None: data[key+'_reference_impedance'] = checked.reference_impedance
    temp = None; reserved = False
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.mat', delete=False) as file:
            temp = Path(file.name); savemat(file.file, data, do_compression=True)
        if not overwrite:
            # Reserve the name without overwriting another process's output.
            with path.open('xb'): pass
            reserved = True
        os.replace(temp, path); temp = None; reserved = False
    finally:
        if temp is not None: temp.unlink(missing_ok=True)
        if reserved: path.unlink(missing_ok=True)
    return path
