#!/usr/bin/env python3
"""
Round 2: fixes the remaining single-stage clobber -- BB Gain currently
still resolves to the same stage as RF Gain when the device only
reports one gain name (Sensitivity/Linearity mode), and since BB Gain
is applied last in GRC's generated init order, it silently overwrites
whatever RF Gain just set unless the two fields happen to match.

This makes BB Gain (like IF Gain already is) an honest no-op in that
situation, so "RF Gain alone" genuinely governs Sensitivity/Linearity
mode with zero caveats.

Only changes the n<=2 branch of stage_for_slot(); the n>=3 branch
(ordinary 3-stage Manual mode -- confirmed correct via SoapySDRUtil
--probe) is untouched.

Usage:
    python3 apply_bb_singlestage_fix.py ~/gr-osmosdr_n6rfm/lib/soapy/soapy_source_c.cc
"""
import sys, shutil, pathlib, re

OLD_BRANCH = re.compile(
    r'if \( n <= 2 \) \{\s*'
    r'// 1- or 2-stage devices: unchanged from prior behavior\.\s*'
    r'if \( slot == "RF" \) return names\.front\(\);\s*'
    r'if \( slot == "BB" \) return names\.back\(\);\s*'
    r'return std::string\(\); // no true middle stage -- honest no-op\s*'
    r'\}'
)

NEW_BRANCH = '''if ( n == 1 ) {
        // Single true stage (e.g. Sensitivity/Linearity table mode):
        // only RF Gain addresses it. IF and BB are honest no-ops here,
        // not silent duplicate/overwrite writes to the same stage.
        if ( slot == "RF" ) return names.front();
        return std::string();
    }

    if ( n == 2 ) {
        // Unchanged from prior behavior.
        if ( slot == "RF" ) return names.front();
        if ( slot == "BB" ) return names.back();
        return std::string(); // no true middle stage -- honest no-op
    }'''


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path-to-soapy_source_c.cc>")
        sys.exit(1)

    path = pathlib.Path(sys.argv[1])
    text = path.read_text()

    matches = OLD_BRANCH.findall(text)
    if len(matches) != 1:
        print(f"ERROR: found {len(matches)} match(es) for the n<=2 branch "
              "(expected exactly 1). No changes made.")
        print("This likely means round 1 wasn't applied yet, or this file "
              "differs from what round 2 expects.")
        sys.exit(2)

    backup = path.with_suffix(path.suffix + ".bak2")
    shutil.copy2(path, backup)
    print(f"Backed up original to: {backup}")

    text = OLD_BRANCH.sub(NEW_BRANCH, text, count=1)
    path.write_text(text)
    print(f"Patched: {path}")


if __name__ == "__main__":
    main()
