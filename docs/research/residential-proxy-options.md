# Reaching the datacenter-IP-blocked CN gov sites — proxy & vantage options

**Question:** ~13 province portals + ~250 prefecture-city portals + a handful of central
bodies blackhole or WAF-403 our DigitalOcean NYC droplet's IP (the "Tier C" of
`docs/working/source-access-map.md`). The operator lives abroad and has **no Chinese
residential IP**. What's the best way to reach these sites for a research corpus — and
when is a proxy actually worth it versus a cheaper substitute?

**Companion docs (read first):** `docs/working/source-access-map.md` (the living Tier A–F
reachability record) and `docs/research/access-blocking.md` (the five-gate model of how
these blocks work). This doc extends §3.4 of access-blocking.md with **current (2026)
vendor pricing, the KYC/legality reality, and a ranked buy-or-don't recommendation.**

**Last researched:** 2026-09-27 (WebSearch, vendor pages + third-party pricing trackers).

---

## 0. TL;DR — the honest call

1. **Don't buy a China residential proxy first.** The premier vendors (Bright Data,
   Oxylabs) explicitly **block government (`.gov`) domains on all networks** and gate
   residential access behind **company KYC** — so the exact thing we need (`.gov.cn`
   scraping) is the exact thing their compliance team refuses. The vendors that *will*
   sell it (IPRoyal, Shifter, Decodo self-serve) have thin/HK-routed "China" pools of
   uncertain reliability against WAF'd `.gov.cn`, and the legality of CN-mainland
   residential egress is a genuine grey area (China licenses only authorized-operator
   VPN/telecom egress).

2. **Do this instead, in order:**
   - **(a) Exhaust the free mirror route** (news.cn / gov.cn 政策文件库 / `flk.npc.gov.cn`
     national laws DB, which has a working JSON API / archive.org). This already covers a
     large share of the *documents* the blocked issuers publish — we just don't need their
     origin sites for those.
   - **(b) Stand up a Hong Kong cloud VPS** (Alibaba Cloud / Tencent Cloud HK, or any HK
     VPS) as a second fetch vantage. **No ICP filing, no mainland KYC**, ~$5–30/mo, and HK
     egress reaches many CN-gov sites our NYC IP can't. This is the highest-leverage,
     lowest-friction unlock and the one concrete infra change worth making.
   - **(c) Keep the residential-Mac + `curl_cffi` surgical harvest** for the
     fingerprint-gated stragglers (ccg.gov.cn class) that even an in-region IP won't fix.

3. **A CN-mainland residential/mobile proxy is a last resort**, only for the specific
   province/city portals that a HK VPS *still* can't reach after (a)+(b), and only if those
   remaining targets carry enough citation demand to justify the cost + compliance risk.
   Budget ~$50–150/mo for a small metered plan from a permissive vendor, expect flaky nodes,
   and read the legality section before committing.

---

## 1. What a proxy does and does not solve (don't skip this)

Per `access-blocking.md` §0, a request passes five gates. **Our Tier C blocks are almost
all Gate 1 (IP/GeoIP/ASN).** A proxy only changes Gate 1 — the vantage IP. It does nothing
for the other gates:

| Our block type (from the access map) | Gate | Does a CN/HK proxy fix it? |
|---|---|---|
| `000` blackhole (惠州, MOHURD, Sichuan/Shanxi/… provinces) | 1 (IP) | **Yes** — needs a CN-geo (or often HK) IP |
| `403/406/412` WAF geo-block (河南/安徽, 湖北/甘肃, 云南 sections) | 1 (IP reputation/geo) | **Usually** — if the proxy IP is CN-geo *and* not itself a flagged range |
| `418` CloudWAF challenge (ccg.gov.cn) | 2+4 (TLS fingerprint + JS) | **No** — needs `curl_cffi`/browser, not an IP |
| `988-byte anti-bot shell` (MOHRSS) | 4 (JS challenge) | **No** — needs a cookie-solving/browser fetch |
| "curl works, urllib stubs" (成都/南通/白银/阜阳) | 2/3 (fingerprint) | **No** — `curl_cffi`, already the plan |
| SPA / JS-rendered lists (西安/海口 datacall) | client-side render | **No** — headless render or JSON endpoint |

So a proxy is the **one lever for the gate-1 tier only** — real, and large (it flips ~13
provinces + the city long tail at once), but it is not a general "unblock everything" tool.
Budget the fingerprint/JS tiers separately (they're the cheap `curl_cffi` wins that need no
proxy at all).

---

## 2. Residential / mobile proxies — the CN reality

### 2.1 The pricing (2026, per-GB)

For a text corpus this is *cheap by bytes* — a policy HTML page is tens of KB, so even
100k pages is a few GB. Headline rates (general residential, all-geo):

| Vendor | PAYG /GB | Committed /GB (100 GB+) | Pool claim | Gov domains? | KYC? |
|---|---|---|---|---|---|
| **Bright Data** | ~$8 (promo $4) | ~$3 | 150M+ | **Blocked (all networks)** | **Company KYC required** (new zones after 2026-07-07) |
| **Oxylabs** | $8 | ~$6 at 100 GB | 175M+ | Restricted use-policy | Business verification |
| **Decodo (ex-Smartproxy)** | $4 | $2.75 (100 GB) → $2 (1 TB) | 115M+ | Self-serve, laxer | Lighter |
| **IPRoyal** | $7 → $1.75 bulk (non-expiring) | ~$1.75 | 2.5M+ CN claim | Self-serve, laxer | Lighter |
| **Shifter** | (per-IP/plan) | — | **11M+ "mainland CN"** claim | Self-serve | Lighter |

Bytes are not the problem. **The problem is CN coverage quality + who will sell it for
`.gov.cn`.**

### 2.2 The two things that actually decide it

**(a) "China" pools are mostly thin or HK-routed.** Multiple 2026 reviews warn that
*"technically supports China" ≠ real mainland routing* — many providers route through Hong
Kong or nearby regions and market it as China, and those routes "behave inconsistently on
mainland-targeted platforms" under load. China's consumer ISPs use CGNAT and don't hand out
clean residential IPs, so genuine mainland exit nodes are the priciest and least reliable in
any pool, and a large advertised pool count "doesn't guarantee usability" (flagged subnets
get blocked immediately). Only vendors with direct CN-ISP partnerships (Shifter markets an
11M mainland pool; IPRoyal a ~2.5M CN pool) plausibly have real mainland egress — and those
claims are unverified against WAF'd `.gov.cn` specifically. **Verdict: you must test CN
nodes against a real Tier-C target before committing, and expect flakiness.**

**(b) The vendors with the best pools won't sell it for our use case.** This is the
decisive finding:
- **Bright Data**: residential access is *"granted only to registered companies, and only
  after the compliance team reviews and approves your KYC submission… approval is never
  automatic, instant or self-serve,"* and — critically — *"government websites are blocked
  across all networks,"* including residential. A foreign research corpus scraping `.gov.cn`
  is precisely what their compliance gate is built to reject.
- **Oxylabs**: similar business-verification + acceptable-use posture.
- **Budget/self-serve vendors (Decodo, IPRoyal, Shifter)**: lighter gating, so *technically*
  purchasable, but that laxness is the flip side of thinner compliance — and they're the
  ones with the shakier CN routing.

So the market splits into "good pool, won't serve us" and "will serve us, uncertain pool."
Neither half is a clean win, which is why the proxy route ranks **below** the HK-VPS and
mirror routes for this project.

---

## 3. Legality & KYC reality (be honest, no evasion recipe)

- **Using a proxy is not inherently illegal** in most jurisdictions; legality turns on where
  you are, the target's ToS, the data type, and whether you bypass an access control. Reading
  *public* government policy pages for research is about the most defensible end of that
  spectrum. But the CN-gov WAF geo-block *is* an access control of a sort, and their ToS are
  rarely permissive — so this sits in a grey area, not a clearly-licit one.
- **The CN-mainland egress itself is the legally fraught part.** China permits only VPN/
  telecom egress *provided by authorized basic-telecom operators*; unlicensed commercial
  VPN/gateway egress inside China is not legal and is what enforcement targets (unlicensed
  *commercial offerings*, not isolated individual browsing). A residential-proxy network's
  CN exit nodes are, in effect, unlicensed egress operating inside China — which is exactly
  why reputable vendors either avoid CN or route "China" through Hong Kong. As the *buyer
  abroad* you're a step removed, but you're paying for egress of contested legality, and the
  node-owner consent chain on cheap pools is often opaque.
- **KYC for the buyer:** Bright Data/Oxylabs require company registration + compliance
  review; a personal research project may not clear it (and even if it did, the gov-domain
  block still applies). Budget vendors ask far less, which is precisely the compliance
  trade-off.
- **Bottom line:** buying CN-mainland residential egress from abroad for `.gov.cn` scraping
  is *doable* via a permissive vendor but sits in a legal/ToS grey zone with an opaque
  consent chain. For a **research** corpus, that's a real reason to prefer the in-region-
  *cloud* and *mirror* routes, which have cleaner footing.

---

## 4. CN cloud egress — mainland vs. Hong Kong

### 4.1 Mainland (Alibaba Cloud / Tencent Cloud CN regions) — **effectively closed to us**

A VM in a Chinese region has a China-geolocated IP that defeats GeoIP for many `/zwgk/`
sections. **But provisioning one as a foreigner is the wall:**
- **International users cannot deploy in mainland regions via alibabacloud.com** — you must
  create a separate account on **aliyun.com using a China-based business license and local
  identity verification.** No mainland company / representative-office registration → no
  mainland instance.
- **ICP filing** (needed to *serve* a site, and entangled with account standing) requires,
  for a foreign entity with no mainland branch, a *Registration Certificate of Permanent
  Representative Office* as the business-license equivalent, plus domain real-name
  verification. This is a company-formation-grade lift, not a signup.
- Even past KYC, a mainland VM is still a **datacenter ASN**, so sites doing an ASN block
  (not just GeoIP) still refuse it — you'd unlock the geo-only subset, not everything.

**Verdict: not realistic for a solo foreign researcher.** Skip.

### 4.2 Hong Kong region — **the sweet spot, and the one infra change worth making**

- **No ICP filing, no mainland KYC.** Cloud resources in China (Hong Kong) or any
  non-mainland region are explicitly outside MIIT's ICP regime — *"if your cloud resources
  are in nodes in regions such as China (Hong Kong)… an ICP filing is not required."* You
  provision it like any overseas VPS, with a normal international account and a credit card.
- **HK egress reaches CN-gov sites NYC can't.** HK connects to the mainland over standard
  international BGP with low latency, and (per our own access map's premise) HK "often
  reaches CN-gov sites that NYC can't." It's outside the Great Firewall, so *outbound* to
  `.gov.cn` is normal internet — the win is that a HK IP is geographically/relationally
  "closer" and less likely to be on a US-datacenter blocklist than AS14061 NYC. It is **not**
  a mainland IP, so it won't beat a strict *CN-only* GeoIP allowlist — but many of our Tier-C
  blocks are ASN/US-datacenter-reputation blocks, not CN-only allowlists, so HK flips a
  meaningful fraction.
- **Cost & friction:** ~$5–30/mo for a small HK VPS (Alibaba/Tencent HK, or a generic HK
  provider); our `base.py` already reads `CRAWL_PROXY` from env, so wiring the droplet to
  fetch Tier-C hosts through a HK squid/http proxy is a small change (no code change needed
  here — just config, which is out of scope for this read-only doc, but the hook exists).
- **Caveat:** HK is a *partial* substitute — measure which Tier-C hosts it actually unlocks
  (re-run `reachability_sweep.sh` *from the HK box*) before assuming coverage. Some
  blackholes will persist because they're CN-only allowlists.

---

## 5. Cheaper substitutes we should prefer (often the smartest move)

For blocked *issuers* whose documents are reprinted somewhere reachable, skip the fight:

- **news.cn (Xinhua) / gov.cn 政策文件库 (`/zhengce/zhengceku/`)** — the access map already
  documents that the CAC 7-department notice and many central docs are mirrored here; **99
  doc titles mention 海警 already reach us via news.cn/gov.cn** even though ccg.gov.cn is
  walled. Central-issuer content is largely capturable this way with **no proxy**.
- **国家法律法规数据库 (`flk.npc.gov.cn`)** — the authoritative national laws/regulations DB,
  **reachable from any IP** and it has a **working JSON API** (`flk.npc.gov.cn/api/`,
  paginated; doc paths prefixed with `wb.flk.npc.gov.cn`). ~22.5k laws/regulations; community
  scrapers (e.g. GitHub `twang2218/law-datasets`, `muztag/laws`) confirm the pattern. This is
  the right home for the highest-demand **DELISTED** docs (苏住建规, 深圳听证办法) that are gone
  from origin sites — a far better target than fighting a province WAF for the same text.
- **北大法宝 (PKULaw)** — the commercial authority for laws/regs; subscription/licensing
  applies. Use for delisted/historical items `flk` doesn't cover.
- **archive.org / Wayback** — reachable from any IP, no challenge; first stop for a specific
  known-URL that went dark or is now geo-blocked.
- **Residential-Mac + `curl_cffi` surgical harvest** — already proven (ccg.gov.cn: 16 docs).
  Zero marginal cost, handles the fingerprint tier that no proxy fixes. Doesn't scale to a
  nightly pipeline, but perfect for occasional high-value pulls.

**When does a proxy actually earn its cost?** Only when, after (a) exhausting mirrors +
`flk` for the *documents*, and (b) standing up a HK vantage for the *origin sites*, there
remains a set of **CN-only-allowlisted province/city portals** with **real citation demand**
that neither route reaches. Given the citation-demand analysis in CLAUDE.md (the long-tail
cities are low-demand-per-city, and the highest-demand missing docs are delisted → belong in
`flk`/法宝, not a province WAF), that residual set is probably **small** — which is why the
honest recommendation is "don't bother with a CN residential proxy yet."

---

## 6. Comparison table (ranked for THIS project)

| Option | ~Monthly cost | Setup friction | Unlocks | Legal footing | Verdict |
|---|---|---|---|---|---|
| **Mirror route** (news.cn/gov.cn/**flk.npc.gov.cn** API/archive.org) | $0 | ~none (crawler work) | blocked *issuers'* documents; delisted laws | clean (public reprints) | **Do first** |
| **Hong Kong cloud VPS** as 2nd vantage | **$5–30** | low (VPS + `CRAWL_PROXY`) | ASN/US-reputation-blocked Tier C (a meaningful fraction of provinces + cities) | clean (no ICP/KYC) | **Do — best infra ROI** |
| **`curl_cffi` from Mac/droplet** | $0 | low (`base.py` path) | fingerprint tier (ccg, 成都/南通/白银/阜阳) | clean | **Do** (separate from proxy) |
| **CN-mainland residential/mobile proxy** (IPRoyal/Shifter/Decodo) | **$50–150** metered | medium (vet CN nodes, wire proxy) | CN-only-allowlisted gate-1 hosts HK can't reach | **grey** (contested CN egress, opaque consent) | **Last resort**, only for a demonstrated residual |
| **Bright Data / Oxylabs residential** | $300+ (100 GB tiers) | high (company KYC) | — (they **block .gov + gate residential**) | vendor refuses use case | **Won't work — skip** |
| **CN-mainland cloud VM** (Aliyun) | $10–50 + formation | **very high** (mainland biz license, real-name, ICP) | geo-only gate-1 subset | requires mainland entity | **Not feasible for a solo foreigner — skip** |

---

## 7. Recommendation

1. **Stand up a Hong Kong VPS as a second fetch vantage** (~$5–30/mo, no KYC/ICP). Re-run
   `scripts/rnd/discovery/reachability_sweep.sh` *from the HK box* against the Tier-C list to
   measure exactly which provinces/cities it unlocks, then route only those hosts through it
   via the existing `CRAWL_PROXY` hook. This is the single best cost/friction/legality trade.
2. **Harvest the blocked issuers' documents from mirrors** — wire `flk.npc.gov.cn`'s JSON
   API (national laws DB) and lean on news.cn/gov.cn reprints + archive.org for delisted
   items. This recovers the *content* without needing the origin sites at all.
3. **Add the `curl_cffi` fetch path** (already the plan in access-blocking.md §3.1) for the
   fingerprint-gated stragglers — orthogonal to the proxy question, cheap, no infra.
4. **Only if** a demonstrated residual of high-citation-demand, CN-only-allowlisted portals
   survives 1–3, buy a **small metered plan from a permissive vendor** (IPRoyal / Shifter /
   Decodo), **test its CN nodes against a real Tier-C target first**, and read §3 on the
   legal grey area before committing. Do **not** start here, and do **not** expect Bright
   Data/Oxylabs to serve `.gov.cn` at all.

---

## Sources

- [Bright Data — residential network access policy](https://docs.brightdata.com/proxy-networks/residential/network-access) · [KYC compliance](https://brightdata.com/trustcenter/kyc) · [KYC FAQ (residential)](https://brightdata.com/trustcenter/kyc-faq-residential-proxy-network) · [pricing](https://brightdata.com/pricing/proxy-network/residential-proxies)
- [Oxylabs residential pricing](https://oxylabs.io/pricing/residential-proxy-pool) · [Oxylabs China proxy](https://oxylabs.io/location-proxy/china) · [Oxylabs Hong Kong proxy](https://oxylabs.io/location-proxy/hong-kong)
- [Decodo (ex-Smartproxy) residential pricing](https://decodo.com/proxies/residential-proxies/pricing) · [IPRoyal pricing 2026](https://use-apify.com/blog/iproyal-pricing-plans-2026) · [IPRoyal China proxy](https://iproyal.com/proxies-by-location/asia/china/)
- [Shifter — China residential (11M+ mainland claim)](https://shifter.io/location/china) · [Shifter Hong Kong](https://shifter.io/location/hong-kong)
- [DataImpulse — best China proxies 2026 (mainland vs HK routing caveats)](https://dataimpulse.com/blog/best-proxy-providers-china/) · [Pixelscan — best Chinese proxies 2026](https://pixelscan.net/blog/best-chinese-proxies/)
- [Alibaba Cloud — ICP filing overview](https://www.alibabacloud.com/help/en/icp-filing/basic-icp-service/user-guide/overview) · [ICP filing for overseas enterprises](https://www.alibabacloud.com/help/en/icp-filing/basic-icp-service/product-overview/icp-filing-application-for-enterprises-outside-the-chinese-mainland) · [server/access check (HK = no ICP)](https://help.aliyun.com/en/icp-filing/basic-icp-service/user-guide/icp-filing-server-access-information-check)
- [MS Advisory — ICP License in China 2026 (foreign company guide)](https://msadvisory.com/icp-license-china/) · [AppInChina — guide to Alibaba Cloud in China](https://appinchina.co/a-guide-to-alibaba-cloud-in-china/)
- [Chinafy — HK VPS & China connectivity](https://www.chinafy.com/blog/what-is-vps-hosting-in-hong-kong-does-it-make-websites-faster-in-china)
- [Law.asia — VPN compliance in China](https://law.asia/vpn-compliance-china/) · [AllBright — VPN compliance in China](https://www.allbrightlaw.com/EN/10475/6408019c394498c4.aspx) · [Sesame Disk — China VPN rules 2026](https://sesamedisk.com/china-vpn-regulations-2026/)
- [国家法律法规数据库 flk.npc.gov.cn](https://flk.npc.gov.cn/) · [twang2218/law-datasets (API pattern)](https://github.com/twang2218/law-datasets/blob/main/law-and-regulations/README.md) · [muztag/laws](https://github.com/muztag/laws)
