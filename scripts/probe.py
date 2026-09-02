#!/usr/bin/env python3
"""Offline visual probe for HA themes.

Renders a static page that reproduces the CSS-variable consumption chains
Home Assistant 2026 actually uses (ha-card, ha-badge, tile, bottom sheet,
dialog, Web Awesome buttons/switches/inputs, sidebar, sections gutters),
applies a theme exactly the way apply_themes_on_element.ts does (every key
becomes an inline --key on the root, plus an auto --rgb-key companion for
hex values), and screenshots it with Chromium.

    python3 scripts/probe.py "themes/VisionOS 26.yaml"

Catches roughly the colour/contrast/geometry class of bugs without touching
a real Home Assistant. It is NOT a substitute for a real-instance check --
shadow-DOM behaviour and card-mod are not simulated.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "probe"


def hex2rgb(h: str):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def flatten(theme: dict, mode: str) -> dict:
    out = {k: v for k, v in theme.items() if k not in ("modes", "card-mod-card", "card-mod-theme")}
    out.update(theme.get("modes", {}).get(mode, {}))
    # HA auto-derives --rgb-<key> for any value starting with '#'
    for k, v in list(out.items()):
        if isinstance(v, str) and v.startswith("#") and f"rgb-{k}" not in out:
            out[f"rgb-{k}"] = ", ".join(str(c) for c in hex2rgb(v))
    return out


PAGE = """<!doctype html><html><head><meta charset=utf-8><style>
* { box-sizing: border-box; }
html { min-height:100%; background: var(--lovelace-background, var(--primary-background-color)); }
html, body { margin:0; }
body { min-height:100vh; }
body {
  font: 14px/1.6 Roboto, Noto, sans-serif;
  color: var(--primary-text-color);
  background: var(--lovelace-background, var(--primary-background-color));
  display: flex;
}
/* --- sidebar --------------------------------------------------------- */
.sidebar {
  width: 256px; flex: none; padding: 12px 8px;
  background: var(--sidebar-background-color);
  color: var(--sidebar-text-color);
  border-right: 1px solid var(--divider-color);
}
/* Mobile drawer: sidebar OVER content. If sidebar-background-color is not
   opaque, the page behind bleeds through and text collides. */
.drawer-test { position: relative; height: 260px; overflow: hidden;
  border-radius: var(--ha-card-border-radius); margin-top: 8px;
  border: 1px solid var(--divider-color); }
.drawer-test .behind { position: absolute; inset: 0; padding: 16px;
  background: var(--primary-background-color); }
.drawer-test .drawer { position: absolute; inset: 0 40% 0 0; padding: 12px 8px;
  background: var(--sidebar-background-color); color: var(--sidebar-text-color); }
/* Settings page: opaque page + opaque cards, NO wallpaper. */
.settings { background: var(--primary-background-color); padding: 16px;
  border-radius: var(--ha-card-border-radius); margin-top: 8px;
  border: 1px solid var(--divider-color); }
.settings .panel { background: var(--card-background-color); padding: 16px;
  border-radius: var(--ha-border-radius-md, 10px); }
.sidebar .item { display:flex; gap:12px; align-items:center; padding:10px 12px;
  border-radius: var(--ha-card-border-radius); }
.sidebar .item.sel { background: var(--ha-color-fill-primary-quiet-resting);
  color: var(--sidebar-selected-icon-color); }
.dot { width:20px;height:20px;border-radius:50%;background:currentColor;opacity:.75 }
/* --- main ------------------------------------------------------------ */
.main { flex:1; min-width:0; padding: 0 0 40px; }
.hdr { height:56px; display:flex; align-items:center; padding:0 20px; gap:16px;
  background: var(--app-header-background-color);
  backdrop-filter: var(--app-header-backdrop-filter);
  border-bottom: 1px solid var(--divider-color); font-weight:500; }
.wrap { padding: 20px; }
h2 { font-size:20px; margin: 26px 0 10px; font-weight:700; }
.sub { color: var(--secondary-text-color); font-size:13px; }
.sections { display:grid; grid-template-columns:1fr 1fr;
  gap: var(--ha-view-sections-column-gap, 16px); }
.grid { display:grid; grid-template-columns:1fr 1fr;
  gap: var(--ha-section-grid-column-gap, 12px); }
/* --- ha-card / ha-badge (same vars, per ha-card.ts + ha-badge.ts) ----- */
.card, .badge {
  background: var(--ha-card-background, var(--card-background-color));
  border: var(--ha-card-border-width) solid var(--ha-card-border-color);
  border-radius: var(--ha-card-border-radius);
  box-shadow: var(--ha-card-box-shadow);
  backdrop-filter: var(--ha-card-backdrop-filter);
  -webkit-backdrop-filter: var(--ha-card-backdrop-filter);
}
.card { padding:16px; }
.badge { display:inline-flex; gap:8px; align-items:center; height:36px;
  padding:0 14px; border-radius: var(--ha-badge-border-radius); margin:0 8px 8px 0; }
/* --- tile card ------------------------------------------------------- */
.tile { display:flex; gap:12px; align-items:center; padding:12px; }
.tile .ic { width:40px;height:40px;flex:none;display:grid;place-items:center;
  border-radius: var(--ha-tile-icon-border-radius);
  background: var(--ha-color-fill-primary-quiet-resting);
  color: var(--state-icon-active-color); }
.tile .ic.off { background: var(--ha-color-fill-neutral-quiet-resting);
  color: var(--state-icon-color); }
.tile b { display:block; font-weight:500; color: var(--ha-tile-info-primary-color); }
.tile span { color: var(--ha-tile-info-secondary-color); font-size:12px; }
/* --- buttons (Web Awesome layer) ------------------------------------- */
.btn { height:40px;padding:0 20px;border-radius: var(--ha-button-border-radius);
  border:1px solid transparent; font:inherit; font-weight:500; cursor:pointer; }
.btn.loud { background: var(--wa-color-brand-fill-loud); color: var(--wa-color-brand-on-loud); }
.btn.normal { background: var(--wa-color-brand-fill-normal); color: var(--wa-color-brand-on-normal);
  border-color: var(--wa-color-brand-border-normal); }
.btn.quiet { background: var(--wa-color-neutral-fill-quiet); color: var(--wa-color-neutral-on-quiet);
  border-color: var(--wa-color-neutral-border-quiet); }
.btn.danger { background: var(--error-color); color:#fff; }
input.f { height:40px; width:100%; padding:0 14px; font:inherit;
  border-radius: var(--wa-form-control-border-radius);
  background: var(--wa-form-control-background-color);
  border:1px solid var(--wa-form-control-border-color);
  color: var(--wa-form-control-value-color); }
input.f::placeholder { color: var(--wa-form-control-placeholder-color); }
/* --- switch / checkbox ----------------------------------------------- */
.sw { width:44px;height:26px;border-radius:999px;position:relative;flex:none;
  background: var(--switch-unchecked-track-color); }
.sw.on { background: var(--ha-switch-checked-background-color); }
.sw::after{content:'';position:absolute;top:3px;left:3px;width:20px;height:20px;
  border-radius:50%;background: var(--switch-checked-button-color);}
.sw.on::after{left:21px}
.cb { width:20px;height:20px;flex:none;border-radius: var(--ha-checkbox-border-radius);
  border:2px solid var(--ha-checkbox-border-color); }
.cb.on { background: var(--ha-checkbox-checked-background-color); border-color:transparent;
  color: var(--ha-checkbox-checked-icon-color); display:grid;place-items:center;font-size:13px }
/* --- dialog + bottom sheet ------------------------------------------- */
.scrim { border-radius:20px; padding:26px; margin-top:8px;
  backdrop-filter: var(--ha-dialog-scrim-backdrop-filter);
  background: rgba(0,0,0,.12); }
.dialog { max-width:420px; padding:20px;
  border-radius: var(--ha-dialog-border-radius);
  background: var(--ha-dialog-surface-background);
  backdrop-filter: var(--ha-dialog-surface-backdrop-filter);
  border:1px solid var(--ha-card-border-color);
  box-shadow: var(--ha-card-box-shadow); }
.sheet { max-width:380px; margin-top:14px; padding:18px;
  border-radius: var(--ha-bottom-sheet-border-radius) var(--ha-bottom-sheet-border-radius) 0 0;
  background: var(--ha-bottom-sheet-surface-background);
  backdrop-filter: var(--ha-bottom-sheet-surface-backdrop-filter);
  border:1px solid var(--ha-card-border-color); border-bottom:none; }
.handle { width:44px;height:5px;border-radius:3px;margin:0 auto 14px;
  background: var(--ha-bottom-sheet-handle-color); }
.row { display:flex; align-items:center; gap:12px; }
.sp { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
.swatch { width:34px;height:34px;border-radius:8px; }
code { background: var(--markdown-code-background-color); padding:2px 6px; border-radius:5px; }
a { color: var(--markdown-link-color); }
</style></head><body>
<div class=sidebar>
  <div class="item sel"><i class=dot></i>Overview</div>
  <div class=item><i class=dot></i>Energy</div>
  <div class=item><i class=dot></i>History</div>
  <div class=item><i class=dot></i>Developer tools</div>
</div>
<div class=main>
  <div class=hdr>Home &nbsp;<span class=sub>Living room · Kitchen · Garage</span></div>
  <div class=wrap>

  <div class=sections>
    <div>
      <h2>Living room</h2>
      <div class=grid>
        <div class="card tile"><i class=ic>&#9679;</i><div><b>Ceiling</b><span>On · 80%</span></div></div>
        <div class="card tile"><i class="ic off">&#9679;</i><div><b>Floor lamp</b><span>Off</span></div></div>
        <div class="card tile"><i class=ic>&#9679;</i><div><b>Air purifier</b><span>Auto</span></div></div>
        <div class="card tile"><i class="ic off">&#9679;</i><div><b>Blinds</b><span>Closed</span></div></div>
      </div>
      <div style="margin-top:14px">
        <span class=badge>&#9679; 24.5 &deg;C</span>
        <span class=badge>&#9679; 61 %</span>
        <span class=badge>&#9679; 3 on</span>
      </div>
    </div>
    <div>
      <h2>Controls</h2>
      <div class=card>
        <div class=row style="margin-bottom:14px"><div class="sw on"></div><div>Kitchen lights</div></div>
        <div class=row style="margin-bottom:14px"><div class=sw></div><div class=sub>Guest mode</div></div>
        <div class=row style="margin-bottom:14px"><div class="cb on">&#10003;</div><div>Notify on arrival</div>
          <div class=cb></div><div class=sub>Vacation</div></div>
        <input class=f placeholder="Search entities&hellip;">
        <div class=sp style="margin-top:14px">
          <button class="btn loud">Primary</button>
          <button class="btn normal">Secondary</button>
          <button class="btn quiet">Cancel</button>
          <button class="btn danger">Delete</button>
        </div>
        <p class=sub style="margin-bottom:0">Body text with a <a href=#>link</a> and <code>code span</code>
        to check the readable minimum on glass.</p>
      </div>
    </div>
  </div>

  <h2>Dialog &amp; bottom sheet</h2>
  <div class=scrim>
    <div class=dialog>
      <div style="font-size:20px;font-weight:700;margin-bottom:4px">Ceiling light</div>
      <div class=sub style="margin-bottom:14px">Living room &middot; on</div>
      <div class=sp><button class="btn loud">Turn off</button><button class="btn quiet">Settings</button></div>
    </div>
    <div class=sheet>
      <div class=handle></div>
      <div style="font-weight:700;margin-bottom:4px">More info</div>
      <div class=sub>Mobile more-info is a bottom sheet in 2026.</div>
    </div>
  </div>

  <h2>Opaque layer (settings page + sidebar drawer)</h2>
  <div class=settings>
    <div class=panel>
      <div style="font-weight:700;margin-bottom:2px">使用者偏好設定</div>
      <div class=sub style="margin-bottom:12px">Opaque page, opaque panel, no wallpaper.</div>
      <div class=row style="margin-bottom:10px"><input class=f value="繁體中文" style="max-width:280px"></div>
      <div class=row><div class="sw on"></div><div>進階模式</div></div>
    </div>
  </div>
  <div class=drawer-test>
    <div class=behind>
      <div style="font-weight:700;font-size:18px">內容頁標題</div>
      <p class=sub>If you can read THIS through the drawer on the left, the
      sidebar background is not opaque and the theme is broken.</p>
      <p class=sub>內容頁文字 內容頁文字 內容頁文字 內容頁文字</p>
    </div>
    <div class=drawer>
      <div class="item sel"><i class=dot></i>Overview</div>
      <div class=item><i class=dot></i>媒體</div>
      <div class=item><i class=dot></i>能源</div>
      <div class=item><i class=dot></i>歷史</div>
    </div>
  </div>

  <h2>Primary ramp &amp; status</h2>
  <div class=card>
    <div class=sp id=ramp></div>
    <div class=sp style="margin-top:12px" id=status></div>
  </div>

  </div>
</div>
<script>
const R=[5,10,20,30,40,50,60,70,80,90,95];
document.getElementById('ramp').innerHTML=R.map(s=>
  `<div class=swatch style="background:var(--ha-color-primary-${String(s).padStart(2,'0')})"></div>`).join('');
document.getElementById('status').innerHTML=
  ['error','warning','success','info'].map(c=>
  `<div class=swatch style="background:var(--${c}-color)"></div>`).join('');
</script>
</body></html>"""


def render(theme_path: pathlib.Path) -> list[pathlib.Path]:
    data = yaml.safe_load(theme_path.read_text(encoding="utf-8"))
    (name, theme), = data.items()
    OUT.mkdir(parents=True, exist_ok=True)
    shots = []
    for mode in ("light", "dark"):
        if mode not in theme.get("modes", {}):
            continue
        # HA applies themes with element.style.setProperty(), not an HTML
        # attribute -- do the same, or values containing double quotes (the
        # SF font stack) silently truncate the style attribute and NOTHING
        # gets themed.
        payload = json.dumps(flatten(theme, mode))
        inject = ("<script>const T=" + payload +
                  ";for(const k in T){document.documentElement.style"
                  ".setProperty('--'+k,T[k]);}</script>")
        html = PAGE.replace("<head>", "<head>" + inject, 1)
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(html)
            src = f.name
        png = OUT / f"{name.replace(' ', '_')}__{mode}.png"
        js = f"""
const {{chromium}} = require('playwright');
(async () => {{
  const b = await chromium.launch();
  const p = await b.newPage({{viewport:{{width:1280,height:1500}},deviceScaleFactor:2}});
  await p.goto('file://{src}');
  await p.waitForTimeout(400);
  await p.screenshot({{path:'{png}', fullPage:true}});
  await b.close();
}})();"""
        subprocess.run(["node", "-e", js], check=True,
                       cwd="/home/claude/.npm-global/lib/node_modules")
        shots.append(png)
    return shots


if __name__ == "__main__":
    for arg in sys.argv[1:] or ["themes/VisionOS 26.yaml", "themes/Liquid Glass 26.yaml"]:
        for s in render(ROOT / arg):
            print("wrote", s.relative_to(ROOT))
