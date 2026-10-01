# Reaching China's government websites from abroad: a network-vantage decision brief

*A short brief for an outside reader. It explains a concrete infrastructure problem in a
research project, the options for solving it, and the specific questions I'd value a second
opinion on. Written 2026-09-28.*

---

## What the project is

I run a research corpus of **Chinese government policy documents** — published notices,
regulations, readouts, and plans from central ministries down through provinces and cities.
The documents are all **public** (the same pages any web visitor can open); there is no
personal data and no non-public or internal material. The corpus currently holds ~314,000
documents and is used for analysis of how policy is written, cited, and propagated. It runs on
a rented server in New York.

## The problem

A large share of Chinese government websites **block the server's IP address**. The block is
network-level (based on the IP / its geographic location / its being a known datacenter
address), not a login or paywall. From New York, roughly **13 provincial portals and ~250
prefecture-city portals** either drop the connection outright or return an anti-bot challenge
instead of the page. So a meaningful fraction of the government hierarchy is simply unreachable
from where the corpus is hosted, which leaves real coverage gaps (many provinces, and the
foreign-ministry primary record, are thin for exactly this reason).

Most **central** sites and the major first-tier cities are reachable from New York, and much
central content is also mirrored on state media (Xinhua, People's Daily) and a public
national-laws database, so the gap is concentrated in the **provincial and municipal** tier.

## Why a different network vantage would help

Because the block is IP/geography-based, the same request from a **better-positioned IP** gets
through. That points to renting a small server in a location whose IP the Chinese sites don't
block, and routing the blocked requests through it. There are two candidate locations, and they
differ in an important way.

**Hong Kong.** A Hong Kong server is outside mainland China. It requires no mainland business
registration, no ICP filing, and no real-name identity verification — you rent it like any
overseas server (~$5–30/month). Its IP reaches *some* of the currently-blocked sites: the ones
that block based on "this is a US datacenter" reputation rather than a strict "mainland-China-
only" rule. It does **not** reliably reach the sites that allow only mainland IPs.

**Mainland (e.g. Shanghai).** A mainland server has a domestic Chinese IP and would reach
essentially **all** of the blocked sites, including the strict mainland-only ones. It is the
strongest option technically. But provisioning a mainland server requires **real-name identity
verification (实名认证)** — the account and the machine are tied to a verified identity. (An ICP
filing, the thing usually cited as the blocker, is only needed to *host* a website; it is not
required just to make outbound requests. Real-name verification is the actual gate here.)

So the trade is: **Hong Kong is low-friction and low-exposure but only a partial fix; mainland
is a complete fix but ties identity-verified infrastructure inside China to the collection.**

## The alternatives I'm weighing against a proxy at all

- **Public mirrors and APIs.** A lot of the blocked *content* is reachable another way — state
  media reprints, and especially a public national-laws database with an open API that serves
  the authoritative text of laws and regulations from any IP. Where this works it needs no proxy
  at all and is the cleanest route.
- **Commercial residential proxies.** The vendors with the best coverage (Bright Data, Oxylabs)
  explicitly block government (`.gov`) domains and gate access behind corporate KYC, so they
  won't serve this use case. The vendors that will are thinner and route "China" traffic through
  Hong Kong anyway, and the legality of their mainland exit nodes is itself murky. I've largely
  ruled this out.

## The legal / compliance dimension (the part I most want a read on)

I want to be careful and not naive here. My own working assessment:

- Collecting **public** government documents for research, from **abroad**, is about the most
  defensible end of the web-scraping spectrum. It is public data, not personal data, and not a
  protected system.
- China's Data Security Law, the broad "national security data" language in the revised
  Counter-Espionage Law, and data-export rules create **genuine grey areas**, especially around
  bulk aggregation and cross-border transfer of Chinese-origin data. None of this is likely to
  reach a foreign academic reading public policy text, but "unlikely" is not "zero."
- The single biggest risk lever, in my view, is the **vantage**: a mainland, real-name-verified
  server puts identity-linked collection infrastructure *inside* China. Hong Kong and the
  mirror routes keep it outside.

## The specific questions I'd value your view on

1. Is a **mainland, real-name-verified server** an acceptable risk for outbound collection of
   *public* government documents by a foreign researcher — or is that a line you'd advise not
   crossing, and why?
2. Is **Hong Kong plus the public-mirror routes** likely to be *sufficient*, or does the
   strict-mainland-only tier of sites matter enough to justify the mainland option?
3. Is there **legal or compliance exposure** here that I'm underweighting — around the
   Counter-Espionage Law's data provisions, data-export rules, real-name linkage, or Hong Kong's
   own position post-2020?
4. Is there a **better approach** I haven't considered (an institutional/library data-sharing
   route, an in-region partner, a different legal footing)?

## Explicitly out of scope

To keep the question bounded: this is only about *public* documents that are already published
on government websites. It does not involve non-public or internal systems, personal data,
bypassing authentication, or republishing anything beyond the public documentary record.

---

## Update (2026-09-30): tested findings and fixes already implemented

Since drafting the brief I (with an AI coding assistant) tested the key technical claims against
the live sites from the New York server, and implemented the fixes that don't need a proxy at
all. This section records what's now known and done, so a second read can focus on what's left.

### What testing confirmed and what it corrected

- **The national-laws database (`flk.npc.gov.cn`) gives metadata but NOT full text from New
  York.** This is the important correction. The database *does* hold local regulations for the
  blocked provinces (confirmed: Henan local regs are listed and reachable from New York), and we
  already hold ~29,000 of these records as metadata (title, issuer, dates, category, cross-
  references). But the full text is not inline; it sits in DOCX/OFD files on a separate object
  store that is **not reachable from a New York IP** (the detail API's text field is empty, the
  file paths return the site's app shell, and the public-CDN host some guides cite does not
  resolve). So `flk` resolves *citations* and *catalogs what exists* for blocked provinces from
  New York, which is genuinely useful, but it is **not** a full-text route. Full text needs
  either an institutional legal database or a China-adjacent IP (see open questions).
  - Minor but concrete: the category code for "local regulations" that older notes/guides cite
    (`222`) is **dead** in the live API; the real codes are `230/270/290`. Filtering on `222`
    silently returns zero. (Fixed in our crawler.)

- **Fingerprint-blocked sites are now solved in place, no proxy.** Several targets (the Coast
  Guard site `ccg.gov.cn`, and a "curl works but our crawler fails" cluster) are not blocked by
  location at all, they reject our crawler's TLS *fingerprint*. Verified: `ccg.gov.cn` returns
  HTTP 418 to our normal fetch, but returns the real 57 KB page when the request carries a
  genuine Chrome TLS fingerprint. **Implemented and deployed:** the crawler now falls back to a
  browser-fingerprint fetch on exactly these failures, from New York, with no proxy.

- **Mainland server: confirmed avoid.** Nothing in testing changed the earlier conclusion; the
  legal/identity-linkage reasoning stands.

- **Hong Kong: still unmeasured, and the honest answer is "test before buying."** Whether a Hong
  Kong IP is treated as non-mainland and dropped by the same provincial firewalls (making it no
  better than New York for those sites) is an empirical question we have **not** yet measured. A
  new wrinkle from the `flk` finding: a China-adjacent IP might be exactly what unlocks `flk`'s
  full-text object store, which would be a reason to test Hong Kong specifically for that.

### What's now implemented (from New York, no proxy)

1. **Browser-fingerprint fetch fallback** — unblocks the fingerprint-gated `.gov.cn` sites
   (ccg.gov.cn and the same-symptom cluster). Deployed and verified.
2. **National-laws metadata sync** — refreshed the `flk` catalog (local regulations for all
   provinces) to resolve citations against the blocked-province legislation.

### What's left (the refined questions for you)

1. **Full text of blocked provinces' local regulations.** Since `flk` gives metadata only from
   abroad, is **institutional access (北大法宝 / PKULaw, or CNKI government gazettes)** the right
   full-text route? (We may have university-library access to these.) Or is it worth standing up
   a Hong Kong / China-adjacent IP specifically to test whether it can pull `flk`'s full-text
   object store?
2. **Is Hong Kong worth it at all?** Given the mirror + API + fingerprint fixes already recover a
   large share of the content from New York, does the residual justify a Hong Kong box — and does
   your experience say a Hong Kong IP actually gets past the strict provincial firewalls, or is it
   dropped like a foreign datacenter IP?
3. **The central-ministry mirror route.** For the handful of central ministries whose own sites
   are blackholed (housing, civil affairs, natural resources, health), the plan is to harvest
   their documents from the State Council policy repository and state-media reprints rather than
   their origin sites. Any reason that's a worse idea than it looks?
4. Anything else the metadata-vs-full-text distinction changes about your earlier advice.
