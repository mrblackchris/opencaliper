"""Keysight Infiniium HDF5 waveforms, converted to seconds and physical units.

Schema: /Waveforms/<name>/<name>Data with XOrg/XInc on the channel group.
Integer H5INt samples use raw * YInc + YOrg; floating H5 samples are already
physical values. YReference is internal metadata, not an ADC offset to subtract.
See https://helpfiles.keysight.com/csg/d9300a/Help/Infiniium-UG/Content/Topics/Files/HDF5_Schema.htm
"""
from datetime import datetime
import numpy as np
from ..core import Recording, Signal


def text(value):
    """Decode scalar HDF5 text without exposing byte-string notation."""
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else str(value)


def read(path):
    """Read unsegmented normal/average analog channels; reject unsupported layouts."""
    import h5py
    units = {'Volt': 'V', 'Amp': 'A', 'Second': 's', 'Hertz': 'Hz',
             'Ohm': 'Ω', 'Watt': 'W', 'Decibel': 'dB', 'NoUnit': '', 'Ratio': ''}
    signals = []
    timestamp = datetime(1970, 1, 1)
    with h5py.File(path, 'r') as file:
        marker = file.get('FileType/KeysightH5FileType')
        if marker is None or text(marker[()]) not in ('Keysight Waveform', 'Keysight Composite'):
            raise ValueError('Expected a Keysight Infiniium HDF5 waveform file')
        if 'Waveforms' not in file:
            raise ValueError('Keysight HDF5 has no Waveforms group')
        for name, group in file['Waveforms'].items():
            if not isinstance(group, h5py.Group):
                raise ValueError(f'{name}: expected a waveform group')
            attrs = group.attrs
            if int(attrs.get('NumSegments', 0)) != 0:
                raise ValueError(f'{name}: segmented HDF5 waveforms are not supported')
            if int(attrs.get('WaveformType', 1)) not in (1, 3):
                raise ValueError(f'{name}: only normal/average analog waveforms are supported')
            if text(attrs.get('XUnits', 'Second')).lower() not in ('second', 's'):
                raise ValueError(f'{name}: expected a time axis in seconds')
            dataset = group.get(name+'Data')
            if not isinstance(dataset, h5py.Dataset) or dataset.ndim != 1 or dataset.dtype.kind not in 'iuf':
                raise ValueError(f'{name}: expected a one-dimensional numeric {name}Data dataset')
            raw = dataset[()]
            if len(raw) != int(attrs.get('NumPoints', len(raw))):
                raise ValueError(f'{name}: NumPoints does not match the waveform length')
            try:
                origin, step = float(attrs['XOrg']), float(attrs['XInc'])
                values = raw.astype(float)
                if raw.dtype.kind in 'iu':
                    gain, offset = float(attrs['YInc']), float(attrs['YOrg'])
                    if not np.isfinite([gain, offset]).all() or gain == 0:
                        raise ValueError(f'{name}: invalid vertical scaling')
                    values = values*gain + offset
            except KeyError as exc:
                raise ValueError(f'{name}: missing scaling attribute {exc}') from exc
            if not np.isfinite([origin, step]).all() or step <= 0:
                raise ValueError(f'{name}: invalid time scaling')
            unit = text(attrs.get('YUnits', ''))
            signals.append(Signal(name, origin + np.arange(len(raw))*step, values, units.get(unit, unit)))
        # Acquisition time is optional and must never block valid waveform data.
        try:
            frame = file['Frame/TheFrame'][()]
            timestamp = datetime.strptime(text(np.asarray(frame['Date']).reshape(-1)[0]), '%d-%b-%Y %H:%M:%S')
        except (KeyError, ValueError, TypeError, IndexError):
            pass
    if not signals:
        raise ValueError('Keysight HDF5 contains no waveforms')
    return Recording(signals, str(path), timestamp)
