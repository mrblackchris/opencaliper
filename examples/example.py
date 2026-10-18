"""Generate a synthetic four-channel MAT file using the acquisition convention.

Run: python example.py
Or:  python example.py --output another-example.mat
All samples are synthetic physical voltages, stored as float32. No hardware needed.
"""
import argparse
from pathlib import Path

import hdf5storage
import numpy as np


def create_example(output):
    """Write the same field layout and HDF5 storage style as an acquisition file."""
    points = 4096
    xinc = 1e-6  # Seconds between stored samples.
    xorg = -1e-3  # Time origin in seconds.
    xref = 0.0  # Reference sample index.
    t = xorg + (np.arange(points) - xref) * xinc
    data = {
        'points': points,
        'xinc': xinc,
        'xorg': xorg,
        'xref': xref,
        'samplerate': 1.0 / xinc,
        'count': 1,
        'format': 'WORD',  # Acquisition metadata, not the saved sample dtype.
        'date': '2026-01-01',
        'time': '12:00:00',
    }
    waves = [
        np.sin(2 * np.pi * 10_000 * t),
        0.5 * np.sin(2 * np.pi * 25_000 * t + np.pi / 4),
        np.where(np.sin(2 * np.pi * 5_000 * t) >= 0, 3.3, 0.0),
        0.2 * np.sin(2 * np.pi * 10_000 * t) + 0.1 * np.sin(2 * np.pi * 80_000 * t),
    ]
    for number, values in enumerate(waves, 1):
        # Despite its name, _t1 contains amplitudes, not timestamps.
        data[f'Channel{number}_t1'] = values.astype(np.float32)
        data[f'Channel{number}_unit'] = 'VOLT'
        data[f'Channel{number}_yinc'] = 0.001
        data[f'Channel{number}_offset'] = 0.0
    output = Path(output)
    # Same HDF5/MATLAB-compatible storage method as the acquisition script.
    # The chosen output file is replaced when it already exists.
    hdf5storage.write(data, '.', filename=str(output), matlab_compatible=True,
                      compression='gzip', truncate_existing=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('example.mat'))
    args = parser.parse_args()
    print(f'Created {create_example(args.output)} (4 channels, 4096 samples each)')


if __name__ == '__main__':
    main()
