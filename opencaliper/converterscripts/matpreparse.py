"""Inspect MAT variable names before choosing one or more supported decoders.

Storage detection (classic MAT versus v7.3) happens in acquisition.load_mat.
This pre-parser detects semantic layouts without changing or copying samples.
Files containing multiple supported layouts retain channels from every layout.
"""
import re
from .pairedconvert import prefixes


def detect_layouts(data):
    """Return recognized layout identifiers in deterministic import order."""
    layouts = []
    if any(re.fullmatch(r'signal_\d+_values', key) for key in data): layouts.append('native')
    if prefixes(data): layouts.append('paired')
    if 'freq' in data and any(key in data for key in ('avg', 'peak', 'pk', 'qpk')): layouts.append('receiver')
    if 'xinc' in data and 'points' in data and any(re.fullmatch(r'Channel\d+_t1', key) for key in data):
        layouts.append('acquisition')
    return tuple(layouts)
