# Government-website catalogue — coverage report

Generated 2026-09-09 by `scripts/rnd/discovery/build_catalogue.py` + `verify_catalogue.sh`.
Data: [`gov-website-catalogue.csv`](gov-website-catalogue.csv) (1786 entities). Reachability
byte-checked from the **droplet (NYC)** — the crawl vantage. Residential/curl_cffi differs and
is tracked separately in `source-access-map.md`.

## The 3-D coverage volume

| Dimension | Entities | Crawled | Reachable-uncrawled (yield) | Blocked from droplet | No subdomain / no portal | Unknown |
|---|---|---|---|---|---|---|
| **Central** (Dim C) | 95 | 57 | 14 | 12 | 12 | 0 |
| **Geo portals** (Dim A) | 397 | 115 | 3 | 8 | 265 | 4 |
| **Departments** (Dim A×B) | 1486 | 88 | 91 | 81 | 1228 | 0 |

- **Crawled 260** entities across the volume (57 central + 115 geo + 88 dept).
- **Yield = 108 reachable-uncrawled sites** we could add to the pipeline today
  ([`catalogue-crawl-next.tsv`](catalogue-crawl-next.tsv)): 14 central bodies + 73 provincial
  department subdomains + 3 geo portals.
- **Blocked from the droplet = ~99** (proxy_gated / stub / anti_bot / server_error). Many geo
  `blackhole` (264) are prefecture portals that refuse the datacenter IP but are reachable
  residentially or via curl_cffi. This is the `proxy_gated` tier the residential-proxy lever
  converts wholesale.
- **1046 dept `blackhole`** are departments with NO independent subdomain in that province.
  They publish under the parent portal's 部门/信息公开 path, not a `<slug>.<prov>.gov.cn` host.
  This is expected below provincial rank and is a correct classification, not a gap.

## The 14 reachable central bodies (crawl-next, highest value)

中国工程院 (cae.cn), 中国社会科学院 (cass.cn), 中国科学技术协会 (cast.org.cn), 国家国际发展合作署
(cidca.gov.cn), 国务院台湾事务办公室 (gwytb.gov.cn), 共青团中央 (gqt.org.cn), 国家机关事务管理局
(ggj.gov.cn), 国务院参事室 (counsellor.gov.cn), 国家矿山安全监察局 (chinamine-safety.gov.cn),
国家原子能机构 (caea.gov.cn), 国家疾病预防控制局 (ndcpa.gov.cn), 国家铁路局 (nra.gov.cn),
中国军网 (81.cn), 国家信访局 (gjxfj.gov.cn).

## Method
1. **Reconcile** (zero-network): compose central tree + geo portals + province×dept cross-product,
   join against our 494 crawled sites → `coverage_status`.
2. **URL-per-entity verify**: construct `<slug>.<province>.gov.cn` + portal domains, byte-check
   from the droplet (`<2KB = stub`, follow redirects), classify.
3. Remaining: a Google-keyword tranche for the 26 unknown (no candidate URL) + unaccounted-body
   discovery, and configuring the 90-site yield into the crawl pipeline.
