"""LTspice transient RAW export."""
from pathlib import Path
from ..raw import write_raw
from ._waveform import measurement


def write(recording, path, overwrite=False):
    """Write a Recording; the dispatcher validates overwrite and nonempty input."""
    path = Path(path)
    write_raw(measurement(recording), path, overwrite=overwrite)
