#!/usr/bin/env python3
"""
Literal search-and-replace fix for soapy_source_c.cc.

v2: matches set_if_gain() and set_bb_gain() independently via regex,
so it's immune to whitespace/blank-line differences between them
(the v1 script required one exact contiguous block and failed on a
real file that had a blank line between the two functions).

Usage:
    python3 apply_gain_fix.py ~/gr-osmosdr_n6rfm/lib/soapy/soapy_source_c.cc
"""
import sys, shutil, pathlib, re

IF_GAIN_PATTERN = re.compile(
    r'double soapy_source_c::set_if_gain\(\s*double gain,\s*size_t chan\s*\)\s*'
    r'\{\s*'
    r'//docs specify RF gain is the first element\s*'
    r'const std::string name = this->get_gain_names\(chan\)\.front\(\);\s*'
    r'return this->set_gain\(gain, name, chan\);\s*'
    r'\}'
)

BB_GAIN_PATTERN = re.compile(
    r'double soapy_source_c::set_bb_gain\(\s*double gain,\s*size_t chan\s*\)\s*'
    r'\{\s*'
    r'//docs specify baseband gain is the last element\s*'
    r'const std::string name = this->get_gain_names\(chan\)\.back\(\);\s*'
    r'return this->set_gain\(gain, name, chan\);\s*'
    r'\}'
)

STAGE_HELPER = '''std::string soapy_source_c::stage_for_slot( const std::string & slot,
                                             size_t chan )
{
    const std::vector<std::string> names = this->get_gain_names(chan);
    const size_t n = names.size();
    if ( n == 0 )
        return std::string();

    if ( n <= 2 ) {
        // 1- or 2-stage devices: unchanged from prior behavior.
        if ( slot == "RF" ) return names.front();
        if ( slot == "BB" ) return names.back();
        return std::string(); // no true middle stage -- honest no-op
    }

    // n >= 3: front=RF, back=BB, true middle stage=IF.
    if ( n > 3 && ! _warned_multi_stage ) {
        std::cerr << "[soapy_source_c] WARNING: device reports " << n
                   << " gain stages; RF/IF/BB fields can only address 3 "
                   << "of them (RF=" << names.front()
                   << ", IF=" << names[n/2]
                   << ", BB=" << names.back()
                   << "). Use a named gain (e.g. via device args or "
                   << "-G name:value) to reach the rest." << std::endl;
        _warned_multi_stage = true;
    }

    if ( slot == "RF" ) return names.front();
    if ( slot == "IF" ) return names[n/2];
    if ( slot == "BB" ) return names.back();
    return std::string();
}
'''

NEW_IF_GAIN = '''double soapy_source_c::set_if_gain( double gain, size_t chan )
{
    const std::string name = this->stage_for_slot( "IF", chan );
    if ( name.empty() )
        return this->get_gain( chan ); // honest no-op, not a silent duplicate write
    return this->set_gain( gain, name, chan );
}'''

NEW_BB_GAIN = '''double soapy_source_c::set_bb_gain( double gain, size_t chan )
{
    const std::string name = this->stage_for_slot( "BB", chan );
    return this->set_gain( gain, name, chan );
}'''


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path-to-soapy_source_c.cc>")
        sys.exit(1)

    path = pathlib.Path(sys.argv[1])
    text = path.read_text()

    if_matches = IF_GAIN_PATTERN.findall(text)
    bb_matches = BB_GAIN_PATTERN.findall(text)

    if len(if_matches) != 1:
        print(f"ERROR: found {len(if_matches)} match(es) for set_if_gain() "
              "(expected exactly 1). No changes made.")
        sys.exit(2)
    if len(bb_matches) != 1:
        print(f"ERROR: found {len(bb_matches)} match(es) for set_bb_gain() "
              "(expected exactly 1). No changes made.")
        sys.exit(3)

    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    print(f"Backed up original to: {backup}")

    # Insert the shared helper right before set_if_gain(), then swap
    # both functions for their fixed versions.
    text = IF_GAIN_PATTERN.sub(STAGE_HELPER + NEW_IF_GAIN, text, count=1)
    text = BB_GAIN_PATTERN.sub(NEW_BB_GAIN, text, count=1)

    path.write_text(text)
    print(f"Patched: {path}")
    print("\nDon't forget to also add to soapy_source_c.h (private section):")
    print('    bool _warned_multi_stage = false;')
    print('    std::string stage_for_slot( const std::string & slot, size_t chan );')


if __name__ == "__main__":
    main()
