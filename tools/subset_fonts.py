"""
Subset brand fonts to Latin WOFF2 for fast loading.
Reduces ~800KB of TTF to ~120KB of WOFF2.

Usage: python tools/subset_fonts.py
"""
import os
import sys

ASSETS = os.path.join(os.path.dirname(__file__), '..', 'assets')

# Latin + Extended Latin + punctuation + currency + arrows
UNICODES = (
    'U+0000-00FF,'   # Basic Latin + Latin-1 Supplement
    'U+0131,'        # ı (dotless i, NL/TR)
    'U+0152-0153,'   # Œ œ
    'U+02BB-02BC,'   # Modifier letters
    'U+02C6,U+02DA,U+02DC,'
    'U+2000-206F,'   # General Punctuation
    'U+2074,'        # ⁴
    'U+20AC,'        # € (euro)
    'U+2122,'        # ™
    'U+2212,U+2215,' # − ∕
    'U+FEFF,U+FFFD'  # BOM, replacement character
)

FONTS = [
    ('AbrilFatface-Regular.ttf',           'mts-abril-fatface.woff2'),
    ('Akshar-VariableFont_wght.ttf',        'mts-akshar.woff2'),
    ('Assistant-VariableFont_wght.ttf',     'mts-assistant.woff2'),
]


def main():
    try:
        from fontTools.subset import main as ft_subset
    except ImportError:
        print("ERROR: fonttools not found. Run: pip install fonttools brotli")
        sys.exit(1)

    for src_name, dst_name in FONTS:
        src = os.path.join(ASSETS, src_name)
        dst = os.path.join(ASSETS, dst_name)

        if not os.path.exists(src):
            print(f"SKIP (not found): {src_name}")
            continue

        args = [
            src,
            f'--output-file={dst}',
            f'--unicodes={UNICODES}',
            '--flavor=woff2',
            '--layout-features=*',  # keep all OpenType features
            '--no-hinting',
            '--desubroutinize',
        ]

        print(f"Subsetting {src_name} ...", end=' ', flush=True)
        ft_subset(args)

        src_kb = os.path.getsize(src) // 1024
        dst_kb = os.path.getsize(dst) // 1024
        saving = 100 - round(dst_kb / src_kb * 100)
        print(f"{src_kb} KB → {dst_kb} KB  (−{saving}%)")

    print("\nDone. Update mts-brand-fonts.liquid to use the .woff2 files.")


if __name__ == '__main__':
    main()
