# CSV import

Open `.csv` files with **Open files**, drag them into the viewer or use the
conversion dispatcher. CSV import is read-only; convert to native MAT or save a
workspace to retain imported channels.

The pre-parser detects comma, semicolon, tab, pipe and whitespace delimiters.
It finds the numeric table after leading title, comment and header rows, then
validates every data row. Blank lines and lines starting with `#`, `!` or `//`
are ignored. An unexpected text row or wrong column count inside the table is
reported with its source line number, rather than dropping samples.

## Shared horizontal axis

The usual layout is one horizontal column followed by one or more signal columns:

```csv
Time [s],Voltage [V],Current [A]
0,1.2,0.1
0.001,1.4,0.2
0.002,1.3,0.15
```

Column names and units are optional. With no recognizable header, the first
column is time in seconds and remaining columns are named Channel1, Channel2,
and so on. An explicit `Time`, `Timestamp` or `t` header identifies seconds;
`Frequency`, `freq` or `f` identifies Hz and opens the signal in Spectrum without
FFT. Axis names are case-insensitive. When an explicit axis exists, an extra
`Index`, `Sample`, `Point` or `Unnamed: 0` column is ignored.

Units can follow names in square brackets or parentheses, or occupy a separate
row between headers and samples. Supported horizontal units are s, ms, us/µs/μs,
ns, ps, Hz, kHz, MHz, GHz and THz. Horizontal values are converted to seconds/Hz.
Amplitude values retain their supplied scale and unit: a value of 100 labelled
mV stays 100 mV. Unspecified amplitude units remain empty.

```text
Time;Supply
ms;V
0,0;1,25
2,5;1,30
```

This semicolon table uses decimal commas and converts 2.5 ms to 0.0025 seconds.
Comma-delimited tables use decimal points. Thousands separators are unsupported.
Quoted fields, such as `"Voltage, supply"`, are supported with explicit delimiters.
Whitespace tables work best with single-word column names.

## Measurement name and comment before samples

Numeric data can begin on the third row, as in:

```text
Supply voltage
Measured at the DC link
0,12.1
0.001,12.2
0.002,12.0
```

For a two-column table without column headers, the first single-field title is
used as the signal name. Multi-channel tables without headers get default names.
A name/header row followed by a free-text comment also works:

```csv
Time,Supply voltage
Comment: nominal load
0,12.1
0.001,12.2
```

Recognizable axis/pair headers take precedence over free-text metadata. When
several unrecognized rows have the table's width, the earliest is used as the
header. Numeric-only metadata can be indistinguishable from samples; label it
or prefix it with a comment marker. Files with numeric tables interrupted by
repeated headers, footers or unrelated blocks must be split into separate files.

## Independent named signal pairs

CSV also accepts columns named `PREFIX_u` with `PREFIX_t` or `PREFIX_f`:

```csv
Signal1_t [ms],Signal1_u [V],Signal2_f [MHz],Signal2_u [dB]
0,1,1,-40
2,3,2,-30
4,5,,
```

`_u` contains amplitudes; `_t` means seconds and `_f` means Hz before optional
unit scaling. Every column in this layout must belong to a complete pair. A
prefix with both `_t` and `_f` is ambiguous and is rejected. Independent pairs
may end at different rows using trailing empty cells for both axis and amplitude.
Missing coordinates inside a pair are rejected. Missing amplitudes with a valid
axis are retained as NaN.

## Missing data, encodings and limitations

Blank, NA, N/A, null, none and NaN amplitude cells are retained as NaN. Horizontal
values must be finite, real and nondecreasing; frequencies must be nonnegative.
Samples are never sorted or resampled. Unsupported/ambiguous layouts give an
error. Plain CSV does not describe an S-parameter matrix or reference impedance;
use Touchstone for that. Complex-number CSV cells and ISO datetime columns are
not supported; use numeric seconds/Hz and native MAT for complex samples.

UTF-8 (with or without BOM), UTF-16 with BOM and Windows-1252 text are accepted.
The importer expects one numeric table per file and loads it into memory.

```sh
python -m opencaliper.converterscripts capture.csv capture.mat
python -m opencaliper info capture.csv
```

Implementation: [csvconvert.py](../opencaliper/converterscripts/csvconvert.py).
