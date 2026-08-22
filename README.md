gr-osmosdr - generic gnuradio SDR I/O block
===========================================

**This fork adds several improvements to the soapy backend**

The soapy backend itself
(`soapy_source_c.cc`, the whole `soapy=` mechanism) is original
[osmocom/gr-osmosdr](https://github.com/osmocom/gr-osmosdr)
functionality, present long before this fork existed.

What's actually new here (originally motivated by getting bias tee
working reliably with
[N6RFM/SoapyAirspy_n6rfm](https://github.com/N6RFM/SoapyAirspy_n6rfm))
is below -- most of it only does anything useful paired with that
driver fork specifically: stock SoapyAirspy doesn't report
`SOAPY_SDR_OVERFLOW`, so `get_overflow_count()`/`rx_overflow` tags
here have nothing to detect, and stock `gains=linearity/sensitivity`
doesn't even exist upstream (see that repo's own `CHANGES.md`):

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

## Gain Settings

For Airspy through the soapy backend, the **Gain Table (Soapy)**
dropdown on the `osmocom Source` block (`manual` / `linearity` /
`sensitivity`) changes what the RF/IF/BB Gain fields below it actually
mean. All numbers below are hardware-confirmed via `SoapySDRUtil
--probe="driver=airspy,soapy=0,gains=<mode>"` -- not assumed.

| Gain Table | RF Gain controls | IF Gain controls | BB Gain controls | Range |
|---|---|---|---|---|
| `manual` | LNA | MIX | VGA | 0-15 dB per stage (0-45 dB total) |
| `linearity` | the whole table, in one step | *(ignored)* | *(ignored)* | 0-21 (a table step index, not dB) |
| `sensitivity` | the whole table, in one step | *(ignored)* | *(ignored)* | 0-21 (a table step index, not dB) |
| *(blank)* | whatever SoapyAirspy's internal default is | -- | -- | not recommended once tuning deliberately |

**In `manual` mode**, RF/IF/BB are three real, independent hardware
stages (LNA/MIX/VGA) -- set each one directly to whatever you want, up
to 15 dB per stage. There is no shared state between them and no
ordering to worry about.

**In `linearity`/`sensitivity` mode**, the device only exposes *one*
real gain control -- **RF Gain is the only field that does anything.**
IF Gain and BB Gain are both honest no-ops in this mode (verified:
neither produces a hardware write). Set RF Gain anywhere from `0` to
`21` and ignore the other two fields entirely.

`0-21` here is not a dB value -- it's a step index into one of
libairspy's two built-in 22-step precomputed gain tables
(`airspy_set_linearity_gain()` / `airspy_set_sensitivity_gain()` in
[SoapyAirspy_n6rfm](https://github.com/N6RFM/SoapyAirspy_n6rfm)'s
`writeSetting("gains", ...)` handling). Each step jointly sets
LNA/MIX/VGA to a vendor-tuned combination optimized for whichever
property (sensitivity vs. linearity) that table targets -- `21` is
simply the top of that table, i.e. maximum gain.

Do not compare `manual` mode numbers to `linearity`/`sensitivity`
numbers directly -- `15` in `manual` mode is a real dB value on one
stage; `15` in table mode is just a step index two-thirds of the way
up a precomputed curve. They are different units that happen to share
a text box.

### Linearity / Sensitivity Table Reference

`0-21` in `linearity`/`sensitivity` mode maps to a real, fixed
combination of LNA/MIX/VGA inside libairspy -- confirmed directly
against the vendor source
([`airspy.c`](https://github.com/airspy/airspyone_host/blob/master/libairspy/src/airspy.c)):

```c
uint8_t airspy_linearity_vga_gains[22]   = {13,12,11,11,11,11,11,10,10,10,10,10,10,10,10,10,9,8,7,6,5,4};
uint8_t airspy_linearity_mixer_gains[22] = {12,12,11,9,8,7,6,6,5,0,0,1,0,0,2,2,1,1,1,1,0,0};
uint8_t airspy_linearity_lna_gains[22]   = {14,14,14,13,12,10,9,9,8,9,8,6,5,3,1,0,0,0,0,0,0,0};

uint8_t airspy_sensitivity_vga_gains[22]   = {13,12,11,10,9,8,7,6,5,5,5,5,5,4,4,4,4,4,4,4,4,4};
uint8_t airspy_sensitivity_mixer_gains[22] = {12,12,12,12,11,10,10,9,9,8,7,4,4,4,3,2,2,1,0,0,0,0};
uint8_t airspy_sensitivity_lna_gains[22]   = {14,14,14,14,14,14,14,14,14,13,12,12,9,9,8,7,6,5,3,2,1,0};
```

The value you set on RF Gain (`0`-`21`) is not used as a direct array
index -- libairspy internally reverses it (`index = 21 - value`) before
looking up the table, so RF Gain `21` reads array position `0` (the
highest values above) and RF Gain `0` reads position `21` (the
lowest). Net effect for you: RF Gain `21` is still genuinely maximum
gain, `0` is genuinely minimum -- the reversal is just an internal
implementation detail, verified row-by-row against real hardware
output.

**Naming collision to watch for:** the vendor's own array names call
the baseband stage `vga`, but tools that dump this table sometimes
label that same column `if` -- **that `if` is not the same thing as
gr-osmocom's "IF Gain" GRC field.** GRC's IF Gain field addresses the
**MIX** stage (see the table above), not VGA. If you're ever
cross-referencing a raw gain-table dump like this against the GRC
block's fields, don't assume matching column names line up.

**What the two tables reveal about intent:** `sensitivity` raises LNA
gain early (near-max by RF Gain `~8`-`9`), prioritizing noise
figure/weak-signal sensitivity even before baseband gain is elevated.
`linearity` holds LNA low much longer (doesn't approach max until RF
Gain `~17`+), loading gain into VGA/baseband first instead --
protecting front-end linearity against strong nearby signals for as
long as possible. Choose accordingly: `sensitivity` for weak, isolated
signals; `linearity` when strong nearby transmitters risk
intermodulation.


### Verifying Gain Settings at Runtime

Because the meaning of RF/IF/BB Gain changes with the Gain Table mode
(above), it's easy to have a flowgraph running with gain values that
don't do what the GRC fields suggest -- particularly after switching
modes without re-checking. Rather than guessing, print the device's
actual, live gain state to the GNU Radio console at startup.

**In gnuradio-companion:**

1. Add a **Snippet** block to your flowgraph (search the block
   library for "Snippet").
2. Set its **Location** to `after init` -- this runs once, after the
   `osmocom Source` block is fully constructed, so `get_gain()` reads
   real values rather than defaults.
3. Paste the code from
   [`tools/gnuradio_snippets/print_gain_settings.py`](tools/gnuradio_snippets/print_gain_settings.py)
   into the Snippet's code box (everything below that file's
   docstring).

Replace `osmosdr_source_1` with your block's actual variable name if
different -- check with:
```bash
grep -n "osmosdr.source" your_flowgraph.py
```

Sample output, Sensitivity mode with RF Gain = 21:
```
--- Gain settings ---
Gain Table: 'sensitivity'
SENS Gain: 21 dB
Overall Gain (legacy path): 0 dB
```

Sample output, Manual mode with RF/IF/BB = 15/15/15:
```
--- Gain settings ---
Gain Table: 'manual'
LNA Gain: 15 dB
MIX Gain: 15 dB
VGA Gain: 15 dB
Overall Gain (legacy path): 0 dB
```

Notes:
- `get_gain_names(0)` queries the device directly, so this loop
  automatically adapts to however many stages the current Gain Table
  mode actually exposes (three in `manual`, one in
  `linearity`/`sensitivity`) -- no need to hardcode stage names.
- `get_setting("gains")` is specific to the soapy backend
  (`soapy_source_c`'s generic settings passthrough). The `try/except`
  keeps this snippet safe to leave in a flowgraph even if you later
  switch to a non-soapy device string (`rtl=`, `hackrf=`, etc.),
  where that call would otherwise raise.
- `Overall Gain (legacy path)` reads back through the generic
  (unnamed) `get_gain()` call -- this is a separate internal code path
  from the named per-stage gains above and won't generally match their
  sum; it's included for completeness, not as a sanity check.


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

Authors
-------
See [AUTHORS](AUTHORS) for the full list. This fork's changes --
including the soapy-backend gain-stage fixes and documentation in this
README -- were made by N6RFM, pair-programmed with Claude (Anthropic).
