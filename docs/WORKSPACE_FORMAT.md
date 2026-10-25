# Workspace format and persistence

A `.ocw` file is a portable snapshot of loaded data and plot state. Create it with
**Workspace → Save workspace** and restore it with **Open workspace**. Opening
replaces the current session; structural undo can recover it. Source files need
not remain available because all loaded arrays are embedded.

This format differs from [native MAT](MAT_FORMAT.md#opencaliper-mat-exports), which
stores interchangeable channels and acquisition timestamp without the GUI layout.

## Archive layout (version 1)

The archive uses ZIP with deflate compression and ZIP64 support:

```text
workspace.json
0-time.npy
0-values.npy
1-time.npy
1-values.npy
...
```

The prefix is a channel ID, which can have gaps. NumPy entries use the normal NPY
format without pickled objects. Horizontal arrays are seconds or Hz according to
the channel's domain. Channel data is loaded into memory when restoring an archive;
workspace restore is not a memory-mapped streaming reader.

The JSON object contains:

| Key | Meaning |
| --- | --- |
| `version` | Integer schema version; currently `1` |
| `channels` | Object keyed by channel ID strings, with `name`, `unit`, `domain` |
| `files` | List of `[source_display_name, [channel_ids...]]` explorer groups |
| `pages` | Ordered tab descriptions |
| `current` | Zero-based active tab index |

Each page contains:

| Key | Meaning |
| --- | --- |
| `title`, `kind` | Tab label and `time` or `spectrum`; legacy `fft` is accepted and migrated |
| `interval` | Applied FFT input time bounds `[start, stop]`, each nullable |
| `resample`, `sample_rate` | Applied FFT interpolation setting and Hz; `0` means Auto |
| `pending` | Source IDs whose FFT failed, retained for retry |
| `cursors`, `visible` | Physical A/B positions and visibility |
| `zoom` | Rectangle-zoom versus pan mode |
| `sizes` | Vertical subplot splitter sizes |
| `plots` | Ordered subplot descriptions |

Each plot contains:

| Key | Meaning |
| --- | --- |
| `ids` | Displayed source channel IDs in curve order |
| `colors` | Pairs `[channel_id, color_string]` |
| `names` | Pairs `[channel_id, local_display_name]` |
| `axes` | Pairs `[channel_id, axis_id]`; null axis is the main Y axis |
| `ranges` | Pairs `[axis_id, [low, high]]` in display coordinates |
| `x` | Visible horizontal bounds in physical seconds or Hz |
| `log` | `[log_x, log_y]` booleans |
| `background` | Plot background color string |
| `annotations` | `[start, stop, label]` entries in physical horizontal units |
| `sizes` | Horizontal sidebar/plot splitter sizes |

Mappings are represented as pairs to retain integer and null keys through JSON.
Additional Y-axis identifiers are rebuilt during restore; signal IDs are retained.

## What is and is not persisted

Saved state includes loaded source channels and materialized math/filter/alignment
results, source display names, time/frequency domain, plot aliases, colors, axis
assignments, view ranges, cursor positions, annotations, tab titles and applied
FFT settings. FFT curves are recalculated from embedded sources on restore.
Pending edits to FFT controls are not applied by saving; click **Recalculate**
first to save changed settings as the active analysis.

The archive does not contain source file bytes, original full file paths,
per-recording acquisition datetime, device-specific metadata, processing recipes,
undo/redo history, explorer selection/filter, the next A/B placement click, or
open spectrogram windows. Source names are explorer display names, usually
basenames. Save native MAT from an original `Recording` if its acquisition datetime
must be preserved. The GUI's **Export all** constructs a new Recording and uses
the default acquisition timestamp.

An archive embeds all loaded samples, including channels not currently plotted.
Sharing it therefore shares those measurements. Generated workspaces and local
recordings are ignored by Git and excluded from source packages.

## Restore, compatibility and undo

Readers reject unknown version numbers or page kinds. Legacy `fft` kinds map to unified Spectrum pages; default `FFT N` titles migrate to Spectrum while custom titles are kept. Version 1 tolerates older
files without `domain` (defaults to time), `names` (empty), `pending` (empty), and
resampling settings (disabled/Auto). Old readers may not support newer page kinds
or optional domain metadata. Preserve defaults when extending optional fields;
use a new version and migration logic for incompatible structural changes.

Save writes a temporary archive beside the destination and replaces it after a
successful write. Imports must finish before saving/opening or undoing. Failed
open attempts restore the previous session and show an error.

Structural history stores source arrays by reference and up to 50 snapshots.
Undoing reconstructs views, with history recording and automatic Spectrum creation
disabled during reconstruction. Unloaded source arrays can remain in memory while
referenced by undo history. Direct cursor placement/dragging and mouse navigation
are outside structural history; opening a workspace itself is undoable.

Implementation: [workspace.py](../opencaliper/workspace.py). Regression coverage:
[test_workspace.py](../tests/test_workspace.py),
[test_esrp.py](../tests/test_esrp.py), and
[test_fft_resampling.py](../tests/test_fft_resampling.py).
