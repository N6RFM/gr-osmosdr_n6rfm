#!/usr/bin/env python3
"""
Round 3: set_bb_gain() needs the same empty-name guard set_if_gain()
already has -- otherwise it calls set_gain(gain, '', chan) whenever
stage_for_slot('BB', ...) returns empty (single-stage mode), sending
an empty gain name to the device instead of doing a clean no-op.

Usage:
    python3 bb_empty_check.py ~/gr-osmosdr_n6rfm/lib/soapy/soapy_source_c.cc
"""
import sys, shutil, pathlib, re

OLD = re.compile(
    r'double soapy_source_c::set_bb_gain\( double gain, size_t chan \)\s*'
    r'\{\s*'
    r'const std::string name = this->stage_for_slot\( "BB", chan \);\s*'
    r'return this->set_gain\( gain, name, chan \);\s*'
    r'\}'
)

NEW = '''double soapy_source_c::set_bb_gain( double gain, size_t chan )
{
    const std::string name = this->stage_for_slot( "BB", chan );
    if ( name.empty() )
        return this->get_gain( chan ); // honest no-op, not a silent duplicate write
    return this->set_gain( gain, name, chan );
}'''

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path-to-soapy_source_c.cc>")
        sys.exit(1)
    path = pathlib.Path(sys.argv[1])
    text = path.read_text()
    matches = OLD.findall(text)
    if len(matches) != 1:
        print(f"ERROR: found {len(matches)} match(es) for set_bb_gain() "
              "(expected exactly 1). No changes made.")
        sys.exit(2)
    backup = path.with_suffix(path.suffix + '.bak3')
    shutil.copy2(path, backup)
    print(f"Backed up original to: {backup}")
    text = OLD.sub(NEW, text, count=1)
    path.write_text(text)
    print(f"Patched: {path}")

if __name__ == "__main__":
    main()
