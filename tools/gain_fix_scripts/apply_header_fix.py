#!/usr/bin/env python3
"""
Adds the two new private members needed by the gain-stage fix to
soapy_source_c.h. Anchored on the unique '_overflow_count' line (the
last member before the closing brace of the class), so it doesn't
depend on exact blank-line/indentation elsewhere in the file.

Usage:
    python3 apply_header_fix.py ~/gr-osmosdr_n6rfm/lib/soapy/soapy_source_c.h
"""
import sys, shutil, pathlib, re

ANCHOR = re.compile(
    r'(unsigned long long _overflow_count = 0;\n)'
)

ADDITION = (
    '    bool _warned_multi_stage = false;\n'
    '    std::string stage_for_slot( const std::string & slot, size_t chan );\n'
)


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path-to-soapy_source_c.h>")
        sys.exit(1)

    path = pathlib.Path(sys.argv[1])
    text = path.read_text()

    matches = ANCHOR.findall(text)
    if len(matches) != 1:
        print(f"ERROR: found {len(matches)} match(es) for the "
              "'_overflow_count' anchor line (expected exactly 1). "
              "No changes made.")
        sys.exit(2)

    if '_warned_multi_stage' in text:
        print("ERROR: '_warned_multi_stage' already present in this file "
              "-- looks like it's already patched. No changes made.")
        sys.exit(3)

    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    print(f"Backed up original to: {backup}")

    text = ANCHOR.sub(lambda m: m.group(1) + ADDITION, text, count=1)
    path.write_text(text)
    print(f"Patched: {path}")


if __name__ == "__main__":
    main()
