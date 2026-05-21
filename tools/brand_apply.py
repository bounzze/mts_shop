#!/usr/bin/env python3
"""
Meet the Seeds — Shopify Theme Brand Apply Tool
================================================
Applies the Meet the Seeds brand identity to the Shopify Horizon theme.

Brand colours  : Royal blue (#1d3686), light blue (#e1edf5), white (#ffffff)
Brand fonts    : Abril Fatface (headings), Akshar (subheadings), Assistant (body)
Font files in  : assets/mts_fonts/…   (copied flat to assets/ by this tool)

Usage
-----
  python tools/brand_apply.py [--dry-run] [--restore]

Options
  --dry-run    Print what would change, but write nothing.
  --restore    Restore from .bak backups created by a previous run.

What this tool does
-------------------
  1. Copies brand font TTF files into the flat assets/ directory.
  2. Updates config/settings_data.json
       • All six built-in colour schemes → brand palette
       • Heading/accent font → abril_fatface_n4 (Shopify CDN font)
  3. Writes snippets/mts-brand-fonts.liquid
       • @font-face declarations using {{ 'file.ttf' | asset_url }}
  4. Writes snippets/mts-brand-overrides.liquid
       • CSS variable overrides applied *after* theme-styles-variables
  5. Writes assets/mts-brand.css
       • Extra brand-specific static styles (buttons, borders, badges …)
  6. Patches layout/theme.liquid
       • Inserts   {%- render 'mts-brand-fonts' -%}
                   {%- render 'mts-brand-overrides' -%}
         after the existing render 'color-schemes' line.
  7. Patches snippets/stylesheets.liquid
       • Appends the mts-brand.css stylesheet tag.

Re-running the tool is safe — it is idempotent.
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPO_ROOT / "assets"
CONFIG_DIR = REPO_ROOT / "config"
SNIPPETS_DIR = REPO_ROOT / "snippets"
LAYOUT_DIR = REPO_ROOT / "layout"

FONTS_SRC_DIR = ASSETS_DIR / "mts_fonts" / "Abril_Fatface,Akshar,Assistant"

SETTINGS_FILE = CONFIG_DIR / "settings_data.json"
THEME_LAYOUT = LAYOUT_DIR / "theme.liquid"
STYLESHEETS_SNIPPET = SNIPPETS_DIR / "stylesheets.liquid"

# ─── Brand Config ─────────────────────────────────────────────────────────────
BRAND_BLUE        = "#1d3686"
BRAND_BLUE_DARK   = "#152a6e"
BRAND_BLUE_LIGHT  = "#e1edf5"
BRAND_BLUE_PALE   = "#f0f5fa"
BRAND_WHITE       = "#ffffff"
BRAND_TEXT_DARK   = "#1a1a2e"
BRAND_NAVY        = "#0d1b4b"

# Font files: source subdir → flat target filename
FONT_FILES = {
    "Abril_Fatface/AbrilFatface-Regular.ttf":          "AbrilFatface-Regular.ttf",
    "Akshar/Akshar-VariableFont_wght.ttf":             "Akshar-VariableFont_wght.ttf",
    "Assistant/Assistant-VariableFont_wght.ttf":       "Assistant-VariableFont_wght.ttf",
}

# Shopify font handle for the heading font (abril_fatface is in Shopify's library).
# Body + subheading are overridden purely via CSS — we keep inter there so the
# Shopify theme editor still works for those slots.
SHOPIFY_HEADING_FONT = "abril_fatface_n4"
SHOPIFY_ACCENT_FONT  = "abril_fatface_n4"

# ─── Colour Schemes ───────────────────────────────────────────────────────────

def _light_scheme(bg, fg_heading, fg, primary, primary_hover, border):
    """Helper that fills in the repetitive variant/button fields."""
    return {
        "background":                           bg,
        "foreground_heading":                   fg_heading,
        "foreground":                           fg,
        "primary":                              primary,
        "primary_hover":                        primary_hover,
        "border":                               border,
        "shadow":                               BRAND_BLUE + "40",
        "primary_button_background":            primary,
        "primary_button_text":                  BRAND_WHITE,
        "primary_button_border":                primary,
        "primary_button_hover_background":      primary_hover,
        "primary_button_hover_text":            BRAND_WHITE,
        "primary_button_hover_border":          primary_hover,
        "secondary_button_background":          "rgba(0,0,0,0)",
        "secondary_button_text":                primary,
        "secondary_button_border":              primary,
        "secondary_button_hover_background":    BRAND_BLUE_LIGHT,
        "secondary_button_hover_text":          primary_hover,
        "secondary_button_hover_border":        primary_hover,
        "input_background":                     BRAND_WHITE + "c7",
        "input_text_color":                     BRAND_TEXT_DARK,
        "input_border_color":                   BRAND_BLUE + "30",
        "input_hover_background":               BRAND_BLUE_PALE,
        "variant_background_color":             BRAND_WHITE,
        "variant_text_color":                   BRAND_BLUE,
        "variant_border_color":                 BRAND_BLUE + "30",
        "variant_hover_background_color":       BRAND_BLUE_LIGHT,
        "variant_hover_text_color":             BRAND_BLUE,
        "variant_hover_border_color":           BRAND_BLUE + "50",
        "selected_variant_background_color":    BRAND_BLUE,
        "selected_variant_text_color":          BRAND_WHITE,
        "selected_variant_border_color":        BRAND_BLUE,
        "selected_variant_hover_background_color": BRAND_BLUE_DARK,
        "selected_variant_hover_text_color":    BRAND_WHITE,
        "selected_variant_hover_border_color":  BRAND_BLUE_DARK,
    }


def _dark_scheme(bg, button_bg, button_text):
    """Helper for dark / inverted schemes."""
    return {
        "background":                           bg,
        "foreground_heading":                   BRAND_WHITE,
        "foreground":                           BRAND_WHITE + "cf",
        "primary":                              BRAND_WHITE + "cf",
        "primary_hover":                        BRAND_WHITE,
        "border":                               BRAND_WHITE + "20",
        "shadow":                               "#000000",
        "primary_button_background":            button_bg,
        "primary_button_text":                  button_text,
        "primary_button_border":                button_bg,
        "primary_button_hover_background":      BRAND_BLUE_LIGHT,
        "primary_button_hover_text":            BRAND_BLUE,
        "primary_button_hover_border":          BRAND_BLUE_LIGHT,
        "secondary_button_background":          "rgba(0,0,0,0)",
        "secondary_button_text":                BRAND_WHITE,
        "secondary_button_border":              BRAND_WHITE + "b0",
        "secondary_button_hover_background":    BRAND_WHITE + "14",
        "secondary_button_hover_text":          BRAND_WHITE,
        "secondary_button_hover_border":        BRAND_WHITE,
        "input_background":                     bg,
        "input_text_color":                     BRAND_WHITE + "ed",
        "input_border_color":                   BRAND_WHITE + "b0",
        "input_hover_background":               BRAND_WHITE + "0a",
        "variant_background_color":             BRAND_WHITE,
        "variant_text_color":                   BRAND_BLUE,
        "variant_border_color":                 BRAND_BLUE_LIGHT,
        "variant_hover_background_color":       BRAND_BLUE_LIGHT,
        "variant_hover_text_color":             BRAND_BLUE,
        "variant_hover_border_color":           BRAND_BLUE_LIGHT,
        "selected_variant_background_color":    BRAND_WHITE,
        "selected_variant_text_color":          BRAND_BLUE,
        "selected_variant_border_color":        BRAND_WHITE,
        "selected_variant_hover_background_color": BRAND_BLUE_LIGHT,
        "selected_variant_hover_text_color":    BRAND_BLUE,
        "selected_variant_hover_border_color":  BRAND_BLUE_LIGHT,
    }


BRAND_COLOR_SCHEMES = {
    "scheme-1": _light_scheme(
        bg=BRAND_WHITE,
        fg_heading=BRAND_BLUE,
        fg=BRAND_TEXT_DARK,
        primary=BRAND_BLUE,
        primary_hover=BRAND_BLUE_DARK,
        border=BRAND_BLUE + "15",
    ),
    "scheme-2": _light_scheme(
        bg=BRAND_BLUE_LIGHT,
        fg_heading=BRAND_BLUE,
        fg=BRAND_TEXT_DARK + "cf",
        primary=BRAND_BLUE,
        primary_hover=BRAND_BLUE_DARK,
        border=BRAND_BLUE + "25",
    ),
    "scheme-3": _light_scheme(
        bg=BRAND_BLUE_PALE,
        fg_heading=BRAND_BLUE,
        fg=BRAND_TEXT_DARK + "cf",
        primary=BRAND_BLUE + "cf",
        primary_hover=BRAND_BLUE,
        border=BRAND_BLUE + "cf",
    ),
    "scheme-4": _dark_scheme(
        bg=BRAND_BLUE,
        button_bg=BRAND_WHITE,
        button_text=BRAND_BLUE,
    ),
    "scheme-5": _dark_scheme(
        bg=BRAND_NAVY,
        button_bg=BRAND_BLUE_LIGHT,
        button_text=BRAND_BLUE,
    ),
    "scheme-6": {
        **_light_scheme(
            bg="rgba(0,0,0,0)",
            fg_heading=BRAND_WHITE,
            fg=BRAND_WHITE,
            primary=BRAND_WHITE,
            primary_hover=BRAND_WHITE + "b0",
            border="#e6e6e6",
        ),
        "primary_button_background":  BRAND_WHITE,
        "primary_button_text":        BRAND_BLUE,
        "primary_button_border":      BRAND_WHITE,
        "primary_button_hover_background": BRAND_BLUE_LIGHT,
        "primary_button_hover_text":  BRAND_BLUE,
        "primary_button_hover_border": BRAND_BLUE_LIGHT,
        "secondary_button_background": "rgba(0,0,0,0)",
        "secondary_button_text":       BRAND_WHITE,
        "secondary_button_border":     BRAND_WHITE,
        "secondary_button_hover_background": BRAND_WHITE + "14",
        "secondary_button_hover_text": BRAND_WHITE,
        "secondary_button_hover_border": BRAND_WHITE,
        "input_background":  BRAND_WHITE,
        "input_text_color":  BRAND_TEXT_DARK + "87",
        "input_border_color": BRAND_TEXT_DARK + "21",
        "input_hover_background": "#fafafa",
    },
}

# ─── Generated snippet content ────────────────────────────────────────────────

MTS_BRAND_FONTS_LIQUID = """\
{%- comment -%}
  Meet the Seeds — Custom brand font-face declarations.
  Font TTF files must be present in the theme's /assets/ directory.
  Run tools/brand_apply.py to copy them from assets/mts_fonts/.
{%- endcomment -%}
<style>
  @font-face {
    font-family: 'Abril Fatface';
    src: url('{{ 'AbrilFatface-Regular.ttf' | asset_url }}') format('truetype');
    font-weight: 400;
    font-style: normal;
    font-display: swap;
  }

  @font-face {
    font-family: 'Akshar';
    src: url('{{ 'Akshar-VariableFont_wght.ttf' | asset_url }}') format('truetype');
    font-weight: 100 900;
    font-style: normal;
    font-display: swap;
  }

  @font-face {
    font-family: 'Assistant';
    src: url('{{ 'Assistant-VariableFont_wght.ttf' | asset_url }}') format('truetype');
    font-weight: 100 900;
    font-style: normal;
    font-display: swap;
  }
</style>
"""

MTS_BRAND_OVERRIDES_LIQUID = """\
{%- comment -%}
  Meet the Seeds — CSS variable overrides.
  Rendered AFTER theme-styles-variables and color-schemes so our brand
  values win in the cascade for :root custom properties.
{%- endcomment -%}
{% style %}
  :root {
    /* ── Brand font families ─────────────────────────────────────────── */
    --font-body--family:       'Assistant', Helvetica Neue, sans-serif;
    --font-body--weight:       400;
    --font-body--style:        normal;

    --font-subheading--family: 'Akshar', Arial, sans-serif;
    --font-subheading--weight: 600;
    --font-subheading--style:  normal;

    --font-heading--family:    'Abril Fatface', Georgia, serif;
    --font-heading--weight:    400;
    --font-heading--style:     normal;

    --font-accent--family:     'Abril Fatface', Georgia, serif;
    --font-accent--weight:     400;
    --font-accent--style:      normal;

    /* ── Brand letter spacing ────────────────────────────────────────── */
    --letter-spacing--heading-normal:  0em;
    --letter-spacing--display-normal:  -0.01em;

    /* ── Button border radius — slightly rounded, clean look ─────────── */
    --style-border-radius-buttons-primary:   8px;
    --style-border-radius-buttons-secondary: 8px;

    /* ── Badge border radius ─────────────────────────────────────────── */
    --style-border-radius-badge: 4px;
  }
{% endstyle %}
"""

MTS_BRAND_CSS = """\
/*
 * Meet the Seeds — Supplementary brand styles
 * Loaded after base.css via stylesheets.liquid.
 * CSS custom properties are overridden in snippets/mts-brand-overrides.liquid.
 */

/* ── Focus ring ──────────────────────────────────────────────────────────── */
:focus-visible {
  outline: 2px solid #1d3686;
  outline-offset: 2px;
}

/* ── Selection highlight ─────────────────────────────────────────────────── */
::selection {
  background-color: #1d368620;
  color: #1d3686;
}

/* ── Subheading / label uppercase accent ─────────────────────────────────── */
h5,
h6,
.h5,
.h6 {
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

/* ── Announcement bar ────────────────────────────────────────────────────── */
.announcement-bar {
  background-color: #1d3686;
  color: #ffffff;
}

/* ── Header logo height override (logo image is tall) ───────────────────── */
.header__heading-logo {
  max-height: 48px;
}

/* ── Product badges — brand colours ─────────────────────────────────────── */
.badge--sale {
  background-color: #1d3686 !important;
  color: #ffffff !important;
}

/* ── Cart bubble ─────────────────────────────────────────────────────────── */
.cart-count-bubble {
  background-color: #1d3686;
  color: #ffffff;
}

/* ── Scrollbar (Chromium) ────────────────────────────────────────────────── */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: #e1edf5;
}
::-webkit-scrollbar-thumb {
  background: #1d368660;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #1d3686;
}
"""

# ─── Helpers ──────────────────────────────────────────────────────────────────

def backup(path: Path) -> Path:
    """Create a .bak copy of a file (once; never overwrites an existing .bak)."""
    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    return bak


def restore(path: Path) -> bool:
    """Restore from a .bak file if it exists. Returns True on success."""
    bak = path.with_suffix(path.suffix + ".bak")
    if bak.exists():
        shutil.copy2(bak, path)
        return True
    return False


def write_file(path: Path, content: str, dry_run: bool, label: str) -> None:
    if dry_run:
        print(f"  [DRY-RUN] Would write: {path.relative_to(REPO_ROOT)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  ✓  {label}: {path.relative_to(REPO_ROOT)}")


# ─── Step 1: Copy font files ──────────────────────────────────────────────────

def copy_fonts(dry_run: bool) -> None:
    print("\n[1] Copying brand font files to assets/ …")
    for rel_src, target_name in FONT_FILES.items():
        src = FONTS_SRC_DIR / rel_src
        dst = ASSETS_DIR / target_name
        if not src.exists():
            print(f"  ⚠  Source not found, skipping: {src}")
            continue
        if dry_run:
            print(f"  [DRY-RUN] Would copy {src.name} → assets/{target_name}")
            continue
        if dst.exists() and dst.stat().st_size == src.stat().st_size:
            print(f"  –  Already up-to-date: assets/{target_name}")
            continue
        shutil.copy2(src, dst)
        print(f"  ✓  Copied: assets/{target_name}")


# ─── Step 2: Update settings_data.json ───────────────────────────────────────

def update_settings(dry_run: bool) -> None:
    print("\n[2] Updating config/settings_data.json …")
    with open(SETTINGS_FILE, encoding="utf-8") as fh:
        data = json.load(fh)

    current = data.get("current", {})
    changed: list[str] = []

    # ── Fonts ──
    for key, new_val in [
        ("type_heading_font", SHOPIFY_HEADING_FONT),
        ("type_accent_font",  SHOPIFY_ACCENT_FONT),
    ]:
        old = current.get(key, "")
        if old != new_val:
            current[key] = new_val
            changed.append(f"    {key}: {old!r} → {new_val!r}")

    # ── Colour schemes ──
    schemes = current.get("color_schemes", {})
    for scheme_id, brand_settings in BRAND_COLOR_SCHEMES.items():
        if scheme_id not in schemes:
            schemes[scheme_id] = {"settings": {}}
        old_settings = schemes[scheme_id].get("settings", {})
        diff = {k: v for k, v in brand_settings.items() if old_settings.get(k) != v}
        if diff:
            schemes[scheme_id]["settings"].update(brand_settings)
            changed.append(f"    {scheme_id}: {len(diff)} colour field(s) updated")

    current["color_schemes"] = schemes
    data["current"] = current

    if not changed:
        print("  –  No changes needed in settings_data.json")
        return

    if not dry_run:
        backup(SETTINGS_FILE)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=None, separators=(",", ":"))
        print(f"  ✓  settings_data.json updated ({len(changed)} change group(s))")
    else:
        print(f"  [DRY-RUN] Would update settings_data.json:")

    for line in changed:
        print(line)


# ─── Steps 3 & 4: Brand snippets ─────────────────────────────────────────────

def write_snippets(dry_run: bool) -> None:
    print("\n[3] Writing brand Liquid snippets …")
    write_file(SNIPPETS_DIR / "mts-brand-fonts.liquid",
               MTS_BRAND_FONTS_LIQUID, dry_run, "mts-brand-fonts.liquid")
    write_file(SNIPPETS_DIR / "mts-brand-overrides.liquid",
               MTS_BRAND_OVERRIDES_LIQUID, dry_run, "mts-brand-overrides.liquid")


# ─── Step 5: Brand CSS ────────────────────────────────────────────────────────

def write_brand_css(dry_run: bool) -> None:
    print("\n[4] Writing assets/mts-brand.css …")
    write_file(ASSETS_DIR / "mts-brand.css", MTS_BRAND_CSS, dry_run, "mts-brand.css")


# ─── Step 6: Patch theme.liquid ───────────────────────────────────────────────

THEME_INJECTION = (
    "{%- render 'color-schemes' -%}",
    (
        "{%- render 'color-schemes' -%}\n"
        "    {%- render 'mts-brand-fonts' -%}\n"
        "    {%- render 'mts-brand-overrides' -%}"
    ),
)


def patch_theme_liquid(dry_run: bool) -> None:
    print("\n[5] Patching layout/theme.liquid …")
    content = THEME_LAYOUT.read_text(encoding="utf-8")
    old, new = THEME_INJECTION

    if new.strip() in content.replace("\n", " "):
        # Already patched
        print("  –  theme.liquid already contains brand snippet renders")
        return

    if old not in content:
        print("  ⚠  Could not find injection point in theme.liquid — manual edit needed")
        print(f"     Add the following lines after:  {old!r}")
        print("       {%- render 'mts-brand-fonts' -%}")
        print("       {%- render 'mts-brand-overrides' -%}")
        return

    patched = content.replace(old, new, 1)
    if dry_run:
        print("  [DRY-RUN] Would insert mts-brand-fonts + mts-brand-overrides renders")
        return
    backup(THEME_LAYOUT)
    THEME_LAYOUT.write_text(patched, encoding="utf-8")
    print("  ✓  theme.liquid patched")


# ─── Step 7: Patch stylesheets.liquid ────────────────────────────────────────

STYLESHEETS_INJECTION_MARKER = "mts-brand.css"
STYLESHEETS_APPEND = (
    "\n{{ 'mts-brand.css' | asset_url | stylesheet_tag }}"
)


def patch_stylesheets(dry_run: bool) -> None:
    print("\n[6] Patching snippets/stylesheets.liquid …")
    content = STYLESHEETS_SNIPPET.read_text(encoding="utf-8")

    if STYLESHEETS_INJECTION_MARKER in content:
        print("  –  stylesheets.liquid already includes mts-brand.css")
        return

    patched = content.rstrip() + STYLESHEETS_APPEND + "\n"
    if dry_run:
        print("  [DRY-RUN] Would append mts-brand.css stylesheet_tag")
        return
    backup(STYLESHEETS_SNIPPET)
    STYLESHEETS_SNIPPET.write_text(patched, encoding="utf-8")
    print("  ✓  stylesheets.liquid patched")


# ─── Restore mode ─────────────────────────────────────────────────────────────

def restore_all() -> None:
    targets = [SETTINGS_FILE, THEME_LAYOUT, STYLESHEETS_SNIPPET]
    print("\nRestoring backups …")
    for t in targets:
        if restore(t):
            print(f"  ✓  Restored: {t.relative_to(REPO_ROOT)}")
        else:
            print(f"  –  No backup found for: {t.relative_to(REPO_ROOT)}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply Meet the Seeds brand to the Shopify Horizon theme."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing any files.")
    parser.add_argument("--restore", action="store_true",
                        help="Restore original files from .bak backups.")
    args = parser.parse_args()

    if not REPO_ROOT.is_dir():
        sys.exit(f"Error: repo root not found at {REPO_ROOT}")

    if args.restore:
        restore_all()
        return

    print("=" * 60)
    print("  Meet the Seeds — Brand Apply Tool")
    if args.dry_run:
        print("  MODE: DRY-RUN (no files will be written)")
    print("=" * 60)

    copy_fonts(args.dry_run)
    update_settings(args.dry_run)
    write_snippets(args.dry_run)
    write_brand_css(args.dry_run)
    patch_theme_liquid(args.dry_run)
    patch_stylesheets(args.dry_run)

    print("\n" + "=" * 60)
    if args.dry_run:
        print("  Dry-run complete. Re-run without --dry-run to apply.")
    else:
        print("  Brand applied successfully!")
        print()
        print("  Next steps:")
        print("  • Push changes to Shopify with the Shopify CLI:")
        print("    shopify theme push")
        print("  • In the Shopify theme editor, set the logo image to")
        print("    assets/mts_images/Logo Meet the Seeds.png")
        print("  • Verify colour schemes look correct in the theme editor.")
    print("=" * 60)


if __name__ == "__main__":
    main()
