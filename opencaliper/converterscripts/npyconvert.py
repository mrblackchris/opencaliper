"""Memory-mapped NumPy time/channel columns."""
from pathlib import Path
import numpy as np
from ..core import Signal, Recording



def read(path):
    """Convert this file into OpenCaliper physical channels; see README.md."""
    path = Path(path)
    # NPY is a simple memory-mapped large-recording interchange format:
    # column zero is seconds, remaining columns are real-valued channels.
    data = np.load(path, mmap_mode='r', allow_pickle=False)
    if data.ndim != 2 or data.shape[1] < 2 or data.dtype.kind not in 'biuf':
        raise ValueError('NPY input must be a real numeric N×(1+channels) array')
    return Recording([Signal(f'Channel{i}', data[:, 0], data[:, i])
                      for i in range(1, data.shape[1])], str(path))
