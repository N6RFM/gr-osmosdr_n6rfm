# Changes in this fork (N6RFM/gr-osmosdr_n6rfm)

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

## Added: `rx_overflow` tag emission in the soapy backend

`soapy_source_c::work()` already detected `SOAPY_SDR_OVERFLOW` (see
the generic settings passthrough above, which exposes
`overflow_count`) but had no way to mark *where in the sample stream*
a drop happened -- only a running total, readable after the fact.

Now, on every `SOAPY_SDR_OVERFLOW`, `work()` calls `add_item_tag()`
with key `rx_overflow` at the exact sample offset where the gap
occurs (`nitems_written(0)`, correct specifically because this
`work()` call produces zero samples). Any ordinary downstream block
can now detect drops in real time just by reading tags on its own
input port, mid-flowgraph -- no polling, no reference to this source
block needed.

This is what [gr-overflow-monitor](https://github.com/N6RFM/gr-overflow-monitor)'s
`Overflow Tag Monitor` block reads. It only has anything to detect
because [SoapyAirspy_n6rfm](https://github.com/N6RFM/SoapyAirspy_n6rfm)
correctly signals `SOAPY_SDR_OVERFLOW` from `readStream()` in the
first place (see that repo's `CHANGES.md`, "Added: SOAPY_SDR_OVERFLOW
signaling") -- this tag emission has nothing to detect against a
driver that silently drops samples without reporting it.

Files changed: `lib/soapy/soapy_source_c.cc`

## Fixed: SpyServer client (`lib/spyserver/`)

Found by reading the code while chasing stutter on an Airspy R2 streamed
from SpyServer v2.0.1921 running on an Orange Pi Zero 3. The client is
Lucas Teske's (racerxdl) and is otherwise unchanged. Device strings,
sample rates and the wire protocol behave as before; see "SpyServer
Source" in the README for the user-facing description.

**Silent hang when the server goes away.** `thread_loop()` polled the
socket with `FIONREAD` and only called `recv()` when bytes were
waiting. After the server closed the connection `FIONREAD` just kept
returning 0, and an `ioctl` failure (return value -1) matched none of
the errno constants the `switch` in `available_data()` tests for, so a
dead connection was never noticed. `work()` then sat in
`_samp_avail.wait()` with nothing left to notify it, and the flowgraph
froze with no message.

Fix: new `tcp_client::peer_closed()` (a `recv(MSG_PEEK | MSG_DONTWAIT)`
probe; POSIX only, returns `false` on Windows, i.e. the old behaviour)
is checked whenever no data is waiting. `cleanup()` now sets
`streaming`/`terminated` under `_fifo_lock` and calls `notify_all()`, and
`work()` returns `WORK_DONE` (printing `SpyServer: stream ended
(connection lost or stopped)`) when `terminated || !streaming`.

**Receive thread spun at 100% of a core.** With no data waiting,
`thread_loop()` looped immediately. It now sleeps 200 us (about 2 KB of
a 10 MB/s stream, far below the kernel socket buffer).

**Message header parsed at the wrong offset.** `parse_header()` used
`memcpy(&header + parser_position, ...)`. `header` is a 20-byte
`MessageHeader`, so that pointer arithmetic advances in 20-byte steps,
and a header split across two TCP reads was written outside the struct
(into neighbouring members). Now `(uint8_t *)&header + parser_position`.
Whether a split happens depends on where the server's TCP segment
boundaries fall relative to message starts, so it can be rare, but when
it happens it corrupts state.

**8-bit IQ path.** `process_uint8_samples()` had three bugs: it copied
`num_samples / 2` samples instead of `num_samples`, it printed `O` on
every message as a result, and `*sample - 128.f / 128.f` evaluates as
`sample - 1.0` (operator precedence) instead of `(sample - 128) / 128`.
Only reachable when the server forces 8-bit (`force_8bit = 1`), because
the client itself always requests 16-bit.

**Body buffer reallocated every message.** `body_buffer_length` was
never updated, so the `body_buffer_length < header.BodySize` test was
always true.

**`osmocom_fft` crash.** `get_bandwidth_range()` returned a single-value
range (zero width), which made the qtgui `Range` used for the bandwidth
slider divide by zero (`ZeroDivisionError` in `find_nsteps()`). It now
returns 0..current sample rate (or the device's maximum rate before one
is set). `set_bandwidth()` is still a no-op.

**Sample-rate list.** Rates were computed with integer division
(`2500000 / 64` gave 39062, not 39062.5) and matched with exact floating
point equality. They are now computed in `double` and matched within
1 Hz; `_sample_rate` stores the list's value.

**Known limitations, not changed here:**

- The format request is hard-coded to 16-bit (`on_connect()`). (The
  device info's `ForcedIQFormat` field was not checked when this section
  was written; it is now, see the overflow-counter section below.)
- 24-bit IQ and 4-bit FFT messages are silently ignored; the FFT stream
  is a TODO.
- `set_freq_corr()`, `set_biast()` and `set_bandwidth()` do nothing.
- (Since fixed, see the overflow-counter section below: the `ENABLE_AIRSPY`
  guard around the `spyserver` case in `lib/source_impl.cc`, and the missing
  newline after `SpyServer: Lost N frames from SpyServer!`.)
- On Windows `peer_closed()` always returns `false`, so a lost
  connection is still not detected there.

**Status:** the `tcp_client.cc` changes pass `g++ -std=c++17
-fsyntax-only`; the full library was then built against GNU Radio
3.10.9 and tested against SpyServer v2.0.1921 with an Airspy R2 at
2.5 MS/s over gigabit Ethernet.

- Throughput: a 420 s run delivered 2.48 to 2.55 MS/s every second, 0 low
  seconds, no `O` or `Lost` messages (the pre-fix baseline was 25,000,000
  samples in 11.0 s, also clean, so no regression).
- Disconnect: with a flowgraph of `osmosdr.source` into a null sink,
  stopping the server mid-stream printed `SpyServer: Error on ThreadLoop:
  Server closed the connection` and `SpyServer: stream ended (connection
  lost or stopped)`, and `top_block.wait()` returned by itself 7.6 s after
  the run began (a few seconds after the server was stopped). Before the
  fix the flowgraph hung silently.
- `osmocom_fft` opens its spectrum window.

Not yet run against SpyServer v2.0.1922 (the server was upgraded
afterwards; a separate client, not this library, was used to check that
it streams, reports the same device info and still changes level with
gain).

Not yet exercised: the 8-bit path (needs `force_8bit = 1` on the server)
and the split-header case (depends on TCP segment boundaries).

Files changed: `lib/spyserver/spyserver_source_c.cc`,
`lib/spyserver/tcp_client.cc`, `lib/spyserver/tcp_client.h`

## SpyServer: overflow counter and tags, gain range and logging, ForcedIQFormat warning, build guard

- **`get_overflow_count()` and `rx_overflow` tags for SpyServer.** The receive
  thread records the stream position of every FIFO overflow and every
  sequence-number gap; `work()` stamps them into the stream as `rx_overflow`
  tags (same key/value as the soapy backend). The count is the number of
  events, not samples.
  Events at the same stream position (a full FIFO dropping message after message)
  are counted individually but tagged once; a gap at the very end of the stream is
  only tagged if more samples follow.
  Tested against a mock SpyServer (sequence gap: 1 event, tag at the exact sample
  index; FIFO overflow: 678 events, 1 tag); not yet against a real SpyServer.
- **`get_gain_range()`** now reports the server's `MaximumGainIndex` (21 for an
  Airspy R2) once known, instead of a fixed 0-16 (falls back to 16 before the
  device info arrives). `set_gain()` was never clamped to the reported range.
- **Gain log.** `SpyServer: gain requested N` when `set_gain()` sends a
  command; `SpyServer: server gain at connect: N` from the first client-sync
  (and `server now reports gain N` if a later sync changes it). Tested against a
  real SpyServer v2.0.1921: it sent no sync after a gain command and did not
  answer a CMD_GET_SETTING probe, so the applied gain cannot be read back from
  that server; verify it from the data level.
- **`ForcedIQFormat` warning** at connect when the server forces a format.
- **Device info log.** Three `SpyServer: device info ...` lines at connect (printed only when
  `SPYSERVER_VERBOSE` is set): type, serial,
  protocol version, max sample rate/bandwidth, decimation stages, gain stages, max gain
  index, resolution, frequency range and forced IQ format, as sent by the server.
- **Quiet by default.** `Got sync Info`, `Maximum Sample Rate` and the device info lines are
  printed only when the environment variable `SPYSERVER_VERBOSE` is set. Connect, gain, sample
  rate, streaming and error messages are unchanged.
- **Build guard.** The `spyserver` case in `source_impl.cc` was inside
  `#ifdef ENABLE_AIRSPY`; it is now under `ENABLE_SPYSERVER`.
- `SpyServer: Lost N frames` now ends with a newline, and `dropped_buffers` is
  only incremented for real gaps (a negative gap, e.g. a repeated sequence
  number, no longer decrements it).
- **Not changed:** digital gain (`((uint32_t)gain) * 0xFFFFFFFF`). The protocol
  header does not document the parameter, so it was left alone.

Files changed: `lib/spyserver/spyserver_source_c.cc`, `lib/spyserver/spyserver_source_c.h`,
`lib/source_impl.cc`, `README.md`, `CHANGES.md`
