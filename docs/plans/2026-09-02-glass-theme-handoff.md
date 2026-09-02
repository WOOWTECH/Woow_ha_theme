# 交接文件：VisionOS 26 / Liquid Glass 26 主題

- **建立**：2026-09-02
- **狀態**：管線已打通、兩個主題已上線、**真機實測與評分尚未執行**
- **接手者請先讀**：第 6、7 節（那是你要做的事）

---

## 1. 這個專案在做什麼

`WOOWTECH/Woow_ha_theme` 是 52 個 HA 主題的集合。目標是把其中的 **visionOS 系列**升級到能對齊 Apple 真實設計規格、並且在 HA 2026.x 上真的跑得好。

範圍限定在兩個主題：`VisionOS 26`、`Liquid Glass 26`。舊的 `visionos.yaml` / `Liquid Glass.yaml` **保留未動**，可以直接切換比對。

---

## 2. 為什麼要重做，不是修補

HA 前端在 2025.5 → 2026.5 之間從 Polymer/Paper + Material Web 遷移到 **Web Awesome**。現在一個主題要餵四層 token：

```
--ha-color-* / --ha-border-radius-* / --ha-font-*   真正的 source of truth
        ↓
--wa-*                          Web Awesome 消費層（按鈕/開關/對話框/輸入框全讀這層）
        ↓
--primary-color / --ha-card-*   legacy 相容層（只有 3 個真的被 derive）
        ↓
--mdc-* / --md-sys-color-*      殘骸（大多已死，本專案刻意不輸出）
```

舊 `visionos.yaml` 114 個 key 的覆蓋率：`--wa-*` **0 個**、語意色 11 個、bottom sheet 0 個、死掉的 `--paper-*` 還留 16 個。手改補不完，所以改成**生成式**。

---

## 3. 目前的架構

```
sources/glass.tokens.yaml          ~40 個設計決策（唯一該手改的檔）
        │  scripts/build_glass_themes.py   展開四層 + self-check
        ↓
themes/VisionOS 26.yaml            57 個全域 key + light/dark 各 ~150
themes/Liquid Glass 26.yaml
        │  scripts/probe.py                容器內 Chromium 離線渲染
        ↓
docs/probe/*.png                   改完先看圖（此目錄已 gitignore）
```

### 3.1 三層規矩（最重要，違反就會出大事）

Apple 的規則：**玻璃只屬於導航層，不進內容層，不玻璃疊玻璃。** HA 的變數看起來可以互換，實際上不行：

| 層 | 變數 | 規則 |
|---|---|---|
| **不透明層** | `primary-background-color`、`secondary-background-color`、`card-background-color`、`material-background-color`、`sidebar-background-color`、`table-row-alternative-background-color` | HA 當 `background-color:` 用。**放 gradient 或半透明 rgba 會讓整個頁面透出後面** |
| **桌布層** | `lovelace-background` | 吃完整 `background` shorthand，只有儀表板視圖。圖片**只能**放這裡 |
| **玻璃層** | `ha-card-background`（badge 共用）、app header、dialog、bottom sheet | alpha 依 Apple material 階，不低於 ~0.45 |

`scripts/build_glass_themes.py` 的 self-check 會擋住不透明層被寫成半透明/gradient，build 直接 fail。**不要繞過它。**

### 3.2 Apple 規格對照（已套用）

| 項目 | 值 |
|---|---|
| 系統色 | 明暗兩套。systemBlue `#007AFF` / `#0A84FF`，systemOrange `#FF9500` / `#FF9F0A`，紅綠黃青紫粉褐同理 |
| 語意墨水底色 | 亮 `#3C3C43`(60,60,67)、暗 `#EBEBF5`(235,235,245)。**不是純黑純白** |
| 分隔線 | 亮 `rgba(60,60,67,.29)`、暗 `rgba(84,84,88,.60)`（暗色用不同底色） |
| systemFill | 亮 `.20/.16/.12`、暗 `.36/.32/.24`，底色 `rgba(120,120,128,x)`，半透明才會融進背景 |
| systemGray | 六階，**明暗方向相反**。neutral ramp 對外一律 05→95 由暗到亮 |
| 材質 | thin/regular/thick = 亮 `.60/.72/.84`、暗 `.45/.65/.80` |
| 模糊 | `blur(20px) saturate(180%)`——apple.com 官網自己用的值 |
| 高光 | `inset 0 1px 0` 上緣 + `inset 0 -1px 0` 下緣 + `0 8px 32px rgba(0,0,0,.10)` 落地陰影。**不用均勻邊框** |
| 圓角 | 同心律（WWDC23 10076）：**內圓角 + padding = 外圓角**。卡片 20/22、alert 14、sheet 16、控制項 capsule |
| 字體 | `-apple-system, BlinkMacSystemFont, system-ui, ...`（SF Pro 不能當 webfont 授權） |
| 控制項 | UISwitch 51×31、thumb 27；最小點擊 44×44 |

---

## 4. 環境與存取

| 項目 | 值 |
|---|---|
| 實驗機 | **E&L house**（Elmo 家主力），HA **2026.7.0**，HA Container（**無 Supervisor、無 add-on**） |
| MCP | `Elmo_ha_mcp`（另有 `folight_ha_mcp` 乾淨備用機；`woowtech_ha_mcp` 目前連線失敗） |
| HACS | 已裝 v2.0.5，本 repo 的 repository_id = **`1207592079`** |
| card-mod | **未安裝**。主題不依賴它 |
| 目前預設主題 | `Woow Dual Blue`（未改動） |

### 4.1 部署迴圈（已實測可用）

repo 沒有發過 release，HACS 會**直接讀 main 分支**：

```
改 sources/ → python3 scripts/build_glass_themes.py → push main
    → ha_manage_hacs(action="update_information", repository_id="1207592079")
    → ha_manage_hacs(action="download",           repository_id="1207592079")
    → ha_reload_core(target="themes")
    → ha_manage_theme(action="list")   # 確認主題還在清單裡
```

push 到 main 之後 **等 60~90 秒**讓 GitHub Actions 重建 `themes/woow_ha_themes.yaml`（HACS 實際安裝的是這個合併檔），再做 update_information。

---

## 5. 這輪已經做完的事

1. 建立 `sources/glass.tokens.yaml` + `scripts/build_glass_themes.py` + `scripts/probe.py`
2. 產出 `VisionOS 26` / `Liquid Glass 26`，已部署到 E&L house，主題清單可見（共 59 個）
3. 打通 push → HACS → reload 的自動化迴圈並實測成功
4. **修掉一個致命 bug**：`primary-background-color` 被寫成 gradient，HA 當 `background-color:` 用 → 宣告被丟棄 → 設定頁整片透明，內容與側邊欄文字互疊。同時側邊欄設成 10% 白，手機抽屜壓在內容上直接穿透
5. 全面對照 Apple 規格重寫（見 3.2）
6. 生成器加上 self-check（死變數、非字串值、必填 token、`modes:` 存在、**不透明層檢查**）
7. probe 加上不透明層回歸測試（設定頁 + 側邊欄抽屜壓內容）

---

## 6. 【待執行】真機實測驗證

**這是接手後的第一優先。目前為止只有離線探針驗證過，真機只有使用者手動截了一張，就抓到探針沒抓到的致命 bug。**

### 6.1 前置

先問使用者拿其中一項，不然只能靠他手動截圖：

- **對外 HTTPS URL + long-lived token** → 可用 Browserless MCP 自動登入、切主題、截圖比對（最理想）
- 或請他手動截圖回傳

### 6.2 測試矩陣

兩個主題 × 明/暗 × 下列畫面。**每一格都要看到，不能抽樣。**

| # | 畫面 | 重點看什麼 |
|---|---|---|
| 1 | 儀表板（sections 視圖） | 卡片玻璃感、間距、桌布有沒有出來 |
| 2 | 儀表板（舊 masonry 視圖） | 同上，舊視圖常常漏 |
| 3 | **側邊欄展開（手機抽屜）** | **是否不透明、有沒有穿透**（這次的 bug） |
| 4 | **設定 → 使用者偏好設定** | **頁面是否不透明**（這次的 bug） |
| 5 | 設定 → 裝置與服務（清單/表格） | data table 背景、分隔線 |
| 6 | 點任一實體 → more-info | 桌面是 dialog、**手機是 bottom sheet**，兩個都要看 |
| 7 | 開發者工具 → 狀態 | 表格、程式碼區塊、輸入框 |
| 8 | 記錄/歷史 | 圖表色彩（`--color-1..54` 本主題沒覆蓋，看會不會撞色） |
| 9 | 能源儀表板 | Apple 系統色在圖表上的表現 |
| 10 | 通知 / 待辦事項 | 列表列高、hover |
| 11 | HACS 頁面 | 第三方頁面容錯 |
| 12 | 自訂卡片（該機有 21 個 HACS 卡片） | 至少測 button-card、mushroom、bubble-card、navbar-card |

### 6.3 每張截圖要檢查的清單

- [ ] 有沒有任何地方**透出後面的內容**（最高優先）
- [ ] 文字對比夠不夠（尤其次要文字壓在玻璃上）
- [ ] 「關閉/未啟用」狀態看不看得見（開關軌道、灰掉的圖示）
- [ ] 圓角有沒有內外同值（同心律違反）
- [ ] 陰影會不會太重（不該像 Material）
- [ ] 主色有沒有染到底（按鈕、開關、focus ring 不該還是 HA 原生青色）
- [ ] 明暗切換有沒有哪一邊爛掉
- [ ] 手機 Companion App 的 bottom sheet
- [ ] iOS Safari 上 `backdrop-filter` 有沒有生效（舊 iPadOS 可能整個 no-op）
- [ ] 大量卡片時捲動順不順（`backdrop-filter` 在 Android WebView 上很吃效能）

### 6.4 回報格式

每發現一個問題就記成：`畫面 / 模式 / 主題 / 症狀 / 疑似哪個變數`，然後**改 `sources/glass.tokens.yaml` 或生成器，不要直接改 `themes/*.yaml`**（那是生成檔，下次 build 會被蓋掉）。

---

## 7. 【待執行】評分表

目前**還沒有任何評分機制**。請建立並在真機實測後逐項打分，0–5 分，附證據（截圖或變數值）。

| 面向 | 權重 | 評分定義 |
|---|---|---|
| A. 不透明層正確性 | 25% | 5 = 12 個畫面零穿透；0 = 任一頁面透明 |
| B. 對比與可讀性 | 20% | 5 = 全部符合 WCAG AA；扣分依未達標的元素數 |
| C. Apple 規格吻合度 | 20% | 逐項對照 3.2 表；每項不符扣 0.5 |
| D. Token 覆蓋率 | 15% | 用 HA frontend 的 token 清單掃描缺漏數 |
| E. 效能 | 10% | 手機捲動 fps、Companion App 電量觀感 |
| F. 相容性 | 10% | 21 個 HACS 卡片有幾個爛掉 |

**及格線建議 4.0，A 面向不到 5 分一律不予發布。**

補充：C 面向的自動化可以再往前推一步——寫一支腳本，把生成的主題值和 3.2 表逐項 assert，變成 CI 的一部分。目前 self-check 只擋致命錯，沒擋「不夠 Apple」。

---

## 8. 剩下的已知問題（依優先序）

| # | 問題 | 說明 | 誰能解 |
|---|---|---|---|
| 1 | **真機未驗證** | 見第 6 節 | 接手者 |
| 2 | **無評分機制** | 見第 7 節 | 接手者 |
| 3 | `prefers-reduced-transparency` / `prefers-contrast` 無降級 | iOS 開「降低透明度」時玻璃會自動變霜面；HA 主題 YAML **沒有 media query**，做不到。要嘛裝 card-mod/UIX，要嘛額外掛一個 CSS resource | 需決策 |
| 4 | `Common Base (Do Not Use)` × 5 外洩 | `metro.yaml` 的 YAML anchor 底座變成可選主題，出現在使用者的主題下拉選單。改 anchor 定義方式即可 | 接手者，30 分鐘 |
| 5 | HACS 不安裝 `www/` 背景圖 | 任何人裝完，`/local/visionos-themes/*.jpg` 都不存在。目前用漸層墊底讓它「沒圖也完整」，但要真的有圖仍需手動複製。可考慮改成 data URI 或縮圖內嵌 | 需決策 |
| 6 | CI 不會跑新生成器 | GitHub App 沒有 `workflows` 權限，`.github/workflows/*.yml` 改不了。**目前生成檔是手動 push 的**。請在 repo 設定加上權限，或使用者自己在 workflow 加一步 `python3 scripts/build_glass_themes.py`（放在 `build_combined_theme.py` 之前，並把 `sources/**` 加進 paths） | 使用者 |
| 7 | 沙箱不能 `git push` 這個 repo | git proxy 未授權，整輪都走 GitHub MCP 逐檔提交，導致本地/遠端 commit 歷史分岔（內容一致）。把 repo 加進 session 授權來源即可 | 使用者 |
| 8 | 圖表色 `--color-1..54` 未覆蓋 | 歷史/能源圖表還是 HA 預設色盤，跟 Apple 系統色會撞 | 接手者 |
| 9 | 其餘 50 個主題未套用此做法 | iOS 系列 28 個結構高度重複，值得先拆解再用同一個生成器 | 待決策 |
| 10 | 舊 `visionos.yaml` / `Liquid Glass.yaml` 還在 | 驗收通過後決定是刪除、還是改成指向新版的別名 | 待決策 |

---

## 9. 踩過的雷（別再犯）

1. **`background-color:` 吃不下 gradient**——寫進去等於整條被丟棄，變透明。這是本輪最大的坑。
2. **半透明不能給頁面/側邊欄/表格**——手機側邊欄是壓在內容上的抽屜，不是浮在桌布上。
3. **HA 只在內建預設主題跑 OKLCH 自動生色階**（`palette.ts` 只在 `themeToApply === "default"` 時呼叫）。自訂主題必須自己吐 `ha-color-primary-05..95` 11 階，否則 Web Awesome 的按鈕/開關/focus ring 全部維持 HA 原生青色。
4. **主題值必須全是字串**。HA 的 `THEME_SCHEMA` 是 `{cv.string: cv.string}`，一個裸數字會讓**整個主題**驗證失敗、從選單靜默消失。
5. **`--sidebar-selected-text-color` 已死**，2026 只讀 `--sidebar-selected-icon-color`。
6. **`--paper-*` 全數已死**（frontend 全庫 0 引用），`--mdc-*` 只剩少數殘骸。
7. **neutral ramp 方向**：HA 慣例 05→95 由暗到亮，但 Apple 的 systemGray 明暗兩套方向相反。直接照抄暗色那套會把 ramp 接反。
8. **probe 用 inline style 屬性會爆**：SF 字體堆疊含雙引號，會提早關閉 `style="..."`，整頁沒套到主題還看不出來。要用 `element.style.setProperty()`，跟 HA 實際做法一致。
9. **card-mod issue #606**：HA ≥ 2026.8 會打斷 card-mod 的 YAML 主題載入路徑（正是玻璃主題會用的那條），官方未修。本專案已把 card-mod 降級成選配且預設關閉，**不要為了做鏡面高光又把它變成必要依賴**。
10. **改完一定要跑 probe 再上真機**，但要知道 probe 抓不到 shadow DOM 與第三方卡片——這次的致命 bug 就是 probe 沒抓到。

---

## 10. 指令速查

```bash
git clone https://github.com/WOOWTECH/Woow_ha_theme.git && cd Woow_ha_theme
pip install pyyaml

python3 scripts/build_glass_themes.py     # 生成 + self-check
python3 scripts/probe.py                  # 產 docs/probe/*.png（需 Chromium + playwright）
python3 scripts/build_combined_theme.py   # 合併成 HACS 安裝的單一檔（CI 也會做）
```

MCP（`Elmo_ha_mcp`）：

```
ha_manage_theme(action="list")
ha_manage_theme(action="set", theme_name="VisionOS 26")
ha_manage_theme(action="set", theme_name="VisionOS 26", mode="dark")
ha_reload_core(target="themes")
ha_manage_hacs(action="update_information", repository_id="1207592079")
ha_manage_hacs(action="download",           repository_id="1207592079")
ha_get_logs()                              # 主題驗證失敗會在這裡
```

---

## 11. 相關檔案

| 路徑 | 用途 |
|---|---|
| `sources/glass.tokens.yaml` | **唯一該手改的檔** |
| `scripts/build_glass_themes.py` | 生成器 + self-check |
| `scripts/probe.py` | 離線視覺探針 |
| `themes/VisionOS 26.yaml` | 生成檔，勿手改 |
| `themes/Liquid Glass 26.yaml` | 生成檔，勿手改 |
| `themes/woow_ha_themes.yaml` | CI 產出的合併檔，HACS 實際安裝的就是它 |
| `docs/plans/2026-04-11-...prd.md` | 前一輪的 8 輪測試 PRD（可當評分表的參考格式） |
