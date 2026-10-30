"""Touchstone S2P/S4P to complex, dimensionless Sij signals on a Hz axis.

Supports RI, MA and DB pairs and single-ended v1 / v2 Full, Lower and Upper
matrices. Two-port full data defaults to S11,S21,S12,S22; four-port data is
row-major. The option line, not descriptive comments, determines the encoding.
Reference impedances are retained per output port, without renormalization.
Mixed-mode declarations and other network parameter types are rejected.
Specification: https://www.ibis.org/touchstone_ver2.0/touchstone_ver2_0.pdf
"""
from pathlib import Path
import re
import numpy as np
from ..core import Recording, Signal


def numbers(line):
    """Read numeric tokens, accepting instrument exports with Fortran exponents."""
    try:
        return [float(token.replace('D', 'E').replace('d', 'e')) for token in line.split()]
    except ValueError as exc:
        raise ValueError(f'Invalid Touchstone numeric data: {line[:80]}') from exc


def read(path):
    """Return all four or sixteen Sij channels with their complex samples intact."""
    path = Path(path)
    ports = int(path.suffix[2:-1])
    scale, encoding, resistance = 1e9, 'MA', 50.
    matrix, order = 'full', '21_12'
    values, references = [], []
    count = None
    section, version, option_seen = 'network', '1.0', False
    for line_number, raw in enumerate(path.read_text(encoding='utf-8-sig', errors='replace').splitlines(), 1):
        line = raw.split('!', 1)[0].strip()
        if not line: continue
        if section == 'information' and line.lower() != '[end information]': continue
        if line.startswith('['):
            match = re.fullmatch(r'\[([^]]+)\]\s*(.*)', line)
            if not match: raise ValueError(f'Touchstone line {line_number}: malformed keyword')
            key, argument = match[1].lower(), match[2].strip()
            if key == 'begin information': section = 'information'
            elif key == 'end information': section = 'header'
            elif key == 'version':
                version = argument
                if version not in ('1.0', '2.0', '2.1'): raise ValueError('Unsupported Touchstone version')
                section = 'header'
            elif key == 'number of ports':
                if int(argument) != ports: raise ValueError('Touchstone port count disagrees with filename')
            elif key == 'number of frequencies': count = int(argument)
            elif key == 'number of noise frequencies': pass
            elif key in ('two-port data order', 'two-port order'):
                order = argument.lower()
                if order not in ('21_12', '12_21'): raise ValueError('Unsupported two-port data order')
            elif key == 'matrix format':
                matrix = argument.lower()
                if matrix not in ('full', 'lower', 'upper'): raise ValueError('Unsupported Touchstone matrix format')
            elif key == 'reference':
                references.extend(numbers(argument)); section = 'reference'
            elif key == 'network data': section = 'network'
            elif key == 'noise data': section = 'noise'
            elif key == 'end': break
            else: raise ValueError(f'Unsupported Touchstone keyword [{match[1]}]')
            continue
        if section == 'information': continue
        if line.startswith('#'):
            if option_seen: continue
            option_seen = True
            tokens = line[1:].upper().split()
            while tokens:
                token = tokens.pop(0)
                if token in ('HZ', 'KHZ', 'MHZ', 'GHZ'):
                    scale = {'HZ': 1., 'KHZ': 1e3, 'MHZ': 1e6, 'GHZ': 1e9}[token]
                elif token in ('RI', 'MA', 'DB'): encoding = token
                elif token == 'S': pass
                elif token == 'R' and tokens: resistance = numbers(tokens.pop(0))[0]
                else: raise ValueError(f'Unsupported Touchstone option {token}; expected S-parameters')
        elif section == 'reference': references.extend(numbers(line))
        elif section == 'network': values.extend(numbers(line))
        elif section == 'noise': continue
        else: raise ValueError(f'Touchstone line {line_number}: data outside [Network Data]')
    if not option_seen: raise ValueError('Touchstone file is missing its # option line')
    if not np.isfinite(resistance) or resistance <= 0:
        raise ValueError('Touchstone reference resistance must be finite and positive')
    if not references: references = [resistance]*ports
    if len(references) != ports or not np.isfinite(references).all() or np.any(np.asarray(references) <= 0):
        raise ValueError('Touchstone requires one positive reference resistance per port')
    indices = [(r, c) for r in range(ports) for c in range(ports)
               if matrix == 'full' or (matrix == 'lower' and c <= r) or (matrix == 'upper' and c >= r)]
    if ports == 2 and matrix == 'full' and order == '21_12':
        indices = [(0, 0), (1, 0), (0, 1), (1, 1)]
    width = 1 + 2*len(indices)
    if not values or len(values) % width:
        raise ValueError('Incomplete Touchstone frequency/matrix data (legacy noise blocks are not supported)')
    data = np.asarray(values).reshape(-1, width)
    if not np.isfinite(data).all(): raise ValueError('Touchstone data must be finite')
    if count is not None and len(data) != count: raise ValueError('Touchstone frequency count does not match data')
    frequency = data[:, 0]*scale
    if np.any(frequency < 0) or np.any(np.diff(frequency) <= 0):
        raise ValueError('Touchstone frequencies must be nonnegative and strictly increasing')
    a, b = data[:, 1::2], data[:, 2::2]
    if encoding == 'RI': complex_values = a + 1j*b
    else:
        if encoding == 'MA' and np.any(a < 0): raise ValueError('Touchstone magnitudes cannot be negative')
        with np.errstate(over='ignore'):
            magnitude = 10.**(a/20) if encoding == 'DB' else a
        complex_values = magnitude*np.exp(1j*np.deg2rad(b))
    if not np.isfinite(complex_values).all(): raise ValueError('Touchstone amplitudes overflow numeric range')
    scattering = np.empty((len(data), ports, ports), dtype=complex)
    for i, (r, c) in enumerate(indices):
        scattering[:, r, c] = complex_values[:, i]
        if matrix != 'full': scattering[:, c, r] = complex_values[:, i]
    return Recording([Signal(f'S{r+1}{c+1}', frequency, scattering[:, r, c], '',
                             domain='sparameter', reference_impedance=references[r])
                      for r in range(ports) for c in range(ports)], str(path))
