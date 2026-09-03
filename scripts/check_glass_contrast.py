#!/usr/bin/env python3
"""Regression gate for glass-theme contrast on adversarial wallpapers.

Theme values may be opaque hex or rgba().  This checker composites each
foreground over the generated card/header material and representative light,
mid-tone, and dark photo pixels, then enforces WCAG 2 contrast requirements.
It deliberately checks the states users must *read* at a glance, not merely
whether the YAML schema parses.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Iterable

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
THEMES = (ROOT / "themes" / "VisionOS 26.yaml", ROOT / "themes" / "Liquid Glass 26.yaml")

# Warm interior photographs are an intentional stress case; the other two
# values make the test cover common shadow and bright-window regions.
BACKDROPS = ("#E8DDC8", "#8F7C65", "#3D2918")
TEXT_MIN = 4.5
GRAPHIC_MIN = 3.0
RGBA = re.compile(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)")


def parse_color(value: str) -> tuple[tuple[float, float, float], float]:
    value = value.strip()
    if value.startswith("#") and len(value) == 7:
        return tuple(int(value[i : i + 2], 16) for i in (1, 3, 5)), 1.0
    match = RGBA.fullmatch(value)
    if match:
        r, g, b, alpha = match.groups()
        return (float(r), float(g), float(b)), float(alpha or 1)
    raise ValueError(f"Unsupported colour syntax: {value!r}")


def composite(value: str, background: tuple[float, float, float]) -> tuple[float, float, float]:
    color, alpha = parse_color(value)
    return tuple(component * alpha + below * (1 - alpha) for component, below in zip(color, background))


def luminance(color: tuple[float, float, float]) -> float:
    linear = []
    for channel in color:
        value = channel / 255
        linear.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return (max(luminance(a), luminance(b)) + 0.05) / (min(luminance(a), luminance(b)) + 0.05)


def checks(tokens: dict[str, str], material: str, label: str) -> Iterable[tuple[str, str, float]]:
    text = ("ha-color-text-primary", "ha-color-text-secondary")
    graphics = (
        "state-icon-color",
        "tile-icon-color",
        "state-inactive-color",
        "state-icon-unavailable-color",
        "state-icon-active-color",
    )
    for backdrop in BACKDROPS:
        base = composite(backdrop, (0, 0, 0))
        surface = composite(material, base)
        for key in text:
            yield backdrop, key, contrast(composite(tokens[key], surface), surface) / TEXT_MIN
        for key in graphics:
            yield backdrop, key, contrast(composite(tokens[key], surface), surface) / GRAPHIC_MIN
        track = composite(tokens["switch-unchecked-track-color"], surface)
        yield backdrop, "switch-unchecked-track-color", contrast(track, surface) / GRAPHIC_MIN
        thumb = composite(tokens["switch-unchecked-button-color"], track)
        yield backdrop, "switch-unchecked-button-color", contrast(thumb, track) / GRAPHIC_MIN


def main() -> int:
    failures: list[str] = []
    for path in THEMES:
        theme = yaml.safe_load(path.read_text(encoding="utf-8"))
        name, values = next(iter(theme.items()))
        for mode, tokens in values["modes"].items():
            header = tokens["app-header-background-color"]
            if header == "transparent":
                failures.append(f"{name}/{mode}: app-header-background-color must be a material, not transparent")
            for backdrop, key, normalized in checks(tokens, tokens["ha-card-background"], f"{name}/{mode}"):
                if normalized < 1:
                    failures.append(
                        f"{name}/{mode} on {backdrop}: {key} is {normalized * (TEXT_MIN if key.startswith('ha-color-text') else GRAPHIC_MIN):.2f}:1"
                    )
    if failures:
        print("glass contrast check FAILED:")
        print("\n".join(f"- {failure}" for failure in failures))
        return 1
    print("glass contrast check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
