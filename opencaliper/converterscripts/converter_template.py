"""Copy this file, adapt read(path), then select it in the Converter window.

No registry change is needed for manually selected scripts. Return physical
samples in a Recording; OpenCaliper handles paired MAT output and file naming.
"""
from pathlib import Path
import numpy as np
from opencaliper import Recording, Signal

CONVERTER_NAME = 'My custom converter'
CONVERTER_TEMPLATE = True  # Remove this line from your working converter.


def read(path):
    """Example: two-column comma-separated numeric time/amplitude data."""
    path = Path(path)
    data = np.loadtxt(path, delimiter=',', ndmin=2)
    if data.shape[1] != 2:
        raise ValueError('Expected two columns: seconds, amplitude')
    signal = Signal('My signal', data[:, 0], data[:, 1], 'V', domain='time')
    # Frequency example: Signal('Peak', frequency_hz, levels, 'dB', domain='frequency')
    return Recording([signal], source=str(path))
