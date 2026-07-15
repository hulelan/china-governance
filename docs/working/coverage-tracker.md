# Coverage tracker — national coverage of Chinese government websites

**THE registry.** Single source of truth for what we crawl, what's buildable, and
what's BLOCKED. Goal: full coverage of CN gov sites (34 province-level jurisdictions,
their departments, and cities). Regenerate the reachability/CMS columns anytime with
`scripts/rnd/discovery/coverage_probe.py` (probes each portal from the droplet).

**Status keys:**
- ✅ `CRAWLED` — we have a working crawler + docs
- 🟢 `BUILDABLE` — reachable from the droplet + CMS known → build now
- 🟡 `ANTI-BOT` — reachable but 403/412/406 → needs browser-shaped headers/cookies
- 🔴 `BLOCKED` — IP-blocked from the droplet (000/timeout) → needs a China/residential vantage point
- ❔ `UNKNOWN-CMS` — reachable but CMS not yet characterized

**CMS platforms seen:**
- `gkmlpt` (公开目录平台) — Guangdong ecosystem. Auto-discovers (SID + tree). FREE batch via `crawlers/gkmlpt.py` (add a SITES entry).
- `jpaas` (jpage `dataproxy.jsp`) — Jiangsu, Shandong… Needs multi-site config (webid discoverable, unitid TODO). One crawler → many provinces.
- `col/` — column-based (Yunnan, Beijing 人社局). Characterize per-site.
- static year-archives — Shanghai. Per-portal.

---

## 1. Provincial portals (31 mainland province-level)

> Populated by `coverage_probe.py` (2026-07-15). `http` = status from droplet.

**Survey 2026-07-15 (31 mainland province-level). Tally: 7 CRAWLED · 2 BUILDABLE(CMS
known) · 8 UNKNOWN-CMS(reachable) · 5 ANTI-BOT · 9 BLOCKED.**

| Status | Jurisdictions |
|---|---|
| ✅ CRAWLED (7) | 广东, 北京, 上海, 江苏, 浙江, 黑龙江, 重庆 |
| 🟢 BUILDABLE (2) | **山东 (jpaas → crawlers.jpaas)**, 云南 (col/) |
| ❔ UNKNOWN-CMS, reachable (8) | 天津, 辽宁, 吉林, 福建, 湖南, 西藏, 宁夏, 新疆 |
| 🟡 ANTI-BOT 403/412 (5) | 内蒙古(403), 安徽(403), 河南(403), 湖北(412), 甘肃(412) |
| 🔴 BLOCKED 000 (9) | 河北, 山西, 江西, 广西, 海南, 四川, 贵州, 陕西, 青海 |

So **~10 provinces are buildable from the droplet now** (2 known-CMS + 8 to characterize),
5 might yield to browser headers, and **9 hard-blocked need a China vantage point.**

**jpaas SOLVED (2026-07-15):** `crawlers/jpaas.py` — generic multi-site jpaas crawler
that AUTO-DISCOVERS unitid/webid/columns from any jpaas site's column pages (validated:
js_czt → 45 docs). Covers Jiangsu departments + Shandong + any jpaas province. Add a
`SITES` entry. TODO: discovery currently finds top-nav policy columns (政策解读); deepen
to reach 规范性文件 sub-columns for full doc coverage.

## 2. Provincial departments

- **Guangdong — 20 CRAWLED (gkmlpt, 2026-07-15):** 自然资源厅/人社厅/住建厅/教育厅/科技厅/
  工信厅/公安厅/民政厅/财政厅/生态环境厅/交通运输厅/农业农村厅/商务厅/文旅厅/卫健委/
  应急管理厅/林业局/医保局/发改委/统计局 (`gdnr`, `gdedu`, … in `SITES`).
  TODO: 水利厅/市场监管局/司法厅/审计厅 (correct domains).
- **Jiangsu depts — BUILDABLE (jpaas):** need multi-site refactor of `jiangsu.py` (solve
  unitid). 财政厅/发改委/工信厅/交通厅 reachable + jpaas confirmed.
- **Beijing depts — UNKNOWN-CMS:** 人社局 = col/; others no clear marker. Characterize.
- Other provinces' departments: pending each province's portal build.

## 3. Municipalities & cities (already crawled)

- Guangdong cities (gkmlpt): 广州/深圳(+districts/depts)/珠海/惠州/江门/中山/汕头/汕尾/
  韶关/河源/阳江/湛江/肇庆/揭阳/云浮/东莞/佛山 (many; some KNOWN_BROKEN).
- Other: 苏州(Suzhou)/武汉(Wuhan)/杭州(Hangzhou).
- **深圳 (Shenzhen)** — main portal + 9 districts + 13 departments + investment portal.

## 4. Central (CRAWLED)

State Council (+ `--library` for the full document DB), NDRC, MOF, MEE, CAC, NDA, SIC,
SAMR, MOFCOM, MIIT, MOST, MOE, NPC(metadata-only), IPC court. Media: Xinhua, People's
Daily, Phoenix, etc.

## 5. 🔴 BLOCKED registry (needs a China / residential vantage point)

The critical list. These are unreachable from the droplet's NYC datacenter IP:
- **Provinces (000/hard-block):** 四川, 河北, + (survey) 安徽, 江西, 陕西, 甘肃, 贵州,
  山西, 内蒙古, 广西, 海南, 青海 — confirm/refine via probe.
- **Anti-bot (403/412 — maybe fixable with headers):** 河南, 湖北.
- **GD cities:** 惠州, 阳江 (datacenter-IP blocked; we hold older docs from residential crawls).
- **NPC full statutory text** — China-IP gated (metadata worldwide).
- **DECISION:** a mainland-China VPS or residential proxy unblocks the hard-blocked
  majority in ONE move. Same decision pending for NPC full-text. This is the gating
  factor for NATIONAL coverage — not crawler code.

## 6. Build queue (reachable, do now)
1. **jpaas multi-site crawler** — unblocks Jiangsu depts + Shandong (+ likely more). Highest multiplier.
2. **Reachable unknown-CMS provinces** — characterize + build: 湖南/福建/辽宁/吉林/天津/云南(col)/新疆/宁夏/西藏.
3. **GD leftover depts** — 水利厅/市场监管局/司法厅/审计厅 (find domains).
4. **Anti-bot retry** — 河南/湖北 with browser headers+cookies.
