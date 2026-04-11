# Woow Theme for Home Assistant

A clean, professional Home Assistant theme by [WOOWTECH](https://github.com/WOOWTECH) with light and dark mode support.

## Features

- Light and dark mode (auto-switches based on system preference)
- Carefully tuned color palette for readability and aesthetics
- Rounded card styling with subtle shadows
- Optimized for CJK (Traditional Chinese) typography
- Compatible with HACS

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to **Frontend** > click the 3-dot menu > **Custom repositories**
3. Add `https://github.com/WOOWTECH/Woow_ha_theme` with category **Theme**
4. Search for "Woow Theme" and install

### Manual

1. Copy `themes/woow.yaml` into your Home Assistant `config/themes/` directory
2. Ensure your `configuration.yaml` includes:

```yaml
frontend:
  themes: !include_dir_merge_named themes
```

3. Restart Home Assistant

## Activation

1. Go to your **User Profile** (click your name in the sidebar)
2. Under **Theme**, select **Woow**
3. Choose light or dark mode, or leave on **Auto**

## Color Palette

| Role | Light | Dark |
|------|-------|------|
| Primary | `#3d8ef0` | `#5aa0f5` |
| Accent | `#f0b830` | `#f0b830` |
| Background | `#f5f6fa` | `#111318` |
| Card | `#ffffff` | `#1e2028` |
| Text | `#1a1c20` | `#e8eaef` |

## License

MIT
