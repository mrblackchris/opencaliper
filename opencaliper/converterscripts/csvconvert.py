"""CSV table pre-parser for shared axes and named PREFIX_u/PREFIX_t/PREFIX_f pairs.

Detect comma, semicolon, tab, pipe or whitespace separators. Skip metadata before
the first numeric row, retaining column names and optional unit rows. Numeric
rows after that point are strict: malformed rows are reported, never discarded.
Unlabelled tables use column one as seconds and remaining columns as amplitudes.
"""
import csv
from dataclasses import dataclass
import io
from pathlib import Path
import re
import numpy as np
from ..core import Recording, Signal
from .pairedconvert import AXIS_UNITS, axis_scale, prefixes, read_data


MISSING = {'', 'na', 'n/a', 'null', 'none', 'nan'}


def number(cell, decimal_comma=False):
    """Parse one real sample, including missing amplitudes and scientific notation."""
    cell = cell.strip()
    if cell.lower() in MISSING: return np.nan
    if decimal_comma and ',' in cell:
        if '.' in cell or cell.count(',') != 1: raise ValueError('Ambiguous decimal/thousands separators')
        cell = cell.replace(',', '.')
    return float(cell.replace('D', 'E').replace('d', 'e'))


def label(cell):
    """Split a column label from its optional bracketed/parenthesized unit."""
    cell = cell.strip()
    match = re.fullmatch(r'(.*?)\s*(?:\[([^\]]+)\]|\(([^)]+)\))', cell)
    if match:
        name, unit = match[1].strip(), (match[2] or match[3]).strip()
        # SPICE names such as V(out) and I(R1) are labels, not unit annotations.
        if match[3] is not None and name in ('V', 'I') and unit.lower() not in ('v', 'a', 'mv', 'ma', 'uv', 'ua', 'µv', 'µa'):
            return cell, ''
        return name, unit
    if '/' in cell:
        name, unit = cell.rsplit('/', 1)
        if unit.strip().lower() in {*AXIS_UNITS['time'], *AXIS_UNITS['frequency']}:
            return name.strip(), unit.strip()
    return cell, ''


def axis_kind(name):
    """Recognize explicit shared-axis names without interpreting arbitrary signals."""
    key = name.strip().lower()
    if key in ('time', 't', 'timestamp'): return 'time'
    if key in ('frequency', 'freq', 'f'): return 'frequency'
    return None


def records(text, delimiter):
    """Yield source-line numbers, fields and comment status for one separator."""
    if delimiter is None:
        rows = ((n, line.split()) for n, line in enumerate(text.splitlines(), 1))
    else:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter, strict=True)
        rows = ((reader.line_num, row) for row in reader)
    for line, row in rows:
        row = [cell.strip() for cell in row]
        if not row or not any(row): continue
        comment = row[0].startswith(('#', '!', '//'))
        if comment:
            row[0] = re.sub(r'^(?:#|!|//)\s*', '', row[0])
        yield line, row, comment


@dataclass
class Table:
    """Detected CSV dialect, physical data rows, labels and optional units."""
    values: np.ndarray
    labels: list[str]
    units: list[str]
    lines: list[int]
    score: tuple


def parse_table(text, delimiter):
    """Locate one numeric table and validate every non-comment data row."""
    decimal_comma = delimiter != ','
    before, rows, lines = [], [], []
    width = None
    for line, cells, comment in records(text, delimiter):
        if comment:
            if width is None: before.append((line, cells, True))
            continue
        try: numeric = [number(cell, decimal_comma) for cell in cells]
        except ValueError:
            if width is None:
                before.append((line, cells, False)); continue
            raise ValueError(f'CSV line {line}: nonnumeric data inside the table') from None
        if width is None:
            if len(cells) < 2:
                before.append((line, cells, False)); continue
            width = len(cells)
        if len(cells) != width:
            raise ValueError(f'CSV line {line}: expected {width} columns, found {len(cells)}')
        rows.append(numeric); lines.append(line)
    if not rows: raise ValueError('CSV has no numeric table with at least two columns')
    values = np.asarray(rows)
    # Prefer a recognizable axis/pair header over a later free-text comment row.
    headers = []
    for line, cells, comment in before:
        if len(cells) != width: continue
        labels = [label(cell)[0] for cell in cells]
        recognized = sum(axis_kind(name) is not None or bool(re.fullmatch(r'.+_[utf]', name)) for name in labels)
        try:
            for cell in cells: number(cell, decimal_comma)
            continue
        except ValueError: pass
        if not comment or recognized:
            headers.append((recognized, -line, cells))
    header = max(headers, key=lambda item: item[:2]) if headers else None
    cells = header[2] if header else ['']*width
    parts = [label(cell) for cell in cells]
    labels, units = [p[0] for p in parts], [p[1] for p in parts]
    # Many instruments write column names, then a separate unit row.
    known_units = {*AXIS_UNITS['time'], *AXIS_UNITS['frequency'], 'v', 'mv', 'uv', 'µv',
                   'a', 'ma', 'ua', 'µa', 'w', 'ohm', 'ω', 'db', 'dbm', 'deg', 'rad', ''}
    unit_rows = [(line, row) for line, row, comment in before if not comment and len(row) == width
                 and all(cell.lower() in known_units for cell in row)]
    if unit_rows:
        unit_line, unit_row = unit_rows[-1]
        if header is None or -header[1] <= unit_line:
            for i, unit in enumerate(unit_row):
                if not units[i]: units[i] = unit
            if header is not None and header[2] == unit_row: labels = ['']*width
    if not header and width == 2:
        titles = [row[0] for _, row, comment in before if not comment and len(row) == 1]
        if titles: labels[1], units[1] = label(titles[0])
    # Ignore an entirely empty trailing column caused by a trailing separator.
    keep = list(range(width))
    while len(keep) > 2 and not labels[keep[-1]] and np.isnan(values[:, keep[-1]]).all(): keep.pop()
    labels = [labels[i] for i in keep]; units = [units[i] for i in keep]
    values = values[:, keep]
    return Table(values, labels, units, lines,
                 (header[0] if header else 0, len(rows), len(keep)))


def detect_table(text):
    """Choose a valid delimiter; do not hide malformed body rows by skipping them."""
    valid, errors = [], []
    for delimiter in (',', ';', '\t', '|', None):
        try: valid.append(parse_table(text, delimiter))
        except (ValueError, csv.Error) as exc: errors.append(str(exc))
    if not valid:
        detailed = next((message for message in errors if 'CSV line' in message), errors[0])
        raise ValueError(detailed+'; expected a time/frequency column followed by numeric signals')
    return max(valid, key=lambda table: table.score)


def read(path):
    """Import shared time/frequency columns or explicitly named independent pairs."""
    path = Path(path)
    raw = path.read_bytes()
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')): text = raw.decode('utf-16')
    else:
        try: text = raw.decode('utf-8-sig')
        except UnicodeDecodeError: text = raw.decode('cp1252')
    table = detect_table(text)
    names, units, values = table.labels, table.units, table.values
    paired = prefixes({name: None for name in names})
    if paired:
        data = {}
        for prefix in paired:
            for suffix in ('u', 't', 'f'):
                key = prefix+'_'+suffix
                columns = [i for i, name in enumerate(names) if name == key]
                if len(columns) > 1: raise ValueError(f'CSV has duplicate paired column {key}')
                if columns:
                    i = columns[0]; data[key] = values[:, i]
                    data[prefix+'_unit' if suffix == 'u' else key+'_unit'] = units[i]
            axes = [suffix for suffix in ('t', 'f') if prefix+'_'+suffix in data]
            if len(axes) != 1:
                raise ValueError(f'{prefix}_u: expected exactly one corresponding {prefix}_t or {prefix}_f column')
            if len(axes) == 1:
                axis_key = prefix+'_'+axes[0]
                # Independent pairs may be padded with empty cells at the end.
                mask = ~(np.isnan(data[axis_key]) & np.isnan(data[prefix+'_u']))
                valid = np.flatnonzero(mask)
                if len(valid) and not mask[:valid[-1]+1].all():
                    raise ValueError(f'{prefix}: missing axis and amplitude inside the CSV table')
                data[axis_key] = data[axis_key][mask]; data[prefix+'_u'] = data[prefix+'_u'][mask]
        used = {prefix+'_'+suffix for prefix in paired for suffix in ('u', 't', 'f')}
        if any(name not in used for name in names):
            raise ValueError('CSV paired tables require every column to belong to a PREFIX_u / PREFIX_t or PREFIX_f pair')
        return read_data(data, path)
    axes = [(i, axis_kind(name)) for i, name in enumerate(names) if axis_kind(name)]
    if len(axes) > 1: raise ValueError('CSV has multiple shared axes; use named PREFIX_u / PREFIX_t or PREFIX_f pairs')
    axis_index, domain = axes[0] if axes else (0, 'frequency' if units[0].lower() in AXIS_UNITS['frequency'] else 'time')
    axis = values[:, axis_index]*axis_scale(units[axis_index], domain)
    if not np.isfinite(axis).all():
        row = int(np.flatnonzero(~np.isfinite(axis))[0])
        raise ValueError(f'CSV line {table.lines[row]}: horizontal coordinate is missing or nonfinite')
    if domain == 'frequency' and np.any(axis < 0): raise ValueError('CSV frequencies must be nonnegative')
    signals = []
    for i, name in enumerate(names):
        if i == axis_index or (axes and name.lower() in ('index', 'sample', 'point', 'unnamed: 0')): continue
        signals.append(Signal(name or f'Channel{len(signals)+1}', axis, values[:, i], units[i], domain=domain))
    if not signals: raise ValueError('CSV contains no amplitude columns')
    return Recording(signals, str(path))
