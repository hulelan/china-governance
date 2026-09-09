#!/usr/bin/env python3
"""Build the unified government-website catalogue from the 3-D entity model.

Composes: central tree (Dim C) + geo portals (Dim A) + generated department
cross-product (Dim A x Dim B), reconciles each against what we already crawl, and
emits (1) docs/working/gov-website-catalogue.csv and (2) a to-verify list of the
unknown rows that carry a candidate URL, for the droplet byte-check sweep.

Idempotent: reads the schema + coverage snapshots, writes the two outputs. Rerun
after a verification pass folds results back in via --verified <tsv>.

Inputs:
  docs/research/gov-entities-schema.yaml      central_tree + dept_taxonomy
  docs/working/china-admin-divisions.csv      geo units (provincial + prefecture)
  docs/working/reconnect-424-urls.csv         provincial/central official_url
  docs/working/source-map-cities.csv          prefecture candidate_domain
  <sites base_url snapshot>                    our crawled site_key->base_url (arg)
"""
import csv, re, sys, os, argparse
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
W = f"{REPO}/docs/working"


def host(url):
    if not url:
        return ""
    h = re.sub(r'^https?://', '', url.strip()).split('/')[0].lower()
    return re.sub(r'^www\.', '', h)


def load_our_sites(path):
    """site rows: site_key|base_url|admin_level -> {host: (site_key, admin_level)} + set of hosts."""
    by_host = {}
    for line in open(path, encoding="utf-8"):
        p = line.rstrip("\n").split("|")
        if len(p) >= 2 and p[1]:
            by_host[host(p[1])] = (p[0], p[2] if len(p) > 2 else "")
    return by_host


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", required=True, help="site_key|base_url|admin_level snapshot")
    ap.add_argument("--verified", help="optional id|status|bytes tsv from a verify sweep to fold in")
    args = ap.parse_args()

    schema = yaml.safe_load(open(f"{REPO}/docs/research/gov-entities-schema.yaml"))
    central = schema["central_tree"]
    depts = schema["dept_taxonomy"]
    our = load_our_sites(args.sites)

    # province name_cn -> portal host, from reconnect-424 provincial rows
    prov_host = {}
    for r in csv.DictReader(open(f"{W}/reconnect-424-urls.csv", encoding="utf-8")):
        if r["level"] == "provincial" and r["official_url"]:
            prov_host[r["institution_cn"].strip()] = host(r["official_url"])
    # reconnect-424 lists only 27 provinces; supplement the 4 mainland ones it omits
    # (all crawled by us) so the reconcile marks them + generates their dept cross-product.
    for name, dom in {"黑龙江省": "hlj.gov.cn", "广东省": "gd.gov.cn",
                      "四川省": "sc.gov.cn", "北京市": "beijing.gov.cn"}.items():
        prov_host.setdefault(name, dom)
    # prefecture city_cn -> candidate_domain, from source-map-cities
    city_host = {}
    for line in open(f"{W}/source-map-cities.csv", encoding="utf-8"):
        if line.startswith("#") or line.startswith("city_cn"):
            continue
        c = line.rstrip("\n").split(",")
        if len(c) >= 3 and c[2]:
            city_host[c[0].strip()] = host(c[2])

    verified = {}
    if args.verified:
        for line in open(args.verified, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) >= 2:
                verified[p[0]] = (p[1], p[2] if len(p) > 2 else "")

    rows = []                       # catalogue rows
    def emit(eid, dim, level, name_cn, counterpart, url, notes=""):
        h = host(url)
        site_key, cov = "", "unknown"
        if h and h in our:
            site_key, _ = our[h]
            cov = "crawled"
        if eid in verified:         # a verify sweep result overrides
            st, _ = verified[eid]
            cov = st if cov != "crawled" else "crawled"
        rows.append({"id": eid, "dimension": dim, "level": level, "name_cn": name_cn,
                     "counterpart_central_body": counterpart or "", "candidate_url": url,
                     "site_key": site_key, "coverage_status": cov, "notes": notes})

    # --- Dim C central tree (already carries url + status) ---
    for r in central:
        h = host(r.get("official_url"))
        cov = r.get("coverage_status") or "unknown"
        sk = r.get("site_key") or (our.get(h, ("", ""))[0] if h in our else "")
        if h in our and our[h]:
            cov = "crawled"
        if r["id"] in verified:
            cov = verified[r["id"]][0] if cov != "crawled" else cov
        rows.append({"id": r["id"], "dimension": "central", "level": "central",
                     "name_cn": r["name_cn"], "counterpart_central_body": r.get("counterpart_central_body") or "",
                     "candidate_url": r.get("official_url") or "", "site_key": sk,
                     "coverage_status": cov, "notes": r.get("reorg_note") or ""})

    # --- Dim A geo portals + Dim A x Dim B department cross-product ---
    provs = []
    for r in csv.DictReader(open(f"{W}/china-admin-divisions.csv", encoding="utf-8")):
        if r["level"] == "provincial":
            provs.append(r)
            ph = prov_host.get(r["name_cn"], "")
            purl = f"https://{ph}" if ph else ""
            emit(f"geo.{r['name_en'].lower().replace(' ','')}", "geo", "provincial",
                 r["name_cn"] + "人民政府", None, purl, "province portal")
            # department cross-product for this province
            if ph:
                for d in depts:
                    name = d["name_cn_provincial"].replace("{unit}", r["name_cn"])
                    cand = f"https://{d['slug']}.{ph}"          # <slug>.<province>.gov.cn
                    emit(f"{r['name_en'].lower().replace(' ','')}.{d['slug']}", "dept",
                         "provincial", name, d.get("counterpart_central_body"), cand,
                         f"alt=https://{ph}/{d['slug']}/")
        elif r["level"] == "prefecture":
            ch = city_host.get(r["name_cn"], "")
            curl = f"https://{ch}" if ch else ""
            emit(f"geo.pref.{r['name_cn']}", "geo", "prefecture",
                 r["name_cn"] + "人民政府", None, curl, "prefecture portal")

    # --- write catalogue ---
    outp = f"{W}/gov-website-catalogue.csv"
    fields = ["id", "dimension", "level", "name_cn", "counterpart_central_body",
              "candidate_url", "site_key", "coverage_status", "notes"]
    with open(outp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # --- write to-verify list (unknown rows with a candidate URL) ---
    tv = f"{W}/catalogue-to-verify.tsv"
    n_tv = 0
    with open(tv, "w", encoding="utf-8") as f:
        for r in rows:
            if r["coverage_status"] == "unknown" and r["candidate_url"]:
                f.write(f"{r['id']}\t{r['candidate_url']}\n")
                n_tv += 1

    # --- summary ---
    from collections import Counter
    by_dim_cov = Counter((r["dimension"], r["coverage_status"]) for r in rows)
    print(f"catalogue: {len(rows)} entities -> {outp}")
    print(f"to-verify: {n_tv} rows -> {tv}")
    print("by dimension x coverage:")
    for (dim, cov), n in sorted(by_dim_cov.items()):
        print(f"  {dim:8} {cov:20} {n}")


if __name__ == "__main__":
    main()
