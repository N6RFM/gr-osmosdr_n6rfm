"""
print_gain_settings.py

Paste the body of this file (everything below the docstring) into a
GNU Radio Companion "Snippet" block, with Location set to "after init".

Prints the osmocom Source's ACTUAL live gain state to the GNU Radio
console at flowgraph startup -- the Gain Table mode currently active,
every named gain stage the device reports (adapts automatically:
three stages in `manual` mode, one in `linearity`/`sensitivity`), and
the legacy overall-gain readback.

Useful because RF/IF/BB Gain mean different things depending on Gain
Table mode (see README.md, "Gain Settings") -- this prints what's
actually configured on the device rather than what the GRC fields
imply.

Usage:
    1. In gnuradio-companion, add a "Snippet" block to your flowgraph.
    2. Set Location: after init
    3. Paste the code below (not this docstring) into the code box.
    4. Replace `osmosdr_source_1` with your block's actual variable
       name if different -- check with:
         grep -n "osmosdr.source" your_flowgraph.py

Sample output, Sensitivity mode, RF Gain = 21:
    --- Gain settings ---
    Gain Table: 'sensitivity'
    SENS Gain: 21 dB
    Overall Gain (legacy path): 0 dB

Sample output, Manual mode, RF/IF/BB = 15/15/15:
    --- Gain settings ---
    Gain Table: 'manual'
    LNA Gain: 15 dB
    MIX Gain: 15 dB
    VGA Gain: 15 dB
    Overall Gain (legacy path): 0 dB

Notes:
  - get_gain_names(0) queries the device directly, so this loop
    adapts automatically to however many stages the current Gain
    Table mode exposes -- no hardcoded stage names.
  - get_setting("gains") is specific to the soapy backend. The
    try/except keeps this safe to leave in a flowgraph even after
    switching to a non-soapy device string (rtl=, hackrf=, etc.),
    where that call would otherwise raise.
  - "Overall Gain (legacy path)" reads through the generic (unnamed)
    get_gain() call -- a separate internal code path from the named
    per-stage gains above. It won't generally match their sum; it's
    included for completeness, not as a cross-check.
"""

print("--- Gain settings ---")
try:
    mode = self.osmosdr_source_1.get_setting("gains")
    print(f"Gain Table: {mode!r}")
except Exception as e:
    print(f"(Gain Table setting not available: {e})")

for name in self.osmosdr_source_1.get_gain_names(0):
    print(f"{name} Gain: {self.osmosdr_source_1.get_gain(name, 0)} dB")
print(f"Overall Gain (legacy path): {self.osmosdr_source_1.get_gain(0)} dB")
