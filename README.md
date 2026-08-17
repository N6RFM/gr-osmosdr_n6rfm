gr-osmosdr - generic gnuradio SDR I/O block
===========================================

**This fork adds several improvements to the soapy backend**
(device strings using `soapy=`, e.g. `driver=airspy,serial=...,soapy=0`),
originally motivated by getting bias tee working reliably with
[N6RFM/SoapyAirspy_n6rfm](https://github.com/N6RFM/SoapyAirspy_n6rfm) --
most of what's below only does anything useful paired with that
driver fork specifically (stock SoapyAirspy doesn't report
`SOAPY_SDR_OVERFLOW`, so `get_overflow_count()`/`rx_overflow` tags
here have nothing to detect; stock `gains=linearity/sensitivity`
doesn't even exist upstream -- see that repo's own `CHANGES.md`):

- **Bias tee actually works.** `set_biast()`/`get_biast()` were
  previously a silent no-op for this backend -- calling them printed
  a debug message and did nothing to the hardware.
- **Generic `set_setting()`/`get_setting()`** -- reach any
  driver-specific SoapySDR setting from Python (e.g. SoapyAirspy's
  `gains`, `bufsize`, `overflow_count`, `high_watermark`) without a
  dedicated wrapper method needing to exist for each one.
- **`get_overflow_count()`** -- overflow events were previously
  silently discarded with zero visibility; now countable.
- **`rx_overflow` stream tags** -- every `SOAPY_SDR_OVERFLOW` is now
  also stamped directly into the sample stream at the exact offset it
  occurred, so any ordinary downstream block can detect drops live
  just by reading its own input tags -- no polling, no cross-block
  reference needed. Read by
  [gr-overflow-monitor](https://github.com/N6RFM/gr-overflow-monitor)'s
  `Overflow Tag Monitor` block.
- **GRC block usability**: a live-toggleable **Bias Tee** checkbox and
  a **Gain Table (Soapy)** dropdown (`manual`/`linearity`/`sensitivity`)
  on the `osmocom Source` block, replacing hand-typed Device Arguments
  syntax.
- **C++17** required (was C++11), for compatibility with modern
  GNU Radio (3.10+) / Boost.
- Fixed stale documentation claiming automatic gain mode is
  RTL-SDR-only.

Full details, file-by-file, in [CHANGES.md](CHANGES.md). Base:
[racerxdl/gr-osmosdr](https://github.com/racerxdl/gr-osmosdr) (Lucas
Teske), which itself added SpyServer support on top of upstream
osmocom/gr-osmosdr.

## Device Arguments Explained

A working example for an Airspy through the soapy backend:

```
driver=airspy,serial=744c60c8218e3e4f,soapy=0
```

Three pieces, three genuinely separate layers -- worth knowing which
is which, since no single tool documents all of them together:

| Term | What it actually is | Where it's handled |
|---|---|---|
| `driver=airspy` | SoapySDR's own universal driver-selection key | SoapySDR core's registry matching |
| `serial=744c60c8218e3e4f` | SoapyAirspy-specific construction arg | SoapyAirspy's constructor directly (see [SoapyAirspy_n6rfm](https://github.com/N6RFM/SoapyAirspy_n6rfm#using)) |
| `soapy=0` | gr-osmosdr's own routing switch -- only the *key's presence* matters, the value is ignored | **This repo**, `lib/source_impl.cc` |

- **`driver=airspy`** and **`serial=744c60c8218e3e4f`** -- construction
  arguments consumed by SoapySDR/SoapyAirspy itself, before this
  block or gr-osmosdr are involved at all. `serial=` matters
  specifically if you have more than one Airspy connected -- without
  it, SoapySDR silently opens whichever matching device enumerates
  first, not necessarily the one you meant. Full explanation
  (including why `serial=744c60c8218e3e4f` and
  `serial=0x744c60c8218e3e4f` are equivalent) in
  [SoapyAirspy_n6rfm's README](https://github.com/N6RFM/SoapyAirspy_n6rfm#using).

- **`soapy=0`** -- this one's entirely ours (this repo), and has
  nothing to do with SoapySDR at all. It's a routing switch: `lib/source_impl.cc`
  just checks `dict.count("soapy")` -- the value (`0` here) is
  irrelevant, only whether the *key* is present. Its presence tells
  this block to use the generic SoapySDR backend (`soapy_source_c`)
  instead of one of the other native backends (`rtl=`, `hackrf=`,
  the native `airspy=`, etc). Once that routing decision is made, the
  whole string -- `soapy=0` included -- gets forwarded to
  `SoapySDR::Device::make()`, which just ignores the `soapy` key
  since it doesn't recognize it.

  **The `0` is not universal and not a device selector.** You'll see
  `soapy=1`, `soapy=2`, etc. in device strings this project
  auto-generates when it enumerates multiple available devices for a
  picker/dropdown (`get_devices()` in `soapy_source_c.cc` assigns
  sequential indices purely for that listing). When you're hand-typing
  your own device string, any value works identically -- `serial=` is
  what actually picks the physical unit, not this number.

While originally being developed for the
[OsmoSDR](https://osmocom.org/projects/osmosdr/wiki) hardware, this
block has become a generic SDR I/O block for a variety of SDR
hardware, including:

 * FUNcube Dongle / Pro+ through [gr-funcube](https://github.com/dl1ksv/gr-funcube)
 * RTL2832U based DVB-T dongles through [librtlsdr](https://osmocom.org/projects/rtl-sdr/wiki)
 * RTL-TCP spectrum server (see librtlsdr project)
 * MSi2500 based DVB-T dongles through [libmirisdr](https://gitea.osmocom.org/sdr/libmirisdr)
 * SDRplay RSP through SDRplay API library
 * gnuradio .cfile input through libgnuradio-blocks
 * RFSPACE SDR-IQ, SDR-IP, NetSDR (incl. X2 option), Cloud-IQ, and CloudSDR
 * AirSpy Wideband Receiver through [libairspy](https://github.com/airspy/airspyone_host)
 * CCCamp 2015 rad1o Badge through [libhackrf](https://github.com/greatscottgadgets/hackrf)
 * Great Scott Gadgets HackRF through [libhackrf](https://github.com/greatscottgadgets/hackrf)
 * Nuand LLC bladeRF through [libbladeRF library](https://www.nuand.com/libbladeRF-doc/)
 * Ettus USRP Devices through [Ettus UHD library](https://github.com/EttusResearch/uhd)
 * Fairwaves UmTRX through [Fairwaves' module for UHD](https://github.com/fairwaves/UHD-Fairwaves)
 * Fairwaves XTRX through [libxtrx](https://github.com/myriadrf/libxtrx)
 * Red Pitaya SDR transceiver <http://bazaar.redpitaya.com>
 * FreeSRP through [libfreesrp](https://github.com/myriadrf/libfreesrp)
 * Airspy SPYServer

By using the gr-osmosdr block you can take advantage of a common software API in
your application(s) independent of the underlying radio hardware.

Homepage + Documentation
------------------------

For general osmocom/gr-osmosdr background, see
<https://osmocom.org/projects/gr-osmosdr/wiki> -- note that page
describes the upstream project, not this fork's changes (see
[CHANGES.md](CHANGES.md) for those).

Requirements: GNU Radio 3.10+ and a C++17 compiler (see
[CHANGES.md](CHANGES.md) for why C++17 is required). Built and tested
on Ubuntu 24 / Linux Mint 22 with GNU Radio 3.10.9.

Before building, make sure the dependencies for whichever devices you
actually use (see list above) are installed -- the build system
detects them automatically and enables the matching source/sink
components.

Building with cmake:

    git clone https://github.com/N6RFM/gr-osmocom_n6rfm.git
    cd gr-osmocom_n6rfm/
    mkdir build
    cd build/
    cmake ..
    make
    sudo make install
    sudo ldconfig

If you're updating an existing install, `sudo make uninstall` from an
old build directory first will cleanly remove it.

NOTE: The osmocom blocks will appear under 'Sources' and 'Sinks' categories
in GRC menu.

Issues
------

For bugs or questions specific to this fork's changes, open an issue
at <https://github.com/N6RFM/gr-osmocom_n6rfm/issues>.
