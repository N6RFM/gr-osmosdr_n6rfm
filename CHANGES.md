# Changes in this fork (N6RFM/gr-osmocom_n6rfm)

Base: [racerxdl/gr-osmosdr](https://github.com/racerxdl/gr-osmosdr), synced with upstream.

## Build: C++17 required (was C++11)

Modern GNU Radio (3.10+) headers require `std::string_view`, a C++17
feature -- the build fails against them under the old C++11 setting.
Bumped `ADD_DEFINITIONS(-std=c++11)` to `-std=c++17` in the top-level
`CMakeLists.txt`.

## Added: bias tee support for the soapy backend (`soapy_source_c`)

`set_biast()`/`get_biast()` were already plumbed all the way through
the shared interface (`source_iface` -> `source_impl` ->
`osmosdr::source`), with a working implementation for the native
`airspy_source_c` backend (device strings starting `airspy=`). The
`soapy_source_c` backend (device strings using `soapy=`, e.g.
`driver=airspy,serial=...,soapy=0`) had no override at all, so it
silently fell through to `source_iface`'s default stub -- which prints
`NOT IMPLEMENTED BIAST(...)` and does nothing to the hardware.

This matters specifically for
[N6RFM/SoapyAirspy](https://github.com/N6RFM/SoapyAirspy) (a fork of
SoapyAirspy with its own bias-tee fixes) -- any device string using
`soapy=0,driver=airspy,...` routes through the soapy backend here, so
without this fix, calling `set_biast()` on such a device would have no
effect regardless of how correctly the underlying SoapySDR driver
handles it.

**Fix:** `soapy_source_c::set_biast()`/`get_biast()` now forward to
`SoapySDR::Device::writeSetting("biastee", ...)` /
`readSetting("biastee")` -- the same generic settings mechanism
SoapyAirspy (and other SoapySDR drivers that support a `biastee`
setting) already expose.

**Scope / what this does *not* do:** this is not yet exposed as a GRC
block checkbox -- only reachable by calling `set_biast()`/`get_biast()`
directly from Python or C++ against the block object. The existing
approach of setting `biastee=true|false` in the Device Arguments
string at construction time (documented in SoapyAirspy's own README)
remains the simplest way to control it from GRC alone.

Files changed: `lib/soapy/soapy_source_c.cc`, `lib/soapy/soapy_source_c.h`

## Example

```python
import osmosdr
src = osmosdr.source("driver=airspy,serial=744c60c8218e3e4f,soapy=0")
src.set_biast(True)
print(src.get_biast())  # True
```

## Added: generic settings passthrough, overflow counter, GRC usability

- `set_setting(key, value)` / `get_setting(key)` -- generic passthrough
  to `SoapySDR::Device::writeSetting()`/`readSetting()`, implemented
  for the soapy backend. Lets you reach any driver-specific setting
  (e.g. SoapyAirspy's `bufsize`, `overflow_count`, `high_watermark`,
  `bitpack`) from Python without a dedicated wrapper method needing to
  exist for each one. Declared on `source_iface` with a safe
  do-nothing/empty-string default, following the same pattern already
  established for `set_biast`/`get_biast` -- other backends are
  unaffected.

- `get_overflow_count()` -- counts `SOAPY_SDR_OVERFLOW` events seen by
  `soapy_source_c::work()`. Previously these were silently retried
  once and discarded with zero visibility; now at least countable from
  Python.

- **GRC block usability** (`osmocom Source` block only): added a
  **Bias Tee** checkbox (wired to `set_biast()`, live-toggleable
  without restarting the flowgraph) and a **Gain Table (Soapy)**
  dropdown (`manual`/`linearity`/`sensitivity`, wired to
  `set_setting("gains", ...)`, applied at construction only -- not
  live-toggled, since gain elements themselves change between modes
  and could leave stale values applied). Both replace what previously
  required hand-typing into the Device Arguments string from memory.

- Fixed stale documentation claiming automatic gain mode is
  RTL-SDR-only -- it isn't, for any backend whose driver implements
  `SoapySDR::Device::setGainMode()` (confirmed working for Airspy via
  SoapyAirspy).

Files changed: `lib/source_iface.h`, `lib/source_impl.cc`,
`lib/source_impl.h`, `include/osmosdr/source.h`,
`python/bindings/source_python.cc`, `lib/soapy/soapy_source_c.cc`,
`lib/soapy/soapy_source_c.h`, `grc/gen_osmosdr_blocks.py`

## Fixed: Gain Table dropdown crashed with NameError

The **Gain Table (Soapy)** GRC parameter above was declared with
`dtype: enum`, which GRC inserts into generated code as a raw,
unquoted fragment (the mechanism enum options use to represent
arbitrary code, e.g. `True`/`False`). Selecting anything other than
the blank default generated an invalid line like:

```python
self.osmosdr_source_0.set_setting("gains", sensitivity)
```

-- a bare, undefined name, raising `NameError: name 'sensitivity' is
not defined` at flowgraph startup.

Fixed by changing `dtype` from `enum` to `string`, matching the
pattern the file already uses for the working "Clock Source" dropdown
-- `dtype: string` parameters are auto-quoted by GRC's codegen.
Verified with `grcc` (GRC's headless compiler): compiled a real
flowgraph with `gain_table: sensitivity` before and after the fix,
confirming the generated line changed from the bare `sensitivity` to
the correctly quoted `'sensitivity'`, and that the resulting script
runs past that line without error.

Files changed: `grc/gen_osmosdr_blocks.py`
