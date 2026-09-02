#!/usr/bin/env python3
"""Expand sources/glass.tokens.yaml into full HA-2026 theme YAML files.

Why a generator: since the 2025->2026 frontend migration (Polymer/Paper ->
Web Awesome) a theme has to satisfy four token layers that are mostly
mechanical derivations of ~30 real design decisions:

    --ha-color-* / --ha-space-* / --ha-font-*   source of truth
        -> --wa-*                                Web Awesome consumption layer
        -> legacy --primary-color / --ha-card-*  compatibility layer
        -> --mdc-* residue                       (dead; deliberately not emitted)

Hand-maintaining ~300 keys per theme is how themes rot. Edit the tokens file,
run this, commit the output.

    python3 scripts/build_glass_themes.py

Emits one file per variant into themes/ , plus a self-check.
"""
from __future__ import annotations

import colorsys
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "glass.tokens.yaml"
THEMES = ROOT / "themes"

RAMP_STEPS = [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95]

# HA's --ha-border-radius-* scale (core.globals.ts)
RADIUS_PX = {
    "sm": 4, "md": 8, "lg": 12, "xl": 16, "2xl": 20,
    "3xl": 24, "4xl": 28, "5xl": 32, "6xl": 36,
}


# --------------------------------------------------------------------------
# colour helpers
# --------------------------------------------------------------------------
def hex2rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def rgb2hex(r: float, g: float, b: float) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in (r, g, b))


def ramp(base_hex: str) -> dict[int, str]:
    """11-step lightness ramp through a hue. Step 40 is the base colour.

    HA only auto-generates this (OKLCH, palette.ts) for the built-in default
    theme -- a custom theme MUST emit its own ramp or every Web Awesome
    button, switch and focus ring stays HA cyan.
    """
    r, g, b = (v / 255 for v in hex2rgb(base_hex))
    h, l0, s = colorsys.rgb_to_hls(r, g, b)
    out: dict[int, str] = {}
    for step in RAMP_STEPS:
        if step == 40:
            out[step] = base_hex.lower()
            continue
        # Piecewise-linear lightness anchored at step 40 == the brand colour,
        # so the ramp stays monotonic whatever the brand's own lightness is.
        if step < 40:
            lt = 0.08 + (l0 - 0.08) * ((step - 5) / 35)
        else:
            lt = l0 + (0.95 - l0) * ((step - 40) / 55)
        # desaturate towards the extremes, the way perceptual ramps do
        st = s * (1 - abs(step - 40) / 110)
        rr, gg, bb = colorsys.hls_to_rgb(h, lt, max(0.0, min(1.0, st)))
        out[step] = rgb2hex(rr * 255, gg * 255, bb * 255)
    return out


def luminance_of_gradient(css: str) -> float:
    """Rough perceived lightness of a CSS gradient, 0..1, from its hex stops."""
    stops = re.findall(r"#[0-9a-fA-F]{3,6}", css)
    if not stops:
        return 0.5
    total = 0.0
    for s in stops:
        r, g, b = (v / 255 for v in hex2rgb(s))
        total += 0.2126 * r + 0.7152 * g + 0.0722 * b
    return total / len(stops)


def rgba(hex_or_rgba: str, alpha: float) -> str:
    if hex_or_rgba.startswith("rgba") or hex_or_rgba.startswith("rgb"):
        return hex_or_rgba
    r, g, b = hex2rgb(hex_or_rgba)
    return f"rgba({r}, {g}, {b}, {alpha})"


# --------------------------------------------------------------------------
# layer builders
# --------------------------------------------------------------------------
def global_layer(v: dict, status: dict, prim: dict[int, str], neut: dict[int, str]) -> dict:
    """Everything that does not change between light and dark."""
    radius = RADIUS_PX[v["radius"]]
    blur = v["glass"]["blur"]
    sat = v["glass"]["saturate"]
    filt = f"blur({blur}) saturate({sat})"

    t: dict[str, str] = {}

    # ---- layer 1: core design tokens -------------------------------------
    for step in RAMP_STEPS:
        t[f"ha-color-primary-{step:02d}"] = prim[step]
        t[f"ha-color-neutral-{step:02d}"] = neut[step]

    t["ha-border-radius-lg"] = f"{max(8, radius - 8)}px"
    t["ha-border-radius-xl"] = f"{max(10, radius - 4)}px"
    t["ha-border-radius-2xl"] = f"{radius}px"
    t["ha-border-radius-3xl"] = f"{radius + 4}px"
    t["ha-font-family-heading"] = "var(--ha-font-family-body)"

    # ---- glass surfaces (ha-card / ha-badge share these) ------------------
    t["ha-card-border-radius"] = f"{radius}px"
    t["ha-card-border-width"] = "1px"
    t["ha-card-backdrop-filter"] = filt
    t["ha-badge-border-radius"] = f"{radius}px"

    # dialogs + the new mobile bottom sheet (2026 more-info is a bottom sheet
    # on phones -- a glass theme that skips these breaks on mobile)
    t["ha-dialog-border-radius"] = f"{radius + 4}px"
    t["ha-dialog-surface-backdrop-filter"] = filt
    t["ha-dialog-scrim-backdrop-filter"] = "blur(6px) brightness(60%)"
    t["dialog-backdrop-filter"] = filt
    t["ha-bottom-sheet-border-radius"] = f"{radius + 8}px"
    t["ha-bottom-sheet-surface-backdrop-filter"] = filt
    t["ha-bottom-sheet-scrim-backdrop-filter"] = "blur(6px) brightness(60%)"
    t["app-header-backdrop-filter"] = filt

    # sections view: glass panes need visible gutters to read as separate panes
    t["ha-view-sections-column-gap"] = "16px"
    t["ha-view-sections-row-gap"] = "16px"
    t["ha-section-border-radius"] = f"{radius}px"
    t["ha-section-grid-column-gap"] = "12px"
    t["ha-section-grid-row-gap"] = "12px"

    # tile / feature / heading cards
    t["ha-tile-icon-border-radius"] = f"{max(10, radius - 6)}px"
    t["tile-icon-border-radius"] = f"{max(10, radius - 6)}px"
    t["ha-card-features-border-radius"] = f"{max(10, radius - 6)}px"
    t["feature-border-radius"] = f"{max(10, radius - 6)}px"
    t["ha-card-feature-gap"] = "8px"

    # controls
    t["ha-button-border-radius"] = "9999px"
    t["ha-checkbox-border-radius"] = "6px"
    t["ha-tooltip-border-radius"] = "10px"
    t["wa-panel-border-radius"] = f"{radius}px"
    t["wa-border-radius-l"] = f"{max(10, radius - 8)}px"
    t["wa-border-radius-pill"] = "9999px"
    t["wa-form-control-border-radius"] = f"{max(10, radius - 8)}px"

    # ---- Apple status palette (legacy named swatches, still literal) ------
    for name, hexv in status.items():
        t[f"{name}-color"] = hexv
    t["error-color"] = status["red"]
    t["warning-color"] = status["orange"]
    t["success-color"] = status["green"]
    t["info-color"] = status["blue"]
    for label, key in (("error", "red"), ("warning", "orange"),
                       ("success", "green"), ("info", "blue")):
        r, g, b = hex2rgb(status[key])
        t[f"rgb-{label}-color"] = f"{r}, {g}, {b}"

    t["primary-color"] = prim[40]
    t["accent-color"] = prim[50]
    r, g, b = hex2rgb(prim[40])
    t["rgb-primary-color"] = f"{r}, {g}, {b}"
    t["app-theme-color"] = prim[40]

    # ha-color-focus drives every focus ring in Web Awesome
    t["ha-color-focus"] = prim[50]
    t["wa-focus-ring-color"] = prim[50]

    return t


def mode_layer(v: dict, mode: str, prim: dict[int, str], neut: dict[int, str]) -> dict:
    g = v["glass"][mode]
    bg = v["background"][mode]
    tint, rim = g["tint"], g["rim"]
    is_light_bg = luminance_of_gradient(bg["gradient"]) > 0.55

    # Foreground family follows the BACKDROP, not the mode name: visionOS ships
    # a dark wallpaper in both modes, so both modes want light text.
    if is_light_bg:
        fg, fg_soft, fg_mute = "#1a1c20", "rgba(26, 28, 32, 0.68)", "rgba(26, 28, 32, 0.38)"
        fg_rgb, on_glass = "26, 28, 32", "#111318"
        scrim_lo, scrim_hi = "rgba(255, 255, 255, 0.55)", "rgba(255, 255, 255, 0.72)"
        hair = "rgba(0, 0, 0, 0.10)"
        ctl, ctl_hi = "rgba(0, 0, 0, 0.09)", "rgba(0, 0, 0, 0.15)"
        shadow = "0 1px 2px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.10)"
    else:
        fg, fg_soft, fg_mute = "rgba(255, 255, 255, 0.96)", "rgba(255, 255, 255, 0.66)", "rgba(255, 255, 255, 0.36)"
        fg_rgb, on_glass = "255, 255, 255", "#ffffff"
        scrim_lo, scrim_hi = "rgba(255, 255, 255, 0.10)", "rgba(255, 255, 255, 0.16)"
        hair = "rgba(255, 255, 255, 0.14)"
        ctl, ctl_hi = "rgba(255, 255, 255, 0.14)", "rgba(255, 255, 255, 0.22)"
        shadow = "0 1px 2px rgba(0,0,0,0.20), 0 10px 30px rgba(0,0,0,0.28)"

    # Gradient FIRST (bottom layer, always paints), image on top. HACS does not
    # ship www/, so the theme must look finished with no image present.
    backdrop = f"center / cover no-repeat fixed url('{bg['image']}'), {bg['gradient']}"

    t: dict[str, str] = {
        # ---- background --------------------------------------------------
        "background-image": backdrop,
        "lovelace-background": backdrop,
        "primary-background-color": bg["gradient"],
        "secondary-background-color": scrim_lo,
        "clear-background-color": tint,
        "app-header-background-color": "transparent",

        # ---- text (layer 1 -> legacy is derived by HA for these three) ----
        "ha-color-text-primary": fg,
        "ha-color-text-secondary": fg_soft,
        "ha-color-text-disabled": fg_mute,
        "ha-color-text-link": prim[50],
        "primary-text-color": fg,
        "secondary-text-color": fg_soft,
        "disabled-text-color": fg_mute,
        "text-primary-color": fg,
        "text-dark-color": fg,
        "rgb-primary-text-color": fg_rgb,
        "lumo-body-text-color": fg,

        # ---- semantic surfaces (new in 2026, unstyled by pre-2026 themes) -
        "ha-color-surface-default": tint,
        "ha-color-surface-low": scrim_lo,
        "ha-color-surface-lower": scrim_hi,
        "ha-color-on-surface-default": fg,
        "ha-color-form-background": scrim_lo,
        "ha-color-form-hover": scrim_hi,
        "ha-color-form-disabled": hair,

        # ---- glass card --------------------------------------------------
        "ha-card-background": tint,
        "ha-card-border-color": rim,
        "ha-card-box-shadow": shadow,
        "card-background-color": tint,
        "ha-dialog-surface-background": scrim_hi,
        "ha-bottom-sheet-surface-background": scrim_hi,
        "ha-bottom-sheet-handle-color": fg_mute,
        "material-background-color": scrim_hi,

        # ---- dividers / outlines ------------------------------------------
        "divider-color": hair,
        "outline-color": hair,
        "outline-hover-color": rim,
        "ha-color-border-neutral-quiet": hair,
        "ha-color-border-neutral-normal": rim,
        "ha-color-border-neutral-loud": fg_soft,
        "ha-color-border-primary-quiet": rgba(prim[40], 0.25),
        "ha-color-border-primary-normal": prim[40],

        # ---- fills (drives ha-button / ha-switch / ha-checkbox) -----------
        "ha-color-fill-neutral-quiet-resting": ctl,
        "ha-color-fill-neutral-quiet-hover": ctl_hi,
        "ha-color-fill-neutral-quiet-active": ctl_hi,
        "ha-color-fill-neutral-normal-resting": ctl_hi,
        "ha-color-fill-neutral-normal-hover": ctl_hi,
        "ha-color-fill-neutral-loud-resting": fg_soft,
        "ha-color-fill-primary-quiet-resting": rgba(prim[40], 0.16),
        "ha-color-fill-primary-quiet-hover": rgba(prim[40], 0.24),
        "ha-color-fill-primary-quiet-active": rgba(prim[40], 0.30),
        "ha-color-fill-primary-normal-resting": prim[40],
        "ha-color-fill-primary-normal-hover": prim[50],
        "ha-color-fill-primary-normal-active": prim[30],
        "ha-color-fill-primary-loud-resting": prim[40],
        "ha-color-fill-primary-loud-hover": prim[50],
        "ha-color-fill-primary-loud-active": prim[30],
        "ha-color-fill-disabled-quiet-resting": hair,
        "ha-color-fill-disabled-normal-resting": hair,
        "ha-color-on-neutral-quiet": fg,
        "ha-color-on-neutral-normal": fg,
        "ha-color-on-neutral-loud": on_glass,
        "ha-color-on-primary-quiet": prim[50] if not is_light_bg else prim[30],
        "ha-color-on-primary-normal": "#ffffff",
        "ha-color-on-primary-loud": "#ffffff",
        "ha-color-on-disabled-quiet": fg_mute,
        "ha-color-on-disabled-normal": fg_mute,

        # ---- Web Awesome bridge (the layer 2024-era themes miss entirely) --
        "wa-color-brand-fill-loud": prim[40],
        "wa-color-brand-fill-normal": rgba(prim[40], 0.24),
        "wa-color-brand-fill-quiet": rgba(prim[40], 0.14),
        "wa-color-brand-border-loud": prim[40],
        "wa-color-brand-border-normal": rgba(prim[40], 0.55),
        "wa-color-brand-border-quiet": rgba(prim[40], 0.28),
        "wa-color-brand-on-loud": "#ffffff",
        "wa-color-brand-on-normal": prim[50] if not is_light_bg else prim[30],
        "wa-color-brand-on-quiet": prim[50] if not is_light_bg else prim[30],
        "wa-color-neutral-fill-loud": fg_soft,
        "wa-color-neutral-fill-normal": ctl_hi,
        "wa-color-neutral-fill-quiet": ctl,
        "wa-color-neutral-border-loud": fg_soft,
        "wa-color-neutral-border-normal": rim,
        "wa-color-neutral-border-quiet": hair,
        "wa-color-neutral-on-loud": on_glass,
        "wa-color-neutral-on-normal": fg,
        "wa-color-neutral-on-quiet": fg,
        "wa-color-text-normal": fg,
        "wa-color-text-quiet": fg_soft,
        "wa-color-surface-default": tint,
        "wa-color-surface-raised": scrim_hi,
        "wa-color-surface-border": rim,
        "wa-form-control-background-color": ctl,
        "wa-form-control-border-color": rim,
        "wa-form-control-value-color": fg,
        "wa-form-control-placeholder-color": fg_mute,

        # ---- sidebar (note: --sidebar-selected-text-color is DEAD in 2026) -
        "sidebar-background-color": scrim_lo,
        "sidebar-text-color": fg_soft,
        "sidebar-icon-color": fg_soft,
        "sidebar-selected-icon-color": prim[40],
        "sidebar-menu-button-background-color": "transparent",
        "sidebar-menu-button-text-color": fg,

        # ---- states / icons ------------------------------------------------
        "state-icon-color": fg_soft,
        "state-icon-active-color": prim[40],
        "state-icon-unavailable-color": fg_mute,
        "state-inactive-color": fg_mute,

        # ---- tiles / badges ------------------------------------------------
        "ha-tile-info-primary-color": fg,
        "ha-tile-info-secondary-color": fg_soft,
        "tile-icon-color": fg_soft,
        "ha-heading-card-title-color": fg,
        "ha-heading-card-subtitle-color": fg_soft,

        # ---- inputs ---------------------------------------------------------
        "input-ink-color": fg,
        "input-fill-color": "transparent",
        "input-disabled-fill-color": "transparent",
        "input-label-ink-color": fg_soft,
        "input-disabled-ink-color": fg_mute,
        "input-dropdown-icon-color": fg_soft,
        "input-idle-line-color": hair,
        "input-hover-line-color": rim,

        # ---- switches / sliders ---------------------------------------------
        "switch-checked-track-color": prim[40],
        "switch-checked-button-color": "#ffffff",
        "switch-unchecked-track-color": ctl_hi,
        "switch-unchecked-button-color": "#ffffff",
        "ha-switch-checked-background-color": prim[40],
        "ha-checkbox-checked-background-color": prim[40],
        "ha-checkbox-checked-icon-color": "#ffffff",
        "ha-checkbox-border-color": ctl_hi,
        "slider-color": prim[40],
        "slider-secondary-color": scrim_hi,
        "slider-track-color": ctl_hi,

        # ---- tables / code ---------------------------------------------------
        "table-row-background-color": "transparent",
        "table-row-alternative-background-color": scrim_lo,
        "data-table-background-color": "transparent",
        "markdown-code-background-color": scrim_lo,
        "code-editor-background-color": scrim_lo,
        "markdown-link-color": prim[50],

        # ---- misc -------------------------------------------------------------
        "ha-tooltip-background-color": scrim_hi,
        "ha-tooltip-text-color": fg,
        "ha-tab-indicator-color": prim[40],
        "ha-tab-track-color": hair,
        "chat-background-color-user": rgba(prim[40], 0.20),
        "chat-background-color-hass": scrim_lo,
        "scrollbar-thumb-color": rim,
        "label-badge-background-color": scrim_hi,
        "label-badge-text-color": fg,
        "md-list-container-color": "none",
    }
    return t


CARD_MOD = """\
ha-card {
  backdrop-filter: unset !important;
}
ha-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  z-index: -1;
  pointer-events: none;
  backdrop-filter: var(--ha-card-backdrop-filter);
  background: linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0) 42%);
}
:host(hui-heading-card) ha-card,
:host(mushroom-title-card) ha-card,
ha-card.text-only,
ha-card.type-custom-bubble-card {
  background: none !important;
  backdrop-filter: none !important;
  box-shadow: none !important;
}
:host(hui-heading-card) ha-card::before,
:host(mushroom-title-card) ha-card::before,
ha-card.text-only::before,
ha-card.type-custom-bubble-card::before {
  content: none !important;
}
.mdc-data-table { background: none !important; }
"""


def stringify(d: dict) -> dict:
    """HA's THEME_SCHEMA is {cv.string: cv.string}. A bare number silently
    invalidates the WHOLE theme and it vanishes from the picker."""
    return {k: (v if isinstance(v, str) else str(v)) for k, v in d.items()}


def build() -> int:
    cfg = yaml.safe_load(SRC.read_text(encoding="utf-8"))
    status = cfg["status"]
    use_card_mod = bool(cfg.get("card_mod"))
    written = []

    for v in cfg["variants"]:
        prim = ramp(v["brand"])
        nr, ng, nb = v["neutral_hue"]
        neut = ramp(rgb2hex(nr, ng, nb))

        theme = stringify(global_layer(v, status, prim, neut))
        theme["modes"] = {
            "light": stringify(mode_layer(v, "light", prim, neut)),
            "dark": stringify(mode_layer(v, "dark", prim, neut)),
        }
        if use_card_mod:
            theme["card-mod-theme"] = v["key"]
            theme["card-mod-card"] = CARD_MOD

        doc = {v["key"]: theme}
        out = THEMES / f"{v['key']}.yaml"
        header = (
            "# GENERATED - do not edit. Source: sources/glass.tokens.yaml\n"
            "# Rebuild: python3 scripts/build_glass_themes.py\n"
        )
        out.write_text(
            header + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True,
                                    default_flow_style=False, width=100000),
            encoding="utf-8",
        )
        written.append((out.name, len(theme) - 1))

    # ---- self-check ------------------------------------------------------
    problems = []
    dead = ("paper-", "mdc-")
    required = ("ha-color-primary-40", "wa-color-surface-default",
                "ha-card-backdrop-filter", "ha-bottom-sheet-surface-background",
                "ha-color-surface-default", "ha-color-focus")
    for name, _ in written:
        data = yaml.safe_load((THEMES / name).read_text(encoding="utf-8"))
        for key, body in data.items():
            flat = {k: v for k, v in body.items() if k != "modes"}
            for m in body.get("modes", {}).values():
                flat.update(m)
            for k, val in flat.items():
                if any(k.startswith(d) for d in dead):
                    problems.append(f"{name}: dead variable {k}")
                if not isinstance(val, str):
                    problems.append(f"{name}: non-string value for {k!r} -> {val!r}")
            for r in required:
                if r not in flat:
                    problems.append(f"{name}: missing required token {r}")
            if "modes" not in body:
                problems.append(f"{name}: no modes: block (dark semantic tokens won't load)")

    for name, n in written:
        print(f"wrote themes/{name}  ({n} global keys + light/dark modes)")
    if problems:
        print("\nSELF-CHECK FAILED:", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 1
    print("self-check OK")
    return 0


if __name__ == "__main__":
    sys.exit(build())
