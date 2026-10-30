# Keysight HDF5 and S-parameter measurements

## Keysight oscilloscope HDF5

Open a `.h5` or `.hdf5` file with **Open files**, drag it into the explorer,
or pass its path to `run_opencaliper.py`. Expand the measurement and drag its
channels into a Time Analysis plot. Dropping it onto a Spectrum plot computes
the same FFT as other time channels.

`converterscripts/h5convert.py` supports the Keysight Infiniium waveform/composite
layout with `/FileType/KeysightH5FileType` and
`/Waveforms/<channel>/<channel>Data`. Each analog waveform becomes a signal named
after its channel group. Time is `XOrg + arange(NumPoints) * XInc` in seconds.
Integer H5INt samples become `raw * YInc + YOrg`; floating H5 samples are already
physical values and are not scaled again. `YReference` and display-origin
attributes do not alter this conversion. Volt/Amp become V/A. Recognizable
acquisition dates are read; missing or malformed dates never prevent loading.

Normal and average, unsegmented, one-dimensional analog waveforms are supported.
Peak-detect pairs, digital buses, histograms, segmented records and non-time
axes are rejected. Arbitrary HDF5 files are not Keysight waveform files; use
`.mat` for supported MATLAB v7.3 layouts. The reader closes the HDF5 file after
materializing its samples. The supplied local `examples/1.h5` has two channels,
each with 7,993 samples. Tests use it when available and also generate fixtures.

## Touchstone S2P and S4P

Opening a `.s2p` or `.s4p` file immediately plots its four or sixteen Sij channels
in an **S Parameter** tab. **New S Parameter Analysis** creates another empty
page; drag signals from the explorer into it to compare measurements. Frequency
axes use Hz and default to logarithmic X. No FFT is applied to network data.

The **S-parameter view** selector offers magnitude in dB (`20*log10(abs(Sij))`),
linear magnitude, wrapped phase in degrees, unwrapped phase in degrees, real
and imaginary components. All plots in a page share this setting; use another
page for a different representation. Zero magnitude is −infinity dB and is
omitted by finite plot bounds. Complex source samples remain unchanged.

Checkboxes/Space, colors, plot-local renaming, independent Y axes, statistics,
annotations and plot exports work as usual. Cursor X positions/differences are
Hz; Y readouts interpolate the displayed representation. Wrapped phase has a
discontinuity at ±180 degrees; use unwrapped phase to interpolate across it.

### Touchstone interpretation and limits

`converterscripts/touchstoneconvert.py` reads RI (real/imaginary), MA (linear
magnitude/angle) and DB (dB magnitude/angle) pairs, with angles in degrees. The
`#` option line determines encoding, independently of comments. Hz/kHz/MHz/GHz
become Hz. Defaults are GHz, S, MA, R 50. Comments, wrapped matrix rows,
case-insensitive extensions and scientific notation are supported.

Two-port full data defaults to S11, S21, S12, S22. Version-2
`[Two-Port Data Order] 12_21` selects S11, S12, S21, S22. Four-port full data is
row-major: S11, S12, S13, S14, S21, and so on. Sij is the response at port i to
an excitation at port j. The supplied `SCD_gen.s4p` declares `# Hz S DB R 50`;
its pairs are dB/angle despite Real/Imag comment headings.

Single-ended version-1 files and the version-2 subset for port count, frequency
count, full/lower/upper matrices, per-port real reference resistance, information
and separated noise sections are supported. Triangular matrices are expanded
symmetrically. Version 2.1 using this subset is accepted. Noise data is not
imported; legacy unseparated noise blocks are unsupported. Mixed-mode
declarations, complex/frequency-dependent reference impedances, other port
counts and Y/Z/H/G network parameters are unsupported. There is no port
renumbering, mixed-mode conversion, renormalization, TDR or calibration.
Invalid/truncated matrices are rejected.

## Smith chart

Click **Smith chart…** to open a snapshot of currently visible S11, S22, S33
and S44 traces. Display a reflection channel first; hidden traces are omitted.
Transmission coefficients are not interpreted as impedances. Reopen the chart
after changing the page's traces, visibility, colors or names.

The chart plots Γ in the complex plane over a normalized impedance grid, with
equal X/Y scaling. Each legend entry shows its reference resistance Z0 from
the file. Hover to read the nearest sample's frequency, Γ and
`Z = Z0 * (1 + Γ) / (1 - Γ)` in ohms. Γ=1 is an open circuit. Active reflections
outside the unit circle remain visible. **Export chart…** saves PNG, SVG or PDF.
Smith-chart windows are not stored in workspaces; reopen them after restoring.

## Conversion and portable sessions

```sh
python -m opencaliper.converterscripts examples/1.h5 scope.mat
python -m opencaliper.converterscripts examples/SCD_gen.s4p network.mat
```

Native MAT preserves complex samples, `domain='sparameter'` and per-channel
`reference_impedance` in ohms. Time-only formats reject network channels.
Touchstone and HDF5 export are not implemented. Workspaces embed complex sources
and retain representation, references, aliases, colors, visibility and cursors.
Older OpenCaliper versions may not recognize the new analysis kind.

Local device recordings are ignored by Git and excluded from source packages.
Synthetic converter, GUI and executable self-tests cover these formats without
requiring those files. New executable builds collect the adapters automatically.

## Format references

- [Keysight HDF5 schema](https://helpfiles.keysight.com/csg/d9300a/Help/Infiniium-UG/Content/Topics/Files/HDF5_Schema.htm)
- [Keysight programming guide, H5 and H5INt scaling](https://www.keysight.com/us/en/assets/9018-07141/programming-guides/9018-07141.pdf)
- [IBIS Touchstone 2.0 specification](https://www.ibis.org/touchstone_ver2.0/touchstone_ver2_0.pdf)
