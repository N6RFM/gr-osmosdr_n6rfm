gr-osmosdr - generic gnuradio SDR I/O block
===========================================

**This fork adds several improvements to the soapy backend, and robustness
fixes to the SpyServer client**

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

Separately, and independent of the soapy driver fork above, the
**SpyServer client** (`lib/spyserver/`) has bug fixes for silent hangs
when the server goes away, a header-parsing bug, a spinning receive
thread, and a GUI crash in `osmocom_fft`. See
[SpyServer Source](#spyserver-source) below and
[CHANGES.md](CHANGES.md).

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

## SpyServer Source

The `osmocom Source` block can pull IQ from a remote
[Airspy SpyServer](https://airspy.com) (Airspy R0/R2/Mini, Airspy HF+,
RTL-SDR). SpyServer decimates on the server, so the stream you receive
can be much narrower than the device's full bandwidth. The client code
is in `lib/spyserver/`; it was written by Lucas Teske (racerxdl) and
this fork fixes several bugs in it (see [CHANGES.md](CHANGES.md)).

### Device arguments

```
spyserver=0,ip=10.10.10.3,port=5555
```

| Term | What it actually is | Where it's handled |
|---|---|---|
| `spyserver=0` | gr-osmosdr's routing switch -- only the *key's presence* matters (`dict.count("spyserver")`), exactly like `soapy=0`. The value is **not** used as the address. | `lib/source_impl.cc` |
| `ip=10.10.10.3` | Server address (`host=` is accepted as an alias). **Required.** Host names are resolved, IPv4 only. | `lib/spyserver/spyserver_source_c.cc` |
| `port=5555` | Server TCP port. Optional, defaults to 5555. | `lib/spyserver/spyserver_source_c.cc` |

Things that do **not** work:

- `spyserver=10.10.10.3:5555` (a `host:port` form) -- fails with
  `You should defined an IP to connect.` because the block only reads
  `ip=` / `host=`.
- Building without libairspy: in `lib/source_impl.cc` the `spyserver`
  case sits inside `#ifdef ENABLE_AIRSPY`, so the block is only
  instantiated when libairspy was found at build time, even though
  the `spyserver` type is listed as built in. Install
  `libairspy-dev` before running `cmake`.

A successful connection prints, on stderr:

```
SpyServer(10.10.10.3, 5555)
SpyServer: Trying to connect
SpyServer: Connected
SpyServer: Got sync Info
SpyServer: Maximum Sample Rate: 2500000
SpyServer: Ready
```

### Sample rates

The block offers the server's device sample rate divided by 2^n (from
the server's minimum IQ decimation up to its decimation stage count).
With `device_sample_rate = 2500000` in `spyserver.config` that is
2.5 MS/s, 1.25 MS/s, 625 kS/s, 312.5 kS/s, 156.25 kS/s, 78.125 kS/s,
and so on down to the server's limit.

`set_sample_rate()` must match one of these (within 1 Hz). Anything else
prints `Sample rate not supported` followed by the list of valid rates
and throws `Unsupported samplerate`. The device rate itself is set on the
**server** (`device_sample_rate`, 2500000 or 10000000 for an Airspy
R0/R2), not from GNU Radio.

### Sample format and bandwidth

The client always requests **signed 16-bit IQ** (hard-coded in
`on_connect()`) and converts it to complex float by dividing by 32768,
so network use is a fixed `sample rate x 4` bytes per second:

| Sample rate | Network rate |
|---|---|
| 2.5 MS/s | 10 MB/s (80 Mbit/s) |
| 10 MS/s | 40 MB/s (320 Mbit/s) |

The protocol also defines unsigned 8-bit, 24-bit, 32-bit float and 4-bit
formats. This block handles 8-bit, 16-bit and float messages; 24-bit
and 4-bit messages are silently ignored, and the block never requests
any format other than 16-bit.

### Server settings that affect this block

- **`maximum_clients`** -- the stock config allows one client. Close other
  clients (SDR++, SDR#, `ss_client`) before connecting from GNU Radio.
- **`bind_port = 5555-6666`** -- a *range*. If 5555 is already in use
  (for example by a second copy of `spyserver` that was left running),
  the server silently takes the next free port and says so only on its
  console (`Listening for connections on 0.0.0.0:5556`). Connect to the
  port it reports.
- **`force_8bit = 1`** -- forces the server to 8-bit IQ. The server
  reports this in the device info's `ForcedIQFormat` field, which the
  block receives but never checks, so the block's 16-bit request is not
  guaranteed to be honoured. The 8-bit path was broken before this
  fork's fix, and 8-bit costs dynamic range, so leave it off for
  anything you plan to decode.
- **`allow_control = 1`** -- needed for `set_gain()` to do anything. When
  it is 0 the block prints
  `Spyserver: The server does not allow you to change the gains.`
- **`frequency_correction_ppb`** -- `set_freq_corr()` in this block is a
  no-op, so apply any frequency correction on the server with this
  setting.

### Diagnostics

All messages go to stderr:

| Message | Meaning |
|---|---|
| `O` | The block's internal buffer (5,000,000 samples; 2 s at 2.5 MS/s) was full and samples were dropped. GNU Radio is not consuming fast enough. |
| `SpyServer: Lost N frames from SpyServer!` | A gap in the server's message sequence numbers: the server or network dropped data. |
| `SpyServer: Error on ThreadLoop: ...` | The receive thread died (for example the server closed the connection). |
| `SpyServer: stream ended (connection lost or stopped)` | `work()` returned after the connection was lost or streaming stopped (see CHANGES.md). Before this fork the flowgraph hung silently here. |

`get_overflow_count()` and the `rx_overflow` stream tags described above
belong to the **soapy** backend only; they do not report anything for
SpyServer.

### Not implemented

- FFT stream (`process_uint8_fft()` is a TODO).
- `set_bandwidth()` -- returns the current sample rate; the bandwidth
  is set by choosing a sample rate.
- `set_freq_corr()`, bias tee (`set_biast()`) and antenna selection --
  accepted but do nothing. For the first two, use
  `frequency_correction_ppb` and `enable_bias_tee` in the server's
  `spyserver.config`.

### Quick test without a flowgraph

```python
import osmosdr
src = osmosdr.source(args="spyserver=0,ip=10.10.10.3,port=5555")
src.set_sample_rate(2.5e6)
src.set_center_freq(100e6)
```

or `osmocom_fft -a "spyserver=0,ip=10.10.10.3,port=5555" -s 2500000`
(which crashed with a divide-by-zero before this fork's fix).

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

Values below are keyed by RF Gain (what you actually type in GRC) rather than the raw array index -- the reversal from above is already applied:

<table>
<tr>
<td valign="top">

<table>
<tr><th colspan="4">Linearity</th></tr>
<tr><th>RF Gain</th><th>VGA</th><th>MIX</th><th>LNA</th></tr>
<tr><td>0</td><td>4</td><td>0</td><td>0</td></tr>
<tr><td>1</td><td>5</td><td>0</td><td>0</td></tr>
<tr><td>2</td><td>6</td><td>1</td><td>0</td></tr>
<tr><td>3</td><td>7</td><td>1</td><td>0</td></tr>
<tr><td>4</td><td>8</td><td>1</td><td>0</td></tr>
<tr><td>5</td><td>9</td><td>1</td><td>0</td></tr>
<tr><td>6</td><td>10</td><td>2</td><td>0</td></tr>
<tr><td>7</td><td>10</td><td>2</td><td>1</td></tr>
<tr><td>8</td><td>10</td><td>0</td><td>3</td></tr>
<tr><td>9</td><td>10</td><td>0</td><td>5</td></tr>
<tr><td>10</td><td>10</td><td>1</td><td>6</td></tr>
<tr><td>11</td><td>10</td><td>0</td><td>8</td></tr>
<tr><td>12</td><td>10</td><td>0</td><td>9</td></tr>
<tr><td>13</td><td>10</td><td>5</td><td>8</td></tr>
<tr><td>14</td><td>10</td><td>6</td><td>9</td></tr>
<tr><td>15</td><td>11</td><td>6</td><td>9</td></tr>
<tr><td>16</td><td>11</td><td>7</td><td>10</td></tr>
<tr><td>17</td><td>11</td><td>8</td><td>12</td></tr>
<tr><td>18</td><td>11</td><td>9</td><td>13</td></tr>
<tr><td>19</td><td>11</td><td>11</td><td>14</td></tr>
<tr><td>20</td><td>12</td><td>12</td><td>14</td></tr>
<tr><td>21</td><td>13</td><td>12</td><td>14</td></tr>
</table>

</td>
<td valign="top">

<table>
<tr><th colspan="4">Sensitivity</th></tr>
<tr><th>RF Gain</th><th>VGA</th><th>MIX</th><th>LNA</th></tr>
<tr><td>0</td><td>4</td><td>0</td><td>0</td></tr>
<tr><td>1</td><td>4</td><td>0</td><td>1</td></tr>
<tr><td>2</td><td>4</td><td>0</td><td>2</td></tr>
<tr><td>3</td><td>4</td><td>0</td><td>3</td></tr>
<tr><td>4</td><td>4</td><td>1</td><td>5</td></tr>
<tr><td>5</td><td>4</td><td>2</td><td>6</td></tr>
<tr><td>6</td><td>4</td><td>2</td><td>7</td></tr>
<tr><td>7</td><td>4</td><td>3</td><td>8</td></tr>
<tr><td>8</td><td>4</td><td>4</td><td>9</td></tr>
<tr><td>9</td><td>5</td><td>4</td><td>9</td></tr>
<tr><td>10</td><td>5</td><td>4</td><td>12</td></tr>
<tr><td>11</td><td>5</td><td>7</td><td>12</td></tr>
<tr><td>12</td><td>5</td><td>8</td><td>13</td></tr>
<tr><td>13</td><td>5</td><td>9</td><td>14</td></tr>
<tr><td>14</td><td>6</td><td>9</td><td>14</td></tr>
<tr><td>15</td><td>7</td><td>10</td><td>14</td></tr>
<tr><td>16</td><td>8</td><td>10</td><td>14</td></tr>
<tr><td>17</td><td>9</td><td>11</td><td>14</td></tr>
<tr><td>18</td><td>10</td><td>12</td><td>14</td></tr>
<tr><td>19</td><td>11</td><td>12</td><td>14</td></tr>
<tr><td>20</td><td>12</td><td>12</td><td>14</td></tr>
<tr><td>21</td><td>13</td><td>12</td><td>14</td></tr>
</table>

</td>
</tr>
</table>
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

    git clone https://github.com/N6RFM/gr-osmosdr_n6rfm.git
    cd gr-osmosdr_n6rfm/
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
at <https://github.com/N6RFM/gr-osmosdr_n6rfm/issues>.

Authors
-------
See [AUTHORS](AUTHORS) for the full list. This fork's changes --
including the soapy-backend gain-stage fixes and documentation in this
README -- were made by N6RFM, pair-programmed with Claude (Anthropic).
