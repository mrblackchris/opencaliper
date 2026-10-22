# Command-line guide

Use Python 3.10 or newer with the project and its dependencies installed. Commands
below run from the source folder or an environment where OpenCaliper is installed.
`python -m opencaliper` and the installed `opencaliper` command are equivalent.
Use `python3` or `py -3` if that selects your desired interpreter.

## Launch the GUI

```bash
python run_opencaliper.py
python run_opencaliper.py examples/example.mat
python -m opencaliper gui examples/example.mat
```

The root script uses the current interpreter and forwards measurement paths.
The `start_opencaliper.sh`/`.bat` launchers manage `.venv`; the
`start_opencaliper_no_venv.sh`/`.bat` launchers use the current Python environment
without creating an environment or installing dependencies. See the
[installation guide](../README.md#easy-start-on-windows-and-linux).

## Inspect channels

```bash
python -m opencaliper info recording.mf4
```

The JSON list contains the zero-based channel index, name, amplitude unit,
`domain`, `axis_unit`, sample count and first/last horizontal coordinates.
Time data uses seconds; frequency sources use Hz. Numeric MDF state channels
retain their codes even when the file provides text labels.

## Statistics

```bash
python -m opencaliper stats recording.mat --signal 0 --start 0.1 --stop 0.5
```

Bounds select inclusive existing samples; reversed bounds are sorted. Without
bounds, the full channel is used. Frequency-domain sources interpret bounds in
Hz, time-domain sources in seconds. Output is JSON: count, minimum, maximum,
peak-to-peak, mean, RMS and population standard deviation. Nonfinite samples are
excluded, and complex data is analyzed by magnitude.

## FFT to CSV

```bash
python -m opencaliper fft recording.mf4 spectrum.csv --signal 0
python -m opencaliper fft recording.mf4 spectrum.csv --signal 0 --start 1 --stop 2
python -m opencaliper fft recording.mf4 spectrum.csv --signal 0 --resample
python -m opencaliper fft recording.mf4 spectrum.csv --signal 0 --resample --sample-rate 1000
```

FFT operates on time data only, with at least four finite real samples. It removes
the mean, applies a Hann window and writes `frequency_Hz,amplitude` columns in CSV.
Amplitude is one-sided peak amplitude in the original unit, not dB or PSD.
The output filename must be new; FFT CSV output has no overwrite option.

Uniform timestamps are required unless `--resample` is specified. Resampling
linearly interpolates within the selected interval; `--sample-rate` sets Hz and
requires `--resample`. If omitted, the rate is reciprocal median timestamp spacing.
Duplicate timestamps and NaN/Inf amplitudes are rejected. Original data is not
modified. Interpolation does not recover missing bandwidth or provide an
anti-alias filter. See [FFT troubleshooting](USER_GUIDE.md#fft-input-errors).

## Convert and export

```bash
python -m opencaliper convert recording.mdf recording.mat
python -m opencaliper convert recording.mat recording.wvf
python -m opencaliper convert recording.mat recording.mf4 --overwrite
mat2raw recording.mat recording.raw
```

The input and output extensions select the adapters. Conversion preserves the
source file and rejects identical input/output paths. Existing destinations
require `--overwrite`; WVF writes a companion HDR. Native MAT preserves channel
names, units, horizontal coordinates, domain and acquisition timestamp. Time-only
exporters can impose stricter constraints and discard device metadata.

For automatic native-MAT output naming, use the dedicated dispatcher:

```bash
python -m opencaliper.converterscripts recording.mf4
python opencaliper/converterscripts/convert.py recording.wvf recording.mat
```

The first command creates `recording.opencaliper.mat`. ESRP receiver MAT spectra
are recognized from `freq` and detector vectors. They remain frequency-domain data
when converted to native MAT; MDF/RAW/WVF exports reject frequency-domain sources.
The [converter guide](../opencaliper/converterscripts/README.md) lists supported
adapters, limits and the extension contract.

## Help and failures

Use `python -m opencaliper --help` or append `--help` to a subcommand. Runtime
failures print `Error: ...` to stderr and return status 1. Argument parsing errors
return status 2. These commands need no desktop session except `gui`.
