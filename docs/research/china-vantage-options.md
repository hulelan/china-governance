# China Vantage Options — reaching geo-blocked CN gov sites for authorized crawling

**Date:** 2026-08-22
**Scope:** Evaluation only (no signups, purchases, or credentials). Purpose: pick the
cheapest, most maintainable vantage that makes mainland-China government policy sites
reachable for our automated server-side crawler.
**Use case:** authorized research crawling of **public** CN gov policy documents. No
evasion of security controls, no login-walled content, no captcha/2FA defeat.

---

## 0. The problem, precisely

Our crawler runs on a DigitalOcean droplet with a **New York datacenter IP**
(`104.236.88.45`, ASN AS14061 DigitalOcean). Some mainland gov sites block it. Observed
block flavors:

- **(a) TCP blackhole / connection refused** — SYN dropped, connection reset/timeout.
- **(b) App-layer WAF 403** — HTTP 200 handshake but a 403 / geo-block interstitial.
- **(c) IPv6-only** — no IPv4 route to the content host at all.

The crawler already supports an optional proxy: `crawlers/base.py` reads `CRAWL_PROXY`
and installs a `urllib.request.ProxyHandler({"http": proxy, "https": proxy})`. So any
**HTTP(S) proxy with user:pass in the URL** (`http://user:pass@host:port`) plugs in with
**zero code changes**. (Caveat: `urllib`'s `ProxyHandler` does **not** natively speak
`socks5://` — a SOCKS-only endpoint would need `PySocks` + a small monkeypatch. Prefer
an HTTP-proxy endpoint, which all the major residential vendors offer.)

### The critical technical frame (verified)

**WAF geo/ASN blocking keys on the SOURCE IP's geolocation/ASN, not on latency.** This
is the whole ballgame. Independent reporting confirms CN gov sites increasingly run a
"reverse Great Firewall": CDN/WAF infrastructure **splits traffic by geography** —
domestic IPs get the real content, foreign IPs get dropped, 403'd, or routed to a dead
edge. One study/press estimate puts it at **~60% of government websites** blocking
foreign access ([SCMP](https://www.scmp.com/news/china/diplomacy/article/3344100/chinas-reverse-great-firewall-quietly-blocking-global-access-official-data),
[Oxford Journal of Cybersecurity](https://academic.oup.com/cybersecurity/article/12/1/tyag005/8465357)).

**Consequence for the shortlist:** the only thing that changes the identity the WAF sees
is a **mainland-China IP** or a **China residential IP**. "CN2 GIA optimized routing"
(premium China-Telecom-routed HK/SG/Tokyo nodes) improves latency and packet loss but
**still hands you a foreign datacenter IP** — it does **not** change your geolocation/ASN,
so it does **not** defeat a geo/ASN block. Confidence: **high** for block flavors (a) and
(b). CN2 GIA can only help a **latency/packet-loss-only** failure or a block keyed
specifically to the US/DigitalOcean ASN that a *different foreign* ASN happens to dodge —
a narrow and unreliable case.

- **Flavor (a) blackhole & (b) WAF-403:** need a **mainland or CN-residential** egress IP.
- **Flavor (c) IPv6-only:** orthogonal — you need an egress with **IPv6** connectivity
  (many proxy pools and the droplet itself are IPv4-first). A mainland VPS with native
  IPv6, or a residential proxy pool that supports IPv6 targets, is required. Verify per
  vendor; do not assume any option below solves (c) unless it advertises IPv6.

---

## 1. Comparison table

| Option | Mainland IP? | Defeats geo-block? | Fits `CRAWL_PROXY`? | Cost ballpark | Setup effort | Compliance / ToS risk | Reliability for automation |
|---|---|---|---|---|---|---|---|
| **China residential proxy** (Bright Data / Oxylabs / Smartproxy / IPRoyal) | **Yes** (real CN residential IPs) | **Yes** (a)+(b) | **Yes, directly** (HTTP proxy w/ auth) | **~$4–8/GB**, pay-per-GB | **Low** (set env var) | Medium: vendor ToS + KYC; you must stay to public/no-login | Good, but rotating IPs; per-request cost |
| **Mainland cloud VPS** (Alibaba / Tencent, e.g. Beijing/Shanghai region) | **Yes** (datacenter CN IP) | **Mostly** (a)+(b)* | Yes (run crawler on it, or use as forward proxy) | **~$5–20/mo** small ECS | **High** (real-name verify, acct) | **High**: real-name registration required; PRC jurisdiction | High (dedicated host) |
| **Managed "China IP" reseller** (HolHost Beijing, SinoServers, etc.) | **Yes** (claims Beijing local IP) | Likely (a)+(b) if IP is genuinely CN | Yes (host crawler or proxy) | **~$29–89/mo** | Medium | **High + trust risk**: small/obscure vendor, opaque ownership | **Unknown/unverifiable** |
| **CN2 GIA host** (BandwagonHost / Riven, HK/SG/Tokyo) | **No** (foreign DC IP) | **No** (latency only) | Yes (but pointless for geo-block) | **~$50–90/mo or /yr** | Medium | Low | High, but doesn't solve the problem |
| **Consumer VPN "China" location** (AdGuard, ZoogVPN) | **Doubtful** (often CN2-routed foreign edge) | **No / unreliable** | **Poorly** (client apps, not auth proxies) | ~$3–13/mo | Low | Medium: ToS often bar automation | **Poor** for server automation |

\* Datacenter CN IPs can themselves be reputation-flagged by some WAFs; a residential IP
is the strongest identity. But a mainland *datacenter* IP still clears pure
geo-by-country blocks, which is the dominant flavor here.

---

## 2. Option-by-option assessment

### 2.1 China residential proxy services — **best fit for our architecture**

**What it is:** a pool of real end-user (residential ISP) IPs inside mainland China. You
send requests to the vendor's proxy endpoint with credentials; it egresses from a CN
residential IP. Because it's an **HTTP proxy with user:pass auth**, it drops straight
into `CRAWL_PROXY` — no code change.

**Availability of mainland-CN IPs (verified):**
- **Bright Data** — explicitly offers **mainland China residential** proxies; site claims
  **~343,000 China IPs**, city/state/ZIP targeting free, country code `cn`
  ([brightdata.com/locations/cn](https://brightdata.com/locations/cn)). Four networks:
  residential, ISP, datacenter, mobile.
- **Oxylabs / Smartproxy (Decodo) / IPRoyal** — all market China residential coverage,
  but I could **not pull hard current China-pool sizes/pricing** from search (results
  were generic). Confidence: **medium** that all three have *some* CN residential
  inventory; **low** on the depth/quality of that inventory. **Verify at signup/trial.**

**Pricing (verified, Bright Data, Aug 2026):** residential **~$8/GB pay-as-you-go**,
falling to **~$5/GB** on committed monthly tiers (e.g. ~$499/mo → 141 GB, ~$1,999/mo →
798 GB); a promo code has been observed near ~$4/GB
([Bright Data pricing pages/reviews](https://use-apify.com/blog/bright-data-pricing-guide-2026)).
Others are broadly in the **$4–8/GB** band (IPRoyal is usually the cheapest, but its CN
depth is the least certain). **Per-GB is the key cost lever**: gov HTML pages are small
(tens–hundreds of KB), so a bounded crawl of the blocked sites is likely **single-digit
to low-tens of GB → a few $10s–$100s**, not a monthly server. Great for an
**intermittent/occasional** crawl of the blocked tail (which is exactly our pattern —
most sites already crawl fine from the droplet).

**ToS / compliance:** major vendors (Bright Data especially) run **KYC + use-case review**
and gate residential proxies; their AUP prohibits fraud, login/credential abuse, PII
scraping, and circumventing security controls. **Public, unauthenticated gov policy
documents are within normal "public data collection" use**, which these vendors
explicitly support — but you should expect to declare the use case and stay strictly on
public/no-login pages. Confidence: **medium-high** this is permitted; the KYC step is a
real (if modest) friction.

**Reliability for automation:** good, with caveats — residential IPs **rotate** (sticky
sessions are available but cost/complexity rises), success rate is high but not 100%, and
you pay per byte so a runaway crawl costs money. For our **bounded, low-volume** blocked
tail this is a fine tradeoff.

**IPv6-only sites (flavor c):** verify the vendor supports IPv6 targets; not guaranteed.

### 2.2 Mainland-China cloud VPS (Alibaba Cloud / Tencent Cloud)

**Does crawling outbound from a mainland VPS require ICP filing? No — important nuance.**
ICP filing (备案) is required to **HOST a public website/service** whose domain resolves
to a mainland server. It is triggered by "domain resolution points to a mainland server
**and a web service is activated**"
([Alibaba Cloud ICP docs](https://www.alibabacloud.com/help/en/icp-filing/basic-icp-service/product-overview/what-is-an-icp-filing),
[Chinafy](https://www.chinafy.com/blog/a-2025-guide-to-icp-licences-in-china-do-i-need-an-icp-license-for-my-website)).
**Making outbound HTTP requests from the box (our crawler) is not "hosting a site," so
ICP filing does not apply.** Confidence: **high**.

**But real-name registration DOES apply — separately from ICP.** To **purchase** any
mainland-region ECS instance, Alibaba/Tencent require **real-name identity verification**
(individual or corporate) under PRC law, at the account level
([Alibaba real-name notice](https://www.alibabacloud.com/en/notice/Alicloud-Real-name)).
So you can crawl outbound without ICP, but you **cannot get the mainland box at all**
without handing over verified real-name/KYC identity and accepting PRC jurisdiction over
the account. That is the real compliance cost here, and it's **high** relative to a proxy.

- **Cost:** small mainland ECS is cheap (~$5–20/mo; mainland regions run ~18–32% below
  Alibaba's international regions).
- **HK region avoids verification** — but **HK is not mainland**, so a HK ECS IP is a
  *foreign* IP and **won't defeat the geo-block** (same failure as CN2 GIA). Don't use HK
  to solve (a)/(b).
- **Fit:** you'd either run the crawler *on* the mainland box, or stand up a forward
  proxy (tinyproxy/squid) there and point `CRAWL_PROXY` at it. Both work; the proxy
  pattern keeps our pipeline on the droplet.
- **Verdict:** technically the strongest identity (dedicated mainland IP, flat cost, no
  per-GB) but the **real-name KYC + PRC-jurisdiction** burden is the highest of any
  option, and it's a standing monthly asset to maintain. Good if crawl volume grows large
  enough that per-GB proxy costs dominate; otherwise overkill.

### 2.3 Managed "China IP" resellers (HolHost et al.)

**HolHost exists and does advertise the thing.** Its "VPS in Mainland China" page offers
**unmanaged KVM VPS in Beijing with a "local Chinese IP,"** 4 plans **~$29–89/mo**,
PayPal/crypto/cards, deployed in 24h, and correctly notes ICP is needed only "to host a
public website"
([holhost.com/vps-mainland-china.php](https://www.holhost.com/vps-mainland-china.php)).
Plausible on its face.

**Trust/reliability risk is the problem.** These are small, thinly documented resellers
with opaque ownership; the HolHost page even shows an anomalous "2004–2026" copyright.
Whether the "Beijing IP" is a genuine, stable, unflagged mainland IP — and whether the
box survives, gets its IP rotated, or the vendor vanishes — is **unverifiable** from the
outside. There is also a KYC-avoidance angle (crypto payment, no real-name) that is
*convenient* but means you're trusting an unaccountable intermediary with your crawl
traffic. Confidence in reliability: **low**. Fine as a **cheap experiment**, not as
production infrastructure.

### 2.4 CN2 GIA hosts (BandwagonHost / Riven Cloud, HK/SG/Tokyo)

Apply the frame: **CN2 GIA is a premium *routing* product (China Telecom's GIA backbone),
not a mainland IP.** A BandwagonHost HK plan gives you an **Equinix-HK datacenter IP** —
foreign geolocation, foreign ASN — with great ping to China
([BandwagonHost HK](https://bandwagonhostreviews.com/hk-vps.php); HK plans ~$50–90+).

- **Defeats geo-block (a)/(b)? No.** The WAF sees a foreign IP regardless of how fast the
  packets arrive.
- **When it *would* help:** only (i) a **latency/packet-loss-only** failure — the site
  actually serves foreign IPs but our NYC path is so lossy it times out; or (ii) a block
  keyed narrowly to the **US/DigitalOcean ASN** that a HK ASN happens not to be on. Both
  are minority cases and neither is reliable.
- **Verdict:** do **not** buy this to solve geo-blocks. Only relevant as a latency
  fallback if we ever diagnose a *pure* latency failure (rare).

### 2.5 Consumer VPNs with a "China" location (AdGuard VPN, ZoogVPN)

Unsuitable for server-side automated crawling:

- **Their "China" endpoint is usually not a real mainland IP.** AdGuard VPN's own testing
  says it **does not work in mainland China**; providers' "get a Chinese IP" pages are
  marketing and frequently resolve to CN2-routed *foreign* edges, not residential/mainland
  IPs ([AdGuard China page](https://adguard-vpn.com/en/server-locations/china-vpn.html)).
  Genuine mainland VPN egress is rare because it requires in-country infrastructure.
- **Architecture mismatch:** these are **client apps** that capture the whole machine's
  routing, not authenticated HTTP-proxy endpoints. They don't cleanly become a
  `CRAWL_PROXY` value, they'd hijack the droplet's other traffic, and they lack per-request
  auth/rotation.
- **ToS:** consumer VPN AUPs commonly prohibit automated scraping / commercial data
  collection.
- **Verdict:** skip.

---

## 3. Ranked recommendation

For **"automated server-side crawling of public CN gov docs, minimizing compliance
burden and cost,"** ordered best-first:

1. **China residential proxy (start with Bright Data; price-check IPRoyal/Oxylabs/Smartproxy).**
   *Only option that both (a) defeats geo/ASN blocks with a genuine CN identity and (b)
   drops into our existing `CRAWL_PROXY` with zero code change; pay-per-GB (~$4–8/GB) fits
   our intermittent blocked-tail pattern for tens of dollars, no standing server, no
   real-name/ICP.* The compliance cost is a one-time KYC/use-case declaration — keep to
   public, no-login pages. **This is the recommendation.**

2. **Mainland cloud VPS (Alibaba/Tencent, mainland region) — if volume grows.**
   *Strongest, cheapest-at-scale identity (dedicated mainland IP, flat ~$5–20/mo, no
   per-GB), and — nuance — outbound crawling needs **no ICP filing**. The catch is
   mandatory **real-name registration** + PRC jurisdiction on the account, the highest
   compliance burden here. Escalate to this only if per-GB proxy spend starts to dominate.*

3. **Managed CN-IP reseller (HolHost) — cheap experiment only.**
   *A ~$29/mo Beijing box could work and sidesteps cloud KYC, but small/opaque vendors
   carry real trust and reliability risk; treat as a disposable test, never core infra.*

**Explicitly not recommended:** CN2 GIA HK/SG/Tokyo hosts (foreign IP — doesn't defeat
the block; latency-only) and consumer VPNs (no real mainland IP, wrong architecture, ToS).

---

## 4. Cheapest first test to run

**Single cheapest test:** take a **Bright Data (or any CN-residential) free trial / small
pay-as-you-go top-up**, get the HTTP proxy endpoint with `cn` (ideally city) targeting,
and run **one** blocked site through our existing plumbing — no code change:

```bash
# 1. Baseline from the droplet (expect a block: timeout / 403 / reset)
curl -sS -o /dev/null -w "%{http_code} %{time_total}s\n" \
  --max-time 30 "https://<blocked-cn-gov-host>/<path>"

# 2. Same request via the CN-residential proxy (expect 200 + real HTML)
export CRAWL_PROXY="http://<user>:<pass>@<vendor-cn-endpoint>:<port>"
curl -sS -x "$CRAWL_PROXY" -o /tmp/via_proxy.html \
  -w "%{http_code} %{time_total}s\n" --max-time 60 \
  "https://<blocked-cn-gov-host>/<path>"

# 3. Confirm it's real content, not an interstitial
head -c 2000 /tmp/via_proxy.html

# 4. End-to-end through the actual crawler (proves CRAWL_PROXY wiring):
CRAWL_PROXY="$CRAWL_PROXY" python3 -m crawlers.govcms --site <blocked-site> --discover
```

Pick 1–2 known-blocked hosts to test — e.g. the datacenter-IP-blocked province portals
noted in `CLAUDE.md` (huizhou / yangjiang) and any WAF-403 provincial policy section.
**Cost of the test: effectively free-to-a-few-dollars** (trial credit / a fraction of a
GB). If the 403/timeout flips to a 200 with real HTML, the residential-proxy path is
validated and we wire `CRAWL_PROXY` into the blocked-site crawls (ideally scoped to just
the blocked tail, to cap per-GB spend).

**If the proxy test fails on a given site** (still blocked/interstitial), that site is
likely doing something beyond geo (login wall, JS challenge, or true IPv6-only). Diagnose
before spending more: an IPv6-only host needs an IPv6-capable egress; a JS/login wall is
out of scope for authorized public-doc crawling.

---

## 5. Confidence & open uncertainties

- **High confidence:** the core frame (geo/ASN keyed on source IP, not latency; CN2 GIA
  gives a foreign IP and won't defeat geo-blocks); ICP applies to hosting, not outbound;
  mainland ECS needs real-name verification; Bright Data has real mainland-CN residential
  IPs and fits `CRAWL_PROXY`; consumer-VPN "China" endpoints are unreliable/unsuitable.
- **Medium confidence:** exact per-GB pricing (moves with promos/commitments — treat
  $4–8/GB as a band, verify at signup); Oxylabs/Smartproxy/IPRoyal **China-pool depth**
  (marketed, not independently verified here).
- **Low confidence / unverifiable:** HolHost's actual IP quality, stability, and vendor
  longevity; whether any given residential pool covers **IPv6** targets; whether a
  specific blocked site will accept a residential vs. datacenter CN IP (some WAFs
  additionally reputation-score) — **only the live test in §4 settles these.**
- **Not tested here (constraint: evaluation only):** no signups/purchases were made; all
  pricing and availability are from vendor/press pages as of Aug 2026 and should be
  re-confirmed before committing spend.

### Sources
- [SCMP — reverse Great Firewall blocking foreign access](https://www.scmp.com/news/china/diplomacy/article/3344100/chinas-reverse-great-firewall-quietly-blocking-global-access-official-data)
- [Oxford Journal of Cybersecurity — government geo-blocking logics](https://academic.oup.com/cybersecurity/article/12/1/tyag005/8465357)
- [Bright Data — China proxy location page](https://brightdata.com/locations/cn)
- [Bright Data pricing guide 2026](https://use-apify.com/blog/bright-data-pricing-guide-2026)
- [Alibaba Cloud — what is ICP filing](https://www.alibabacloud.com/help/en/icp-filing/basic-icp-service/product-overview/what-is-an-icp-filing)
- [Chinafy — do I need an ICP license](https://www.chinafy.com/blog/a-2025-guide-to-icp-licences-in-china-do-i-need-an-icp-license-for-my-website)
- [Alibaba Cloud — real-name registration notice for mainland ECS](https://www.alibabacloud.com/en/notice/Alicloud-Real-name)
- [HolHost — VPS in Mainland China](https://www.holhost.com/vps-mainland-china.php)
- [BandwagonHost HK VPS review (CN2 GIA)](https://bandwagonhostreviews.com/hk-vps.php)
- [AdGuard VPN — China location page](https://adguard-vpn.com/en/server-locations/china-vpn.html)
