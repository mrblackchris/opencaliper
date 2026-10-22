"""Yokogawa WVF export with companion HDR and int16 quantization."""
from pathlib import Path
from ..acquisition import write_wvf
from ._waveform import measurement


def write(recording, path, overwrite=False):
    """Write a Recording; the dispatcher validates overwrite and nonempty input."""
    path = Path(path)
    write_wvf(measurement(recording, quantized=True), path, overwrite=overwrite)
