#!/usr/bin/env python3
"""Expand sources/glass.tokens.yaml into full HA-2026 theme YAML files.

Why a generator: since the 2025->2026 frontend migration (Polymer/Paper ->
Web Awesome) a theme has to satisfy four token layers that are mostly
mechanical derivations of ~40 real design decisions:

    --ha-color-* / --ha-border-radius-* / --ha-font-*   source of truth
        -> --wa-*                                Web Awesome consumption layer
        -> legacy --primary-color / --ha-card-*  compatibility layer
        -> --mdc-* residue                       (dead; deliberately not emitted)

Hand-maintaining ~300 keys per theme is how themes rot. Edit the tokens file,
run this, commit the output.

    python3 scripts/build_glass_themes.py

The self-check at the bottom enforces the layer discipline documented in the
tokens file. The rule it exists to protect: variables Home Assistant consumes
as `background-color:` MUST be opaque. A gradient there is invalid CSS and is
dropped silently, which makes entire pages transparent; a low-alpha rgba there
makes the sidebar drawer and settings panels see-through onto the dashboard.
"""
from __future__ import annotations

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "sources" / "glass.tokens.yaml"
THEMES = ROOT / "themes"

RAMP_STEPS = [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95]

# Variables Home Assistant assigns to `background-color:`. Anything here that
# is not a fully opaque colour makes a whole surface see-through. This list is
# the thing the self-check guards.
MUST_BE_OPAQUE = (
    "primary-background-color",
    "secondary-background-color",
    "card-background-color",
    "material-background-color",
    "sidebar-background-color",
    "table-row-alternative-background-color",
)


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


def mix(a: str, b: str, t: float) -> str:
    """Blend two opaque hex colours. Used to build ramps that stay opaque."""
    ar, ag, ab = hex2rgb(a)
    br, bg, bb = hex2rgb(b)
    return rgb2hex(ar + (br - ar) * t, ag + (bg - ag) * t, ab + (bb - ab) * t)


def ramp(base_hex: str) -> dict[int, str]:
    """11-step ramp with step 40 == the brand colour.

    HA only auto-generates the OKLCH palette for the built-in default theme, so
    a custom theme MUST emit its own ramp or every Web Awesome button, switch
    and focus ring stays HA cyan. Blending toward near-black / near-white in
    sRGB keeps the hue stable, which matters more here than perceptual spacing.
    """
    out: dict[int, str] = {}
    for step in RAMP_STEPS:
        if step == 40:
            out[step] = base_hex.lower()
        elif step < 40:
            out[step] = mix("#0b0b0c", base_hex, (step - 5) / 35 * 0.92 + 0.08)
        else:
            out[step] = mix(base_hex, "#fbfbfd", (step - 40) / 55 * 0.94)
    return out


def rgba(hex_or_rgba: str, alpha: float) -> str:
    if hex_or_rgba.startswith("rgb"):
        return hex_or_rgba
    r, g, b = hex2rgb(hex_or_rgba)
    return f"rgba({r}, {g}, {b}, {alpha})"


def is_opaque(value: str) -> bool:
    v = value.strip().lower()
    if v in ("transparent", "none"):
        return False
    if v.startswith("linear-gradient") or v.startswith("radial-gradient"):
        return False       # invalid as a background-color -> dropped -> see-through
    if v.startswith("rgba("):
        alpha = v.rstrip(")").split(",")[-1].strip()
        try:
            return float(alpha) >= 0.999
        except ValueError:
            return False
    if v.startswith("#"):
        return len(v.lstrip("#")) in (3, 6)   # #rrggbbaa would carry alpha
    return v.startswith("rgb(") or v.startswith("var(")


# --------------------------------------------------------------------------
# layer builders
# --------------------------------------------------------------------------
# Apple's systemGray ramps, dark set and light set concatenated into one
# monotonic dark->light scale. Exactly 11 stops for HA's 11 ramp steps.
APPLE_NEUTRALS = ["#1C1C1E", "#2C2C2E", "#3A3A3C", "#48484A", "#636366",
                  "#8E8E93", "#AEAEB2", "#C7C7CC", "#D1D1D6", "#E5E5EA", "#F2F2F7"]


def global_layer(cfg: dict, v: dict, prim_l: dict, prim_d: dict) -> dict:
    """Mode-independent tokens: geometry, typography, blur, neutral ramp."""
    r = v["radius"]
    card, dialog, sheet, pad = r["card"], r["dialog"], r["sheet"], r["inner_padding"]
    filt = f"blur({cfg['blur']}) saturate({cfg['saturate']})"
    # Apple's concentricity rule (WWDC23 10076): inner radius + padding = outer.
    # Nesting equal radii is one of the loudest non-Apple tells.
    inner = max(4, card - pad)

    t: dict[str, str] = {}

    # HA's neutral ramp is mode-independent and must run dark -> light.
    for step, hexv in zip(RAMP_STEPS, APPLE_NEUTRALS):
        t[f"ha-color-neutral-{step:02d}"] = hexv
    # ha-toast lives outside some view-theme scopes. These mode-independent
    # values must therefore exist at the root as well as in each mode.
    t["ha-color-on-neutral-loud"] = "#FFFFFF"
    t["wa-color-neutral-on-loud"] = "#FFFFFF"

    # ---- typography ------------------------------------------------------
    # -apple-system resolves to SF UI on Apple platforms. Apple differentiates
    # headline from body by WEIGHT at the same size, not by size.
    t["ha-font-family-body"] = cfg["font_stack"]
    t["ha-font-family-heading"] = cfg["font_stack"]
    t["ha-font-size-scale"] = "0.85"
    t["ha-font-weight-heading"] = "700"
    t["ha-font-weight-action"] = "600"
    t["ha-line-height-normal"] = "1.29"      # 22/17, Apple body

    # ---- geometry --------------------------------------------------------
    t["ha-border-radius-sm"] = "6px"
    t["ha-border-radius-md"] = "10px"        # Apple grouped list card
    t["ha-border-radius-lg"] = f"{inner}px"
    t["ha-border-radius-xl"] = f"{card - 4}px"
    t["ha-border-radius-2xl"] = f"{card}px"
    t["ha-border-radius-3xl"] = f"{sheet}px"
    t["ha-card-border-radius"] = f"{card}px"
    t["ha-badge-border-radius"] = "9999px"   # Apple badges are capsules
    t["ha-section-border-radius"] = f"{card}px"
    t["ha-tile-icon-border-radius"] = f"{inner}px"
    t["tile-icon-border-radius"] = f"{inner}px"
    t["ha-card-features-border-radius"] = f"{inner}px"
    t["feature-border-radius"] = f"{inner}px"
    t["ha-dialog-border-radius"] = f"{dialog}px"
    t["ha-bottom-sheet-border-radius"] = f"{sheet}px"
    # iOS 26's default control shape is a Capsule.
    t["ha-button-border-radius"] = "9999px"
    t["wa-border-radius-pill"] = "9999px"
    t["ha-checkbox-border-radius"] = "6px"
    t["ha-tooltip-border-radius"] = "10px"
    t["wa-panel-border-radius"] = f"{card}px"
    t["wa-border-radius-l"] = f"{inner}px"
    t["wa-form-control-border-radius"] = "10px"

    # ---- compact layout: 85% of HA's section/card geometry ---------------
    # Scale the spacing tokens used for card padding together with typography
    # so text-to-edge proportions remain stable. Larger control-size tokens
    # stay untouched to preserve the 44px HIG tap-target floor.
    for step in range(1, 9):
        t[f"ha-space-{step}"] = f"{step * 3.4:g}px"
    # 56px rows -> 48px, 500/320px columns -> 425/272px.
    t["ha-card-feature-gap"] = "7px"
    t["ha-view-sections-column-gap"] = "14px"
    t["ha-view-sections-row-gap"] = "14px"
    t["ha-view-sections-narrow-column-gap"] = "7px"
    t["ha-view-sections-row-height"] = "48px"
    t["ha-view-sections-column-max-width"] = "425px"
    t["ha-view-sections-column-min-width"] = "272px"
    t["ha-section-grid-column-gap"] = "10px"
    t["ha-section-grid-row-gap"] = "10px"
    t["ha-section-grid-row-height"] = "48px"

    # ---- control metrics: UISwitch is 51x31pt with a 27pt thumb ----------
    t["ha-switch-width"] = "51px"
    t["ha-switch-size"] = "31px"
    t["ha-switch-thumb-size"] = "27px"
    t["ha-checkbox-size"] = "22px"
    t["ha-button-height"] = "44px"           # HIG minimum tap target
    t["wa-form-control-height"] = "44px"

    # ---- blur: 20px + saturate 180%, the values apple.com itself uses ----
    t["ha-card-backdrop-filter"] = filt
    t["app-header-backdrop-filter"] = filt
    t["ha-dialog-surface-backdrop-filter"] = filt
    t["ha-bottom-sheet-surface-backdrop-filter"] = filt
    t["dialog-backdrop-filter"] = filt
    # Apple dims rather than blurs hard behind sheets.
    t["ha-dialog-scrim-backdrop-filter"] = "blur(4px) brightness(55%)"
    t["ha-bottom-sheet-scrim-backdrop-filter"] = "blur(4px) brightness(55%)"
    # The rim light lives in box-shadow (see mode_layer), not in a border.
    t["ha-card-border-width"] = "0"

    return t


def mode_layer(cfg: dict, v: dict, mode: str) -> dict:
    ink = cfg["ink"][mode]
    grays = cfg["grays"][mode]
    # Navigation remains glass. Content cards use thick material so a busy
    # wallpaper cannot erase state, text, or control affordances beneath it.
    nav_material = cfg["materials"][mode]["regular"]
    content_material = cfg["materials"][mode]["content"]
    card_brightness = "190%" if mode == "light" else "38%"
    card_filter = (f"blur({cfg['blur']}) saturate({cfg['saturate']}) "
                   f"brightness({card_brightness})")
    thick = cfg["materials"][mode]["thick"]
    wp = v["wallpaper"][mode]
    page, surface, elevated = v["page"][mode], v["surface"][mode], v["elevated"][mode]
    brand = v["brand"][mode]
    prim = ramp(brand)
    light = mode == "light"
    # Keep the Apple system colour in the exported palette, but use a darker
    # ramp stop for light-mode interactive UI where system orange/blue on a
    # near-white material does not meet the 3:1 graphical-contrast floor.
    ui_brand = prim[10] if light else prim[80]
    brand_hover = prim[5] if light else prim[90]
    brand_active = prim[5] if light else prim[95]
    state_icon = "#2C2C2E" if light else "#E5E5EA"
    # Off remains neutral; unavailable is an accessible fault colour, rather
    # than the same faint grey used for an intentionally disabled control.
    unavailable_icon = "#650B0B" if light else "#FFC7C2"
    off_track = "#2C2C2E" if light else "#E5E5EA"
    off_thumb = "#FFFFFF" if light else "#1C1C1E"
    control_fill = "#E5E5EA" if light else "#48484A"
    control_hover = "#D1D1D6" if light else "#636366"
    # HA 2026.7's toast uses neutral-10 (always dark) plus this on-loud
    # role. Keep the entire loud-neutral pairing dark-on-light independent.
    neutral_loud = "#3A3A3C"
    neutral_on_loud = "#FFFFFF"

    fg, fg2, fg3 = ink["primary"], ink["secondary"], ink["tertiary"]
    sep, fill1, fill2, fill3 = ink["separator"], ink["fill1"], ink["fill2"], ink["fill3"]
    gray, gray2, gray3 = grays[0], grays[1], grays[2]

    # Apple's glass: a bright specular top edge, a faint bottom bounce, and a
    # wide low-opacity grounding shadow. A uniform 1px border reads as a
    # sticker; asymmetric inset highlights read as lit glass.
    if light:
        rim_hi, rim_lo = "rgba(255,255,255,0.75)", "rgba(255,255,255,0.20)"
        drop = "0 8px 32px rgba(0,0,0,0.10)"
        on_brand = "#ffffff"
    else:
        rim_hi, rim_lo = "rgba(255,255,255,0.22)", "rgba(255,255,255,0.06)"
        drop = "0 8px 32px rgba(0,0,0,0.34)"
        on_brand = "#1C1C1E"
    glass_shadow = f"inset 0 1px 0 {rim_hi}, inset 0 -1px 0 {rim_lo}, {drop}"

    # Wallpaper: gradient underneath as the always-paints fallback (HACS does
    # not install www/), image on top. This is the ONLY place the image goes.
    # A mild overlay normalises bright windows/deep shadows so transparent
    # heading cards retain readable ink without flattening the photograph.
    overlay = "rgba(255,255,255,0.20)" if light else "rgba(0,0,0,0.24)"
    wallpaper = (f"linear-gradient({overlay}, {overlay}), "
                 f"center / cover no-repeat fixed url('{wp['image']}'), {wp['gradient']}")

    t: dict[str, str] = {
        # ---- OPAQUE layer. Never translucent, never a gradient. -----------
        "primary-background-color": page,
        "secondary-background-color": surface,
        "card-background-color": surface,
        "material-background-color": surface,
        "sidebar-background-color": surface,
        "table-row-alternative-background-color": mix(surface, gray, 0.06),
        "mdc-theme-surface": surface,

        # ---- WALLPAPER layer: dashboard views only ------------------------
        "lovelace-background": wallpaper,
        "background-image": wallpaper,

        # ---- GLASS layer --------------------------------------------------
        "ha-card-background": content_material,
        "clear-background-color": content_material,
        "ha-card-backdrop-filter": card_filter,
        "app-header-background-color": nav_material,
        "ha-dialog-surface-background": thick,
        "ha-bottom-sheet-surface-background": thick,
        "ha-bottom-sheet-handle-color": fg3,
        "ha-card-box-shadow": glass_shadow,
        "dialog-box-shadow": glass_shadow,

        # ---- ink ----------------------------------------------------------
        "ha-color-text-primary": fg,
        "ha-color-text-secondary": fg2,
        "ha-color-text-disabled": fg3,
        "ha-color-text-link": ui_brand,
        "primary-text-color": fg,
        "secondary-text-color": fg2,
        "disabled-text-color": fg3,
        "text-primary-color": fg,
        "text-dark-color": fg,
        "rgb-primary-text-color": "0, 0, 0" if light else "255, 255, 255",
        "lumo-body-text-color": fg,

        # ---- semantic surfaces (new in 2026, unstyled by pre-2026 themes) -
        "ha-color-surface-default": surface,
        "ha-color-surface-low": page,
        "ha-color-surface-lower": mix(page, gray, 0.12) if light else "#000000",
        "ha-color-on-surface-default": fg,
        "ha-color-form-background": control_fill,
        "ha-color-form-hover": control_hover,
        "ha-color-form-disabled": control_fill,

        # ---- separators: Apple's hairline, its own base colour ------------
        "divider-color": sep,
        "outline-color": sep,
        "outline-hover-color": fg3,
        "ha-color-border-neutral-quiet": sep,
        "ha-color-border-neutral-normal": sep,
        "ha-color-border-neutral-loud": fg2,
        "ha-color-border-primary-quiet": rgba(ui_brand, 0.25),
        "ha-color-border-primary-normal": ui_brand,

        # ---- fills: Apple systemFill greys, translucent so they integrate -
        "ha-color-fill-neutral-quiet-resting": fill3,
        "ha-color-fill-neutral-quiet-hover": fill2,
        "ha-color-fill-neutral-quiet-active": fill1,
        "ha-color-fill-neutral-normal-resting": fill2,
        "ha-color-fill-neutral-normal-hover": fill1,
        "ha-color-fill-neutral-loud-resting": neutral_loud,
        "ha-color-fill-primary-quiet-resting": rgba(ui_brand, 0.14),
        "ha-color-fill-primary-quiet-hover": rgba(ui_brand, 0.22),
        "ha-color-fill-primary-quiet-active": rgba(ui_brand, 0.28),
        "ha-color-fill-primary-normal-resting": ui_brand,
        "ha-color-fill-primary-normal-hover": brand_hover,
        "ha-color-fill-primary-normal-active": brand_active,
        "ha-color-fill-primary-loud-resting": ui_brand,
        "ha-color-fill-primary-loud-hover": brand_hover,
        "ha-color-fill-primary-loud-active": brand_active,
        "ha-color-fill-disabled-quiet-resting": fill3,
        "ha-color-fill-disabled-normal-resting": fill3,
        "ha-color-on-neutral-quiet": fg,
        "ha-color-on-neutral-normal": fg,
        "ha-color-on-neutral-loud": neutral_on_loud,
        # On a light backdrop a brand-coloured label on a brand-tinted fill
        # needs the darker ramp step (orange on light orange especially).
        "ha-color-on-primary-quiet": ui_brand,
        "ha-color-on-primary-normal": on_brand,
        "ha-color-on-primary-loud": on_brand,
        "ha-color-on-disabled-quiet": fg3,
        "ha-color-on-disabled-normal": fg3,

        # ---- Web Awesome bridge (the layer 2024-era themes miss entirely) --
        "wa-color-brand-fill-loud": ui_brand,
        "wa-color-brand-fill-normal": rgba(ui_brand, 0.16),
        "wa-color-brand-fill-quiet": rgba(ui_brand, 0.10),
        "wa-color-brand-border-loud": ui_brand,
        "wa-color-brand-border-normal": rgba(ui_brand, 0.45),
        "wa-color-brand-border-quiet": rgba(ui_brand, 0.22),
        "wa-color-brand-on-loud": on_brand,
        "wa-color-brand-on-normal": ui_brand,
        "wa-color-brand-on-quiet": ui_brand,
        "wa-color-neutral-fill-loud": neutral_loud,
        "wa-color-neutral-fill-normal": fill2,
        "wa-color-neutral-fill-quiet": fill3,
        "wa-color-neutral-border-loud": fg2,
        "wa-color-neutral-border-normal": sep,
        "wa-color-neutral-border-quiet": sep,
        "wa-color-neutral-on-loud": neutral_on_loud,
        "wa-color-neutral-on-normal": fg,
        "wa-color-neutral-on-quiet": fg,
        "wa-color-text-normal": fg,
        "wa-color-text-quiet": fg2,
        "wa-color-surface-default": surface,
        "wa-color-surface-raised": elevated,
        "wa-color-surface-border": sep,
        "wa-form-control-background-color": control_fill,
        "wa-form-control-border-color": sep,
        "wa-form-control-value-color": fg,
        "wa-form-control-placeholder-color": fg3,

        # ---- sidebar (--sidebar-selected-text-color is DEAD in 2026) ------
        "sidebar-text-color": fg2,
        "sidebar-icon-color": fg2,
        "sidebar-selected-icon-color": ui_brand,
        "sidebar-menu-button-background-color": "transparent",
        "sidebar-menu-button-text-color": fg,

        # ---- states / icons ------------------------------------------------
        "state-icon-color": state_icon,
        "state-icon-active-color": ui_brand,
        "state-icon-unavailable-color": unavailable_icon,
        "state-unavailable-color": unavailable_icon,
        "state-inactive-color": state_icon,
        # Explicit domain/state entries outrank the generic fallback in
        # stateColorCss. Keep these even though current HA falls back cleanly:
        # they protect against stale/default domain variables and card-specific
        # resolution paths.
        "state-light-off-color": state_icon,
        "state-light-inactive-color": state_icon,
        "state-switch-off-color": state_icon,
        "state-switch-inactive-color": state_icon,
        "state-climate-off-color": state_icon,
        "state-climate-inactive-color": state_icon,

        # ---- tiles / headings ----------------------------------------------
        "ha-tile-info-primary-color": fg,
        "ha-tile-info-secondary-color": fg2,
        "tile-icon-color": state_icon,
        "ha-heading-card-title-color": fg,
        "ha-heading-card-subtitle-color": fg2,

        # ---- inputs ---------------------------------------------------------
        "input-ink-color": fg,
        "input-fill-color": control_fill,
        "input-disabled-fill-color": control_fill,
        "input-label-ink-color": fg2,
        "input-disabled-ink-color": fg3,
        "input-dropdown-icon-color": fg2,
        "input-idle-line-color": sep,
        "input-hover-line-color": fg3,

        # ---- switches / sliders ---------------------------------------------
        "switch-checked-track-color": ui_brand,
        "switch-checked-button-color": on_brand,
        "switch-unchecked-track-color": off_track,
        "switch-unchecked-button-color": off_thumb,
        "ha-switch-checked-background-color": ui_brand,
        "ha-switch-checked-thumb-color": on_brand,
        "ha-checkbox-checked-background-color": ui_brand,
        "ha-checkbox-checked-icon-color": on_brand,
        "ha-checkbox-border-color": off_track,
        "slider-color": ui_brand,
        "slider-secondary-color": fill2,
        "slider-track-color": fill1,

        # ---- tables / code ---------------------------------------------------
        "table-row-background-color": surface,
        "data-table-background-color": surface,
        "markdown-code-background-color": fill3,
        "code-editor-background-color": fill3,
        "markdown-link-color": ui_brand,

        # ---- misc -------------------------------------------------------------
        "ha-tooltip-background-color": elevated,
        "ha-tooltip-text-color": fg,
        "ha-tab-indicator-color": ui_brand,
        "ha-tab-track-color": sep,
        "chat-background-color-user": rgba(ui_brand, 0.16),
        "chat-background-color-hass": fill3,
        "scrollbar-thumb-color": fg3,
        "label-badge-background-color": elevated,
        "label-badge-text-color": fg,
        "md-list-container-color": "none",

        # ---- brand + Apple system palette, per appearance -------------------
        "primary-color": ui_brand,
        "accent-color": ui_brand,
        "rgb-primary-color": ", ".join(str(c) for c in hex2rgb(ui_brand)),
        "app-theme-color": page,
        "ha-color-focus": ui_brand,
        "wa-focus-ring-color": ui_brand,
    }

    for step in RAMP_STEPS:
        t[f"ha-color-primary-{step:02d}"] = prim[step]
    for name, pair in cfg["status"].items():
        t[f"{name}-color"] = pair[mode]
    for label, key in (("error", "red"), ("warning", "orange"),
                       ("success", "green"), ("info", "blue")):
        t[f"{label}-color"] = cfg["status"][key][mode]
        t[f"rgb-{label}-color"] = ", ".join(str(c) for c in hex2rgb(cfg["status"][key][mode]))
    return t


CARD_MOD = """\
ha-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  z-index: 0;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(255,255,255,0.18), rgba(255,255,255,0) 38%);
}
:host(hui-heading-card) ha-card,
ha-card.text-only {
  background: none !important;
  backdrop-filter: none !important;
  box-shadow: none !important;
}
"""


def stringify(d: dict) -> dict:
    """HA's THEME_SCHEMA is {cv.string: cv.string}. A bare number silently
    invalidates the WHOLE theme and it vanishes from the picker."""
    return {k: (v if isinstance(v, str) else str(v)) for k, v in d.items()}


def build() -> int:
    cfg = yaml.safe_load(SRC.read_text(encoding="utf-8"))
    written = []

    for v in cfg["variants"]:
        prim_l, prim_d = ramp(v["brand"]["light"]), ramp(v["brand"]["dark"])
        theme = stringify(global_layer(cfg, v, prim_l, prim_d))
        theme["modes"] = {
            "light": stringify(mode_layer(cfg, v, "light")),
            "dark": stringify(mode_layer(cfg, v, "dark")),
        }
        if cfg.get("card_mod"):
            theme["card-mod-theme"] = v["key"]
            theme["card-mod-card"] = CARD_MOD

        out = THEMES / f"{v['key']}.yaml"
        header = ("# GENERATED - do not edit. Source: sources/glass.tokens.yaml\n"
                  "# Rebuild: python3 scripts/build_glass_themes.py\n")
        out.write_text(
            header + yaml.safe_dump({v["key"]: theme}, sort_keys=False,
                                    allow_unicode=True, default_flow_style=False,
                                    width=100000),
            encoding="utf-8")
        written.append((out.name, len(theme) - 1))

    # ---- self-check ------------------------------------------------------
    problems = []
    dead = ("paper-",)
    required = ("ha-color-primary-40", "wa-color-surface-default",
                "ha-card-backdrop-filter", "ha-bottom-sheet-surface-background",
                "ha-color-surface-default", "ha-color-focus", "ha-font-family-body")
    for name, _ in written:
        data = yaml.safe_load((THEMES / name).read_text(encoding="utf-8"))
        for _key, body in data.items():
            flat = {k: val for k, val in body.items() if k != "modes"}
            modes = body.get("modes", {})
            for m in modes.values():
                flat.update(m)
            for k, val in flat.items():
                if any(k.startswith(d) for d in dead):
                    problems.append(f"{name}: dead variable {k}")
                if not isinstance(val, str):
                    problems.append(f"{name}: non-string value for {k!r} -> {val!r}")
            for r in required:
                if r not in flat:
                    problems.append(f"{name}: missing required token {r}")
            if not modes:
                problems.append(f"{name}: no modes: block (dark tokens won't load)")
            # THE layer-discipline check: see the module docstring.
            for mode_name, m in modes.items():
                for k in MUST_BE_OPAQUE:
                    if k not in m:
                        problems.append(f"{name}[{mode_name}]: {k} not set")
                    elif not is_opaque(m[k]):
                        problems.append(
                            f"{name}[{mode_name}]: {k} = {m[k]!r} is not opaque "
                            f"-- HA uses it as background-color, so this makes a "
                            f"whole surface see-through")

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
