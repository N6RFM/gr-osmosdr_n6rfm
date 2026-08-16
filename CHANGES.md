# Changes in this fork (N6RFM/gr-osmosdr_racerdxl)

Base: [racerxdl/gr-osmosdr](https://github.com/racerxdl/gr-osmosdr), synced with upstream.

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
