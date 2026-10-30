"""Shared signal model and public converter entry points.

Format implementations and their documented contract live in converterscripts/.
"""
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np


@dataclass
class Signal:
    """One channel with a horizontal axis and numeric sample values.
    
    @param name Human-readable channel name.
    @param time Nonempty finite nondecreasing axis: seconds or Hz, per domain.
    @param values Matching numeric amplitudes; complex and nonfinite values are allowed.
    @param unit Physical amplitude unit, or an empty string if unspecified.
    
    @param domain "time" (seconds), "frequency" (Hz), or "sparameter" (Hz).
    @param reference_impedance Positive real port reference resistance in ohms for S-parameters.

    The time field holds horizontal coordinates in all three domains. Arrays are
    flattened during initialization. Individual operations impose additional
    constraints. Frequency-domain source and FFT signals use time for Hz.
    The dataclass is mutable; display code should treat source arrays as read-only."""
    name: str
    time: np.ndarray
    values: np.ndarray
    unit: str = ""
    domain: str = "time"
    reference_impedance: float | None = None

    def __post_init__(self):
        if self.domain not in ("time", "frequency", "sparameter"):
            raise ValueError("Signal domain must be time, frequency or sparameter")
        if self.domain == 'sparameter' and self.reference_impedance is None:
            self.reference_impedance = 50.
        if self.reference_impedance is not None:
            self.reference_impedance = float(self.reference_impedance)
            if not np.isfinite(self.reference_impedance) or self.reference_impedance <= 0:
                raise ValueError('Reference impedance must be finite and positive')
        self.time = np.asarray(self.time, dtype=float).reshape(-1)
        self.values = np.asarray(self.values).reshape(-1)
        if len(self.time) != len(self.values) or not len(self.time):
            raise ValueError(f"{self.name}: empty or mismatched samples")
        if not np.isfinite(self.time).all() or np.any(np.diff(self.time) < 0):
            raise ValueError(f"{self.name}: time must be finite and nondecreasing")
        if self.values.dtype.kind not in 'biufc':
            raise ValueError(f"{self.name}: numeric samples required")

    def region(self, start=None, stop=None):
        """Select existing samples in an inclusive horizontal interval.
        
        @param start Lower bound, or None for the beginning.
        @param stop Upper bound, or None for the end.
        @return Tuple of sliced axis and value arrays, possibly empty.
        
        Two supplied bounds are sorted. Boundary samples are not interpolated."""
        a, b = sorted((start, stop)) if start is not None and stop is not None else (start, stop)
        left = np.searchsorted(self.time, a) if a is not None else 0
        right = np.searchsorted(self.time, b, side='right') if b is not None else len(self.time)
        return self.time[left:right], self.values[left:right]



@dataclass
class Recording:
    """Group channels and their acquisition metadata.
    
    @param signals List of Signal objects, possibly with independent time axes.
    @param source Source path or descriptive string; empty for constructed data.
    @param timestamp Acquisition datetime; defaults to the naive Unix epoch.
    
    This container does not itself validate the channel list."""
    signals: list[Signal]
    source: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime(1970, 1, 1))



def load(filename):
    """Detect the input format and return a Recording of physical samples.

    See converterscripts/README.md for reader contracts and adding formats.
    """
    from .converterscripts.convert import load as read_recording
    return read_recording(filename)


def export(recording, filename, overwrite=False):
    """Select an exporter by suffix and write a Recording; return its path.

    Existing files are refused unless overwrite=True. Format-specific
    restrictions are checked by the exporter before writing samples.
    """
    from .converterscripts.convert import export as write_recording
    return write_recording(recording, filename, overwrite=overwrite)
