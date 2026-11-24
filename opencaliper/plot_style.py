"""Serializable per-trace line and sample-marker appearance."""
from PySide6 import QtCore
import pyqtgraph as pg

LINES = {'Solid': QtCore.Qt.PenStyle.SolidLine, 'Dashed': QtCore.Qt.PenStyle.DashLine,
         'Dotted': QtCore.Qt.PenStyle.DotLine, 'Dash-dot': QtCore.Qt.PenStyle.DashDotLine,
         'None (markers only)': QtCore.Qt.PenStyle.NoPen}
MARKERS = {'None': None, 'Circle': 'o', 'Square': 's', 'Triangle': 't', 'Diamond': 'd', 'Plus': '+', 'Cross': 'x'}
DEFAULT = dict(width=1., line='Solid', marker='None', size=6., filled=True)


def normalize(style):
    """Validate styles loaded from dialogs/workspaces before changing curves."""
    result = {**DEFAULT, **style}
    if not isinstance(result['line'], str) or not isinstance(result['marker'], str) or result['line'] not in LINES or result['marker'] not in MARKERS:
        raise ValueError('Unsupported line or marker style')
    try: result['width'], result['size'] = float(result['width']), float(result['size'])
    except (ValueError, TypeError) as exc: raise ValueError('Line width and marker size must be numeric') from exc
    if not .25 <= result['width'] <= 20 or not 1 <= result['size'] <= 40:
        raise ValueError('Line width must be 0.25–20 px and marker size 1–40 px')
    if result['line'] == 'None (markers only)' and result['marker'] == 'None':
        raise ValueError('Choose a marker when the line is disabled')
    return result


def apply(curve, style, color=None):
    """Style an existing curve without replacing its samples or visibility."""
    style = normalize(style)
    pen = pg.mkPen(curve.opts['pen'])
    if color is not None: pen.setColor(color)
    pen.setWidthF(style['width']); pen.setStyle(LINES[style['line']]); pen.setCosmetic(True)
    curve.setPen(pen)
    curve.setSymbol(MARKERS[style['marker']]); curve.setSymbolSize(style['size'])
    curve.setSymbolPen(pg.mkPen(pen.color(), width=1))
    curve.setSymbolBrush(pg.mkBrush(pen.color()) if style['filled'] else pg.mkBrush(None))
