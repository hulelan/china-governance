# Access Blocking — how servers block a crawler, which walls WE hit, and how to get past them

**Audience:** the project owner, technically fluent, who wants (a) the full taxonomy
of how a web server can refuse a client like ours, (b) a map of which of those walls
we *actually* hit and where, (c) bypass options that work from a **US cloud droplet +
a Mac abroad** with **no Chinese residential IP**, and (d) proportionate ideas for
hardening our own site, chinagovernance.com.

Companion docs: `docs/working/source-access-map.md` (the living Tier A–F reachability
record — read it first for the current per-host status), `crawlers/base.py` (our
`fetch()`), and CLAUDE.md "Known Issues" (our own nginx rate-limits + Basic Auth).

---

## 0. The one-paragraph mental model

A request has to survive **five gates in sequence**, and any one of them can drop it:
**(1) can your packets even reach the origin** (IP/ASN/GeoIP) → **(2) does your TLS
handshake look like a real browser** (JA3/JA4) → **(3) does your HTTP/2 frame + header
order look like a real browser** → **(4) can you execute the JavaScript challenge and
carry the cookie it sets** → **(5) do your request *rate and behavior* look human**
(rate-limit, CAPTCHA, mouse/timing). Our crawler (`crawlers/base.py`) is a Python
`urllib` client: it clears gate 1 only for IPs that like datacenters, and it fails
gates 2–4 **by construction** because it is not a browser and has a fixed, non-Chrome
fingerprint. Almost every "curl works but our `fetch()` gets a stub" case is a gate-2/3
fingerprint failure; almost every "blackhole from the droplet" case is gate-1.

---

## 1. The taxonomy of blocking

### 1.1 IP-layer blocking (gate 1)

**How it's implemented.** The cheapest, earliest filter — decided before any HTTP is
parsed, often before the TLS handshake completes, sometimes at the router (BGP
blackhole) so the TCP SYN is simply dropped.

- **Datacenter / ASN blocklists.** The WAF or CDN keeps a list of ASNs known to be
  hosting providers (DigitalOcean AS14061, AWS, GCP, OVH, Hetzner…) and refuses or
  tarpits them. Feeds like MaxMind's "anonymous IP" / connection-type DB, IP2Location,
  or a CDN's own telemetry label an IP `hosting` vs `residential` vs `mobile`. Our
  droplet is `104.236.88.45`, **AS14061 DigitalOcean, geolocated NYC** — a textbook
  "block datacenter traffic to a domestic-only site."
- **GeoIP allow/deny (CN-only).** Many Chinese government portals allow only
  China-geolocated IPs to reach `/zwgk/` policy sections. Implemented as an nginx
  `geo`/`geoip2` map, a CDN edge rule, or a national-level filter. A non-CN IP gets a
  TCP reset, a 403/406/412, or a silent drop.
- **IP reputation feeds.** Real-time scores (Spamhaus, Project Honeypot, commercial
  bot-intel) that demote IPs seen scraping elsewhere. A shared cloud IP inherits the
  sins of previous tenants.

**Unique drawbacks / failure modes.**
- **Collateral damage:** blunt ASN blocks also block Googlebot, Bingbot, and legit
  cloud-hosted services, so sites that want to be indexed usually *can't* do a hard
  datacenter block on their public pages — which is exactly why the CN-gov pattern is
  "domestic users only, we don't care about foreign search indexing."
- **ASN churn:** cloud providers add/rotate ranges constantly, so blocklists are
  perpetually stale — a brand-new droplet IP sometimes works for a while.
- **VPN/proxy leakage:** GeoIP is defeated by any IP inside the allowed region, so a
  CN-egress proxy flips the whole decision (see §3). Conversely, a "residential" proxy
  that's actually a flagged datacenter range gets caught by the reputation layer even
  though its GeoIP says residential.

### 1.2 TLS fingerprinting — JA3 / JA4 (gate 2)

**This is almost certainly why our residential-Mac `curl`/`urllib` still fails
`ccg.gov.cn` while the browser renders it.** Worth explaining precisely.

**How it's implemented.** When any TLS client opens a connection it sends a
**ClientHello** in the clear (before encryption). That message enumerates, in a
specific order, the client's: TLS version, the **cipher suites** it offers, the TLS
**extensions** it advertises, the **elliptic curves** (supported groups), and the
**EC point formats**. Different TLS *stacks* build this list differently, so the
ClientHello is a stack fingerprint:

- **JA3** (Salesforce, 2017) concatenates five fields in order —
  `TLSVersion,Ciphers,Extensions,EllipticCurves,ECPointFormats` (decimal values joined
  by `-` and `,`) — and **MD5-hashes** the string. A given client library produces a
  stable JA3 hash; WAFs keep an allowlist of "known browser" JA3s and a blocklist of
  "known tool" JA3s (curl, Python `urllib`/`requests`, Go `net/http`, Java).
- **JA4 / JA4+** (FoxIO, 2023, the current standard) fixes JA3's two weaknesses. JA3 is
  order-sensitive, so clients could randomize cipher/extension order ("cipher
  stunting") to churn their hash. **JA4 sorts the ciphers and sorts the extensions
  before hashing, and folds in signature algorithms**, so the fingerprint is stable
  against reordering and *harder to evade*. JA4 is also human-readable —
  `a_b_c` format: the `a` part is metadata (protocol q/t, TLS version, SNI present d/i,
  cipher count, extension count, first ALPN), `b` is a hash of the sorted cipher list,
  `c` is a hash of the sorted extensions + signature algorithms. **JA4+** is a family:
  **JA4H** (HTTP: method, header set, header *order*, cookie values — see §1.3),
  **JA4S** (the server's response fingerprint), **JA4T** (TCP-layer: window size,
  options order — OS-level).

**Why urllib and curl look different from Chrome — the precise reason.** Chrome ships
**BoringSSL**; Firefox ships **NSS**; Python `urllib`/`ssl` and `curl` ship
**OpenSSL**. These libraries offer *different cipher suites in a different order*,
advertise *different extensions* (Chrome sends GREASE values, `application_settings`
(ALPS), `compress_certificate`, a specific `signature_algorithms` set, session-ticket
and padding extensions in a Chrome-specific order; OpenSSL's default list and order are
nothing like it). So Chrome's JA3/JA4 is one well-known value that millions of real
users share, and Python-`urllib`-over-OpenSSL is a *completely different* value that
screams "automated tool." **Our `base.py` makes this worse, not better:** it builds a
`_permissive_ssl_ctx()` that calls `set_ciphers("DEFAULT:@SECLEVEL=1")` and sets
`OP_LEGACY_SERVER_CONNECT` — great for handshaking with crumbling legacy gov TLS, but
it produces an *even more unusual, even more non-Chrome* ClientHello. Setting a browser
`User-Agent` string (which we do) changes nothing here: the UA is an HTTP header sent
*after* the TLS handshake, while JA3/JA4 is computed *from the handshake itself*. **A
WAF that fingerprints TLS sees "OpenSSL tool" no matter what UA you claim.** That is the
`ccg.gov.cn` situation: the residential Mac clears gate 1 (IP is fine) but fails gate 2
(the handshake isn't Chrome's), so it gets the 418 "访问被拦截" interstitial while the
actual browser on the same machine, with the same IP, sails through.

**Unique drawbacks / failure modes (for the defender).**
- **False positives on odd-but-legit clients:** IoT, old Androids, corporate proxies,
  and legit API integrations have non-browser JA3s and get caught.
- **JA3 is evadable** (that's why JA4 exists) — randomized order changed the hash.
- **Fingerprints drift with browser releases:** every Chrome major bumps the
  fingerprint, so allowlists need maintenance, and *impersonation tools* need to track
  the current Chrome (see curl_cffi's `chrome124`/`chrome135` targets in §3).
- **Shared hashes:** many clients share one JA3, so it identifies the *stack*, not the
  user — a blocklist of "curl's JA3" also blocks every honest curl user.

### 1.3 HTTP/2 and header-order fingerprinting (gate 3)

**How it's implemented.** Even a client that fakes the TLS handshake can betray itself
one layer up:

- **HTTP/2 fingerprinting (Akamai-style / the "Akamai fingerprint").** HTTP/2 opens
  with SETTINGS frames (header table size, max concurrent streams, initial window
  size, max frame size), a WINDOW_UPDATE, priority frames, and a specific
  **pseudo-header order** (`:method :authority :scheme :path` vs other orders). Each
  client stack emits a characteristic combination, hashed into an "Akamai
  fingerprint." Chrome's HTTP/2 settings tuple is well-known; Python `httpx`/`h2`,
  `curl`, and Go emit different tuples.
- **Header order & casing.** Browsers send request headers in a fixed order
  (`sec-ch-ua`, `sec-fetch-*`, `accept`, `accept-encoding`, `accept-language`, …) with
  specific casing and specific *values* (Chrome's `Accept` string, its
  `sec-ch-ua` client hints). `urllib` sends a short, differently-ordered, differently-
  cased header set and omits the `sec-*` client-hint headers entirely. **JA4H** hashes
  exactly this (method + header set + order + cookies). A WAF can allow a perfect JA3
  but still reject a request whose header order isn't Chrome's.

**Unique drawbacks / failure modes.** Highly brittle for the defender (header order
varies across legit HTTP libraries and even browser versions/extensions), and cheap for
a *browser-based* attacker to pass perfectly — so this gate mainly catches naive
scripted clients (like ours) and is easily cleared by real-browser automation or a
faithful impersonation library, but it raises false-positive risk if tuned aggressively.

### 1.4 JavaScript challenges (gate 4)

**How it's implemented.** The first response isn't the content — it's a small HTML+JS
"interstitial" that the client must execute, after which it's allowed through
(usually by setting a cookie the real content pages then require). Flavors:

- **Cookie-setting redirect.** Server answers the first request with a 302→self (or a
  200 stub) that runs JS to compute a token and set a cookie; the reload carries the
  cookie and gets content. Our `base.py` already installs a `HTTPCookieProcessor`
  (comment names the openresty `CT6T/CT6TS` cookie pattern) — that handles the *trivial*
  "set a static cookie and redirect" case, but **not** a case where JS must *compute*
  the cookie value.
- **Proof-of-work interstitial.** The "wait 5 seconds" page runs a CPU puzzle
  (hash grinding) to make automated mass-fetching expensive. Cloudflare's old JS
  challenge and its "I'm Under Attack Mode" are the western archetype.
- **Browser-environment probes.** The JS inspects `navigator` (webdriver flag,
  languages, plugins, hardware concurrency), draws to a `<canvas>` and hashes the
  pixels (**canvas fingerprint**), queries **WebGL** vendor/renderer, checks screen
  metrics, timing, and the presence of automation hooks. A headless or non-browser
  client either can't run the JS at all (dead) or runs it and fails the environment
  probe (detected).

**The common Chinese stacks (name-check).**
- **创宇盾 / 知道创宇 (Knownsec ChuangYuDun / "Yunfangyu").** Cloud WAF+CDN, the most
  common on CN-gov sites. Presents a JS interstitial (`访问被拦截`, "访问验证", 5-second
  style) plus TLS/behavioral filtering; issues cookies after the challenge. **The
  `ccg.gov.cn` 418 "访问被拦截！" is this class of block.** Related Knownsec product:
  **加速乐 (Jiasule)** CDN/anti-bot.
- **安全狗 Safedog (Safedog / 服务器安全狗).** Host-based (agent on the server) WAF —
  signature rules, rate limits, UA/referer checks; lighter than a cloud challenge, more
  a "403 on a suspicious request."
- **长亭雷池 SafeLine (Chaitin).** Popular open-source/commercial WAF built on
  *semantic* request analysis (not just regex signatures) plus a **dynamic-protection /
  JS-challenge** module that rewrites pages and requires browser execution.
- **CloudWAF** (generic cloud-WAF label; also Alibaba Cloud WAF, Tencent Cloud WAF,
  Baidu Cloud) — CDN-fronted WAFs with the same challenge/fingerprint toolkit.
- **Western analogues** (same mechanisms, useful mental model): **Akamai Bot Manager**,
  **Cloudflare** (Turnstile / JS challenge / Bot Fight Mode), **Imperva/Incapsula**,
  **DataDome**, **PerimeterX/HUMAN**.

**Unique drawbacks / failure modes.** Expensive for *everyone*: they break RSS readers,
accessibility tools, legit API clients, and search crawlers; add latency (the 5-second
wait); and are an arms race — every solver update forces a challenge update. Proof-of-
work also burns the *defender's* users' CPU/battery. Aggressive environment probing
generates false positives on privacy browsers (Brave, hardened Firefox) that spoof
canvas/WebGL.

### 1.5 CAPTCHA, behavioral, rate-limiting, honeypots (gate 5)

**How it's implemented.**
- **CAPTCHA** — reCAPTCHA/hCaptcha/Turnstile, or CN sliders (极验 GeeTest
  slide-to-fit, 网易易盾 NetEase Yidun) — an explicit human-proof, usually escalated to
  only when the earlier gates are *suspicious* rather than on every request.
- **Behavioral / mouse+timing.** JS records mouse paths, scroll cadence, keystroke
  timing, dwell time, and inter-request intervals; a client that requests pages on a
  perfect metronome with no mouse events scores as a bot. Often fed to an ML risk score
  rather than a hard rule.
- **Rate-limiting.** Per-IP (or per-subnet, or per-cookie) request quotas — a leaky
  bucket / token bucket returning **429** on exceed. (This is what *we* run — see §4.)
- **Honeypots.** Links/fields invisible to humans (`display:none`, off-screen,
  `nofollow` traps) that only a blind crawler would follow; hitting one flags/bans you.

**Unique drawbacks / failure modes.** CAPTCHAs harm real users (accessibility,
friction) and are cheaply broken by human-solver farms (~$1–3 per 1,000). Behavioral
scoring needs a JS runtime and lots of tuning (false-positive prone). Per-IP
rate-limits are defeated by IP rotation and can wrongly throttle a shared corporate NAT
or a genuine burst; subnet limits (our `57.141.20.0/24` case) over-block. Honeypots risk
catching legit accessibility tools.

---

## 2. Which walls WE actually hit (mapping to specific hosts)

Every case below is drawn from `docs/working/source-access-map.md`. Our client is
`urllib` from `base.py`, vantage = the NYC droplet (AS14061) plus, secondarily, a Mac
on a residential line abroad.

| Our observed symptom | Real host examples | Which gate / mechanism | Why |
|---|---|---|---|
| **`000` — TCP blackhole** (SYN dropped, connection refused/timeout) | 惠州/阳江 GD cities; 住建部 MOHURD, 民政部 MCA, 自然资源部 MNR; Sichuan/Shanxi/Guangxi/Jiangxi/Hebei/Hainan/Guizhou/Shaanxi provinces; 浙江/黑龙江 main portals; `www.hlj.gov.cn` (502); many long-tail cities | **Gate 1** — IP/GeoIP blackhole (network geo-fence) | Datacenter/non-CN IP dropped at the router. Only a CN/residential IP changes it. |
| **`403 / 406 / 412` — WAF geo/reputation block** on policy sections | 河南/安徽/内蒙古 (403); 湖北/甘肃 (412); 卫健委 NHC (412); 云南 Yunnan (homepage 200 but every `/zwgk/*` = 403); `www.baiyin.gov.cn` root 200 but `/art/` docs 403; Gansu 财政厅 czt (412) | **Gate 1** (IP reputation/GeoIP at the WAF) — possibly + gate 2/3 | The TCP connects (so not a pure blackhole), but the edge WAF rejects the request on IP/geo (and section-level rules). |
| **`521` — origin/anti-bot down for us** | 公安部 MPS (521) | **Gate 1/4** (CDN reports origin unreachable / anti-bot) | Cloudflare-style "web server is down" or an anti-bot origin gate. |
| **`418` — CloudWAF challenge interstitial** ("访问被拦截！") | **`ccg.gov.cn`** (China Coast Guard) — blocks the droplet **and** urllib/curl from the residential Mac; only a real browser renders it | **Gate 2 + gate 4** — 创宇盾/知道创宇-class JS challenge + TLS fingerprint | The residential IP passes gate 1; the non-Chrome TLS handshake + the un-executed JS challenge fail gates 2/4. **The clearest fingerprint case we have.** |
| **`988-byte anti-bot shell` on a 200** | 人社部 MOHRSS (`www.mohrss.gov.cn`) | **Gate 4** — JS challenge served as the "content" | IP reachable, but every page is the challenge stub, not real HTML. Needs a cookie-solving/browser fetch (our Tier D). |
| **"curl -L returns 7 KB but our `urllib fetch()` gets an HTTP-error stub"** | 成都 Chengdu, 南通 Nantong, 白银 Baiyin, 阜阳 Fuyang | **Gate 2/3** — TLS + header/HTTP fingerprint | Same IP, same moment: `curl` and `urllib` differ only in their TLS/HTTP fingerprint and header order, so the WAF lets one through and stubs the other. Browser headers alone don't fix it (proves it's below the header layer). |
| **`200` but a ~160-byte redirect stub / ~1 KB shell** | many sites where "HTTP 200 ≠ content" (the access map's core warning) | **Gate 1 or 4** — geo-redirect or challenge stub | Why the access map insists on byte-checking, not status codes. |
| **Homepage 200 but sections 404** | 国家能源局 NEA (home 200, `/zwgk` 404) | **Gate 1** — section-level geo-fence | The WAF 404s policy sections for non-CN IPs while leaving the homepage open. |
| **SPA / JS-rendered list (no XHR, deep static, or true datacall)** | 西安/成都/郑州/无锡/南通 big-city portals; 福建 `/zck/` WAS5 search; 海口/聊城/常州 datacall tabs | **Gate 4-ish (client-side rendering, not a security block)** | Not anti-bot at all — the content is rendered by JS/loaded by XHR, so a non-JS fetch sees an empty shell. Fixed by finding the JSON endpoint or a headless render, *not* by a proxy. |
| **429 — rate-limited** | (rare for us as a client; this is what *we serve* — see §4) | **Gate 5** | — |

**Two things this table makes obvious:**
1. **Most of our blocked tier is gate 1 (IP).** The blackholes and 403/412s are an *IP*
   problem — no amount of TLS/header spoofing helps; only a CN-geolocated vantage does.
   This is why the access map's "one lever" is a residential-CN proxy.
2. **A distinct, smaller set is gate 2/3 (fingerprint):** `ccg.gov.cn` (418), and the
   "curl works, urllib stubs" cities (成都/南通/白银/阜阳). These are the ones a
   TLS-impersonation fetch or a browser can unlock *from an IP we already have* — no
   proxy needed. Worth separating in the roadmap because they're cheap wins.

---

## 3. Bypass options that fit our constraints (US droplet + Mac abroad, no CN residential IP)

**Why a Chinese residential IP is hard to get from abroad.** Residential proxies work by
routing you through real consumer devices; the pool of *Chinese* residential exit nodes
is small, legally fraught, and expensive because (a) China's consumer ISPs use
CGNAT and don't hand out clean static residential IPs, (b) most commercial
residential-proxy networks have thin or no China coverage, (c) selling/operating proxy
egress inside China brushes against Chinese law on unlicensed VPN/telecom services, so
reputable vendors avoid it. The **partial substitutes** are: a **CN-region cloud
instance** (Alibaba/Tencent — a datacenter IP *inside* China, which defeats GeoIP but
not a datacenter-ASN block), a **CN mobile/4G proxy** (rarer, pricier, but a true
residential-class IP), or simply **not needing a CN IP** for the fingerprint-only cases.

Ordered from lightest to heaviest:

### 3.1 TLS-impersonation libraries (curl_cffi / curl-impersonate, utls) — the cheap win
**What it is.** A drop-in HTTP client that emits a **real browser's TLS + HTTP/2
fingerprint** without running a browser. **`curl-impersonate`** is a patched curl built
against BoringSSL/NSS with Chrome's/Firefox's exact cipher list, extensions, and HTTP/2
SETTINGS. **`curl_cffi`** is the Python binding (via cffi) — current line **v0.15.x**,
Python ≥3.10 since v0.14 — offering **~37 preset fingerprints** including
version-specific Chrome targets (`chrome124`, `chrome135`, …), Safari, Safari iOS, and
Firefox; you select one with `impersonate="chrome124"`. **utls** is the Go equivalent
(a `crypto/tls` fork with a `ClientHelloID`).
**How it defeats JA3/JA4.** It reproduces the ClientHello *byte-for-byte* like the
target browser (ciphers, extensions incl. GREASE, curves, ALPN) **and** matches the
HTTP/2 settings + header order — so gate 2 and gate 3 see "Chrome," from the same IP,
with no browser process.
**When it still fails.** It does **nothing** for gate 1 (IP/GeoIP — our blackholes and
403/412 stay blocked) and **nothing** for gate 4 (a JS proof-of-work / environment probe
still needs a JS runtime). So it unlocks exactly the **"curl works but urllib stubs"**
cities (成都/南通/白银/阜阳) — plausibly `ccg.gov.cn` *from the residential Mac* (its IP
is fine; only the fingerprint + challenge fail — worth a test, though the JS challenge
may still stop it). **This is the highest ROI, lowest-effort bypass for us**: add a
`curl_cffi` fetch path to `base.py` (the access map already proposes "a `curl`-subprocess
fetch path"; `curl_cffi` is the cleaner in-process version), gated to the handful of
fingerprint-blocked hosts.

### 3.2 Real-browser automation (we already have Claude-in-Chrome) — for the hard cases
**What it is.** Drive an actual Chrome (Claude-in-Chrome, or Playwright/Puppeteer
headful). A real browser passes gates 2, 3, and 4 *for free* — real TLS, real HTTP/2,
it executes the JS challenge and holds the cookie, and it renders SPA/datacall content.
**Pros.** Unlocks the anti-bot + JS-render tiers (MOHRSS Tier D, the datacall big-city
tier, `ccg.gov.cn` if the IP is allowed) that nothing short of a browser can. We already
use Claude-in-Chrome for network inspection (that's how we found the Haidian subdomain
and disproved the "JS-rendered" premise on 24 cities).
**Cons.** **Does not scale** — a browser is ~100–500 MB RAM and seconds per page vs
milliseconds for `urllib`; the 4 GB droplet can run maybe 1–2 headless Chromes, not a
fleet. Still subject to gate 1 (a blocked IP blocks the browser too, unless the browser
egresses through a CN vantage). Best used as a **surgical harvester** for a specific
high-value blocked source (e.g. walk `ccg.gov.cn`'s `/zcfg/` once via the browser and
ingest the results), not as the daily pipeline.

### 3.3 Headless + stealth (Playwright + fingerprint patches)
**What it is.** Headless Chromium via Playwright/Puppeteer with `playwright-stealth` /
`puppeteer-extra-plugin-stealth` / `undetected-chromedriver` / `rebrowser` patches that
hide the `navigator.webdriver` flag, fix headless-specific canvas/WebGL/`chrome`-object
tells, and normalize timings.
**Pros/cons.** Between 3.1 and 3.2: scriptable and lighter than headful, passes gate 4
challenges a headless browser would otherwise fail. But it's an **arms race** (stealth
patches vs detection updates), heavier than `curl_cffi`, and still IP-bound (gate 1).
Overkill unless we hit a challenge that `curl_cffi` can't solve and that we need at
volume.

### 3.4 Proxies & CN-egress cloud (the only real fix for gate 1)
- **Residential/mobile proxy economics.** Commercial residential-proxy pricing is
  ~**$3–15 per GB** of traffic (Bright Data, Oxylabs, Smartproxy tiers); mobile/4G is
  pricier. For a text corpus this is *cheap by bytes* — a policy HTML page is tens of
  KB, so even 100k pages is a few GB. The catch is **China coverage**: general
  residential pools have thin CN presence, and the CN nodes that exist are the priciest
  and least reliable. A per-GB residential plan **with China exit nodes** is the single
  highest-leverage unlock (it flips the entire gate-1 Tier C at once), but verify CN
  coverage before buying, and expect flaky nodes.
- **CN-egress cloud (Alibaba Cloud / Tencent Cloud CN regions).** A VM in a Chinese
  region gives you a China-geolocated IP that defeats GeoIP for many `/zwgk/` sections.
  **Caveats:** (1) it's still a *datacenter* ASN, so sites doing a datacenter-ASN block
  (not just GeoIP) still refuse it; (2) **KYC/legal** — CN cloud accounts require
  real-name registration (a mainland ID / business license, phone, sometimes ICP
  filing) and the ToS prohibit "unauthorized data collection," so this is a compliance
  decision, not just a technical one; (3) cross-border egress from the CN VM back to our
  droplet/DB adds latency and its own filtering. Reasonable as a **read-only fetch
  vantage** we forward from, not as a place to host the app.

### 3.5 Mirror / cache substitutes (no proxy, no browser — often the smartest move)
For blocked *issuers* whose documents are **reprinted elsewhere we can already reach**,
skip the fight entirely:
- **news.cn (Xinhua) / gov.cn (State Council 政策文件库 `/zhengce/zhengceku/`).** The
  access map already documents that the CAC 7-department notice and many central docs
  are mirrored here — **99 doc titles mention 海警** already reach us via news.cn/gov.cn
  even though `ccg.gov.cn` is walled.
- **北大法宝 (PKULaw)** and the **国家法律法规数据库 (national laws DB, `flk.npc.gov.cn`).**
  The authoritative home for laws/regulations, including our highest-demand **DELISTED**
  documents (苏住建规, 深圳听证办法, etc.) that are gone from origin sites. Access/licensing
  terms apply (PKULaw is subscription).
- **archive.org / web.archive.org.** The Wayback Machine often holds a snapshot of a
  page that's now blocked or delisted — reachable from any IP, no challenge. First stop
  for a specific known-URL that went dark.
- **Google / Bing cache.** Increasingly deprecated (Google removed its `cache:`
  operator in 2024), so treat as a long-shot, not a strategy.

### 3.6 What's realistic for us vs. overkill

| Option | Effort | Unlocks | Verdict for this project |
|---|---|---|---|
| **Mirror/cache substitutes** (§3.5) | ~none | blocked *issuers* whose docs are reprinted | **Do first** — free, already partly in use |
| **curl_cffi fetch path** (§3.1) | low (a `base.py` path + host allowlist) | the fingerprint-only hosts (成都/南通/白银/阜阳, maybe ccg from Mac) | **Do — best ROI**; zero infra |
| **Residential-CN proxy w/ verified CN nodes** (§3.4) | medium (vendor + cost + wiring `CRAWL_PROXY`, which `base.py` already supports) | **all of gate-1 Tier C** in one move | **The one big lever** — but vet CN coverage/cost |
| **Claude-in-Chrome surgical harvest** (§3.2) | low per-target, doesn't scale | a *specific* JS/anti-bot source (ccg 政策法规) | **Do occasionally**, per high-value source |
| **CN-egress cloud VM** (§3.4) | medium + **KYC/legal** | GeoIP-gated sections (not ASN blocks) | **Only if** the proxy route fails; compliance review first |
| **Playwright + stealth at volume** (§3.3) | high, arms-race maintenance | challenges curl_cffi can't solve, at scale | **Overkill** unless a specific need appears |

`base.py` is already primed for two of these: it reads **`CRAWL_PROXY`** from the env
(§3.4 wiring is done) and its docstring already anticipates a `curl` fallback path
(§3.1). The gap is a *fingerprint-faithful* fetch, which `curl_cffi` fills better than
raw `curl`.

---

## 4. Applying it to OUR site (chinagovernance.com) — proportionate hardening

**What we already run** (CLAUDE.md "Known Issues"): nginx **per-IP rate-limiting**
(`ratelimit.conf`: `perip` 10 r/s, `rawhtml` 2 r/s, a `harvester` geo-zone throttling
known bulk sources to 1 r/s, 429 on exceed), **robots.txt** disallowing
`/raw_html`/`/cms_files`/`/api`, and site-wide **HTTP Basic Auth** (the site is
currently private). That is gate-5 (rate) + gate-4-lite (a password) — and for our
threat model (a small research site that got hammered by a raw-HTML scraper on a 2-vCPU
box) it is **the right amount**. The problem we actually had was *serving capacity
saturation*, which rate-limiting + Basic Auth already solve.

**What each heavier layer would add, and its cost — being honest that it's likely
overkill:**

- **A JA3/JA4 (TLS-fingerprint) layer.** Would let us *allow browsers, block tools*
  regardless of IP — i.e. block exactly the kind of `urllib`/curl scraper that hit us.
  In practice this needs a fingerprinting-capable front end: **Cloudflare** (free tier
  does JA3/JA4 + bot scoring with near-zero maintenance) or a self-hosted WAF
  (**长亭雷池 SafeLine** is open-source and does semantic + dynamic protection;
  nginx+`ssl_preread`/a Lua module can extract JA3 but you maintain the allowlist
  yourself). **Cost:** self-hosting a fingerprint allowlist is a maintenance treadmill
  (every Chrome release shifts fingerprints; you'll false-positive on Safari/iOS,
  privacy browsers, and legit API users). **Verdict: skip self-hosting; if we ever
  de-privatize and get scraped again, put Cloudflare in front and let its managed bot
  score do this — don't hand-roll JA3 rules.**
- **A JS / behavioral challenge (gate 4).** Cloudflare Turnstile or a challenge page
  would stop non-browser scrapers cold. **Cost:** it breaks our own `/api/v1/stats`
  automation, any legit programmatic reader, and adds latency for humans. **Verdict:
  overkill** — it fights a problem (bot content-theft) we don't really have on a corpus
  that's meant to be *read*; our content is public-interest research, not a moat.
- **Behavioral/honeypot layers.** Even more false-positive-prone and maintenance-heavy;
  no benefit at our scale. **Skip.**

**Proportionate concrete steps (in priority order):**
1. **Keep Basic Auth while private** — it moots everything below (already done).
2. **When/if public again:** front the site with **Cloudflare (free)** for the CDN +
   managed bot/JA3 scoring + caching, instead of hand-building any of it on nginx. This
   also absorbs the raw-HTML scraper problem at the edge (cache + rate-limit before it
   reaches our 2 workers).
3. **Cache `/raw_html/` and heavy endpoints at the edge / longer in-app** so a scraper
   can't saturate the 2 workers even if it gets past rate-limits (the real failure mode
   we hit). Consider `--workers 3` as CLAUDE.md already notes.
4. **Fix the operational nits** the notes flag: serve `robots.txt` and static assets
   from a path nginx (`www-data`) can actually read (the `/root/...` 403 issue), so the
   robots directives we rely on are actually served.
5. **Do not** self-host a JA3/behavioral WAF or add CAPTCHAs. For a small,
   read-oriented research corpus the false-positive cost and maintenance treadmill
   outweigh any benefit — the honest call is that gates 4–5 beyond Cloudflare's managed
   layer are overkill for us.

---

## Appendix — quick reference

**Our fetch stack (`crawlers/base.py`):** Python `urllib` + OpenSSL, dual TLS context
(standard first, then a permissive `SECLEVEL=1` + legacy-renegotiation fallback),
gunzip/deflate decode, per-call `CookieJar`, `CRAWL_PROXY` env hook, browser-ish UA
string. **It is not a browser and has a fixed, non-Chrome TLS/HTTP fingerprint** — the
root cause of every gate-2/3 failure above.

**Status-code cheat sheet (from the access map):** `000` = TCP blackhole (gate 1) ·
`403/406/412` = WAF geo/reputation (gate 1, maybe +2/3) · `521` = origin/anti-bot ·
`418` = CloudWAF challenge (gate 2+4) · `200` + tiny body = redirect/challenge stub, not
content (byte-check always) · home 200 but section 404 = section-level geo-fence.

**Named stacks:** CN — 创宇盾/知道创宇 (Knownsec), 加速乐 Jiasule, 安全狗 Safedog,
长亭雷池 SafeLine (Chaitin), Alibaba/Tencent Cloud WAF; sliders 极验 GeeTest / 网易易盾.
Western analogues — Cloudflare, Akamai Bot Manager, Imperva/Incapsula, DataDome,
PerimeterX/HUMAN.

**Key tools:** `curl-impersonate` / **`curl_cffi` v0.15.x** (Python ≥3.10; ~37
fingerprints incl. `chrome124`/`chrome135`, Safari, Firefox) for TLS impersonation;
**utls** (Go); **Playwright + stealth** / **undetected-chromedriver** for headless;
Claude-in-Chrome for surgical real-browser harvest.

**Fingerprint standards:** **JA3** = MD5 of
`TLSVersion,Ciphers,Extensions,Curves,PointFormats` (order-sensitive, evadable).
**JA4/JA4+** (FoxIO) = sorted ciphers + sorted extensions + signature algorithms,
human-readable `a_b_c`; family incl. **JA4H** (HTTP method/headers/order/cookies),
**JA4S** (server), **JA4T** (TCP). Chrome=BoringSSL, Firefox=NSS,
urllib/curl=OpenSSL → different fingerprints; a `User-Agent` header cannot change any of
them because they're computed below HTTP.
