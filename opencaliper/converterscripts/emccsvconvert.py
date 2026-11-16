"""EMC receiver CSV with Frequency and QPK/PK+/AVG Level columns.

The second header row contains units; data starts on the third row. Categorical
metadata is ignored. Exported levels are preserved; Correction is not reapplied.
"""
import csv
import io
import numpy as np
from ..core import Recording, Signal
from .pairedconvert import AXIS_UNITS, axis_scale

CONVERTER_NAME = 'EMC receiver CSV (QPK / PK+ / AVG)'
LEVELS = {'qpk level': 'Quasipeak', 'pk+ level': 'Peak', 'avg level': 'Average'}


def recognizes(text):
    """Recognize the column schema, not the filename or instrument brand."""
    for delimiter in (';', ',', '\t'):
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        header = [cell.strip().lower() for cell in next(reader, [])]
        if 'frequency' in header and any(name in header for name in LEVELS):
            units = [cell.strip().lower() for cell in next(reader, [])]
            if len(units) == len(header) and units[header.index('frequency')] in AXIS_UNITS['frequency']:
                return delimiter
    return None


def read_text(text, path):
    """Decode detector levels while retaining units and frequency coordinates."""
    delimiter = recognizes(text)
    if delimiter is None: raise ValueError('Expected Frequency and QPK Level / PK+ Level / AVG Level CSV columns')
    from .csvconvert import number
    reader = csv.reader(io.StringIO(text), delimiter=delimiter, strict=True)
    header = [cell.strip().lower() for cell in next(reader)]
    units = [cell.strip() for cell in next(reader, [])]
    if len(units) != len(header): raise ValueError('EMC CSV: expected a unit row after the column names')
    frequency_index = header.index('frequency')
    if not units[frequency_index]: raise ValueError('EMC CSV: frequency unit is missing')
    scale = axis_scale(units[frequency_index], 'frequency')
    columns = [(i, LEVELS[name]) for i, name in enumerate(header) if name in LEVELS]
    frequency, samples = [], [[] for _ in columns]
    for row in reader:
        if not row or not any(cell.strip() for cell in row): continue
        if len(row) != len(header): raise ValueError(f'EMC CSV line {reader.line_num}: wrong column count')
        try:
            frequency.append(number(row[frequency_index], delimiter != ',')*scale)
            for values, (i, _) in zip(samples, columns): values.append(number(row[i], delimiter != ','))
        except ValueError as exc: raise ValueError(f'EMC CSV line {reader.line_num}: invalid numeric sample') from exc
    axis = np.asarray(frequency)
    if not len(axis) or not np.isfinite(axis).all() or np.any(axis < 0) or np.any(np.diff(axis) <= 0):
        raise ValueError('EMC CSV frequency must be finite, nonnegative and strictly increasing; split repeated sweeps first')
    return Recording([Signal(name, axis, values, units[i], domain='frequency')
                      for (i, name), values in zip(columns, samples)], str(path))


def read(path):
    """Read an EMC receiver CSV using the common decoder for text encodings."""
    from .csvconvert import decode_text
    return read_text(decode_text(path), path)
