# Press-release and press-conference coverage of the central bodies we crawl

Built 2026-11-25. Vantage: the droplet (NYC). Every "reachable" below is a byte check
(bytes, CJK characters, article-shaped links), never an HTTP status.

- Machine pass: `scripts/rnd/discovery/press_section_audit.py` → `press-conference-coverage.csv`
  (55 central sites, taken from the crawler code by `build_section_registry.collect`).
- Hand pass on top of it: `scripts/rnd/discovery/probe_section.py <list-url>` for each
  candidate, which runs the govcms lister and body extractor and counts rows already held.
- The gaps are filed in `data/known_missing_sections.yaml` and shown on `/admin/sections`.

## What the machine pass can and cannot see

It reads each homepage and keeps links whose text names a press section (新闻发布会, 发布厅,
发言人, 吹风会, 答记者问, 新闻发布). That finds a candidate on 25 of 55 homepages.
It MISSES sections the homepage does not link in text: it found nothing for `samr`
(whose 新闻发布厅 exists at `/xw/xwfbt/`), `gov` (`/lianbo/fabu/`) and `nbs`
(`/sj/xwfbh/`). So "no press link on homepage" in the CSV means "not found by this
method", and the 22 sites in that state below are unaudited, not clean (8 more
homepages answered with a stub or a 403).

## Audit table

`crawled` = do we hold documents from that section. Counts are documents held under the
section's path on 2026-11-25 before this branch.

| site | press section | reachable | crawled before | action on this branch |
|---|---|---|---|---|
| samr 市场监管总局 | 新闻发布厅 `/xw/xwfbt/` | yes, 329 rows | **no (0)** | **added** (`xwfbt`); scratch crawl 275 docs, 271 with body, to 2026-11-24 |
| gov 国务院 | 新闻发布 `/lianbo/fabu/` (JSON feed, 702 rows, 2022-10-) | yes | **no (0)** | **added** (`FEEDS['fabu']`); scratch crawl 571 article rows, 570 with body |
| gov 国务院 | 国务院政策例行吹风会 `/xinwen/<year>zccfh/<n>/` | yes | no | left: per-briefing mini-sites, need a walker (75 rows) |
| mfa 外交部 | 发言人表态 / 例行记者会 `/fyrbt_673021/` | yes, newest row today | **no (0)**: wrong path AND site not scheduled | **fixed + added**, site put in the nightly |
| mfa 外交部 | 吹风会 `/web/wjdt_674879/cfhsl_674891/` | yes | no | left: rows not in a shape the lister reads |
| mofcom 商务部 | 新闻发言人谈话 `/xwfb/xwfyrth/` | yes, 641 rows | 1 | **added** (`xwfyrth`) |
| mofcom 商务部 | 新闻发布会 `/xwfbh/` → `/xwfbzt/<year>/<slug>/` | yes, 488 conferences | no | left: mini-sites, need a walker |
| nea 国家能源局 | 新闻发布 `/xwfb/` | yes (datasource JSON) | **no (0)**: wrong paths AND not scheduled | **fixed + added**, 60 rows on a non-deep run |
| mot 交通运输部 | 新闻发布会 `/xinwen/xinwenfabuhui/` | yes, 16 rows, 9-10k chars | 2 | **added** (govcms section) |
| nbs 国家统计局 | 新闻发布会 `/sj/xwfbh/` | yes, 19 rows, 5-12k chars | 3 | **added** (govcms section) |
| pbc 人民银行 | 新闻发布 `/goutongjiaoliu/113456/113469/` | yes | **yes (5,590, newest 2026-11-21)** | none needed |
| cac 网信办 | 网信发布 `/wxzw/wxfb/` (its release column; no separate press hall found) | yes | **yes (479, newest 2026-11-20)** | none needed |
| ndrc 发改委 | 新闻发布 `/xwdt/xwfb/` | yes, 25 rows | no (0) | left: `ndrc.py` hard-codes `/xxgk/zcfb/<key>/`; small code change |
| mee 生态环境部 | 新闻发布 `/ywdt/xwfb/` (incl. 例行发布会实录) | yes, ~2.9k chars | no (0) | left: probably one `SECTIONS` entry; mee's own lister not run on it |
| miit 工信部 | 新闻发布会 `/xwfb/xwfbh/` | yes, 22 rows, 6-12k chars | partly (9 of 22, via the search API) | left: crawler is category-id based |
| spb 国家邮政局 | 新闻发布会 `/gjyzj/c106927/` | yes, 9 rows, ~4.9k chars | 3 | left: likely one govcms entry, untested through `crawl_site` |
| csrc 证监会 | 新闻发布会 `/csrc/c100029/`, 答记者问 `/csrc/c100028/` | yes | 6, incidentally | left: script-rendered lists; crawler reads 政策法规库 only |
| mem 应急管理部 | 新闻发布会 `/xw/xwfbh/` | yes | no | left: mini-site per conference |
| moe 教育部 | 新闻发布会 `/jyb_xwfb/xw_fbh/` | yes (26 KB) | no | left: crawler reads 7 WAS-search channels, none is this column |
| mct 文旅部 | 新闻发布会 `/hdjl/xwfbh/` | yes (31 KB) but 0 article links | no | left: script-rendered |
| mwr 水利部 | 新闻发布会 `/xw/xwfbh/` | yes (29 KB) but 0 article links | no | left: 在线访谈 mini-sites, one answered a 695 B stub |
| cas 中科院 | 例行发布会 `/xwfbh/` | yes (11 KB) but 0 article links | no | left |
| moj 司法部 | 新闻发布 `/zwgkxwfbh/` | yes (42 KB); lister finds only footer links | no | left |
| spc 最高法 | 新闻发布会 `/zixun/gengduo/26.html`, 实录 `/39.html` | yes (16 KB) | no | left: article URLs `/zixun/xiangqing/<id>.html` not listed by govcms |
| mod 国防部 | 例行记者会 / 发言人谈话 `/gfbw/xwfyr/` | yes (53 KB) | no | left: site configured but not scheduled; URL shape not listed |
| sasac 国资委 | 新闻发布 `/n2588025/` | yes (35 KB), 1 article link | no | left: script-rendered |
| chinatax 税务总局 | 新闻发布 `/chinatax/n810219/` | yes (67 KB), 0 article links | no | left |
| npc_dbgz 全国人大 | 新闻发布会 `/c2/c12834/` | yes (9 KB), 2 links | no | left |
| nfsra 粮储局 | 新闻发布 = the news column `/html/xinwen/` | yes, 25 rows, ~1k chars | no (0) | left: a news column rather than a press hall |
| cma 气象局 | 新闻发布 → a 2011 在线直播 page | yes | no | left: the homepage link is to a legacy page |
| ncha 文物局 | 新闻发布会 `/vipchat/` | **stub, 365 B** | no | blocked or script-only |
| nia 移民局 | 新闻发布 `/n741435/` | **stub, 735 B** | no | blocked or script-only |
| caac, most, mof, nda, npc, sic | homepage itself is a stub from the audit's fetch (157 B to 2.5 KB) | n/a | n/a | not assessable from the homepage; nda/mof/sic crawl fine by section path |
| mva, spp | homepage 403 | n/a | n/a | not assessable |
| chinapeace, cnao, cnipa, cnsa, cppcc, dangyuan, ipc_court, mara, natcm, neac, nhsa, nrta, nsfc, saac, safe, sastind, sfa, tc260 | no press link found on the homepage | n/a | n/a | **unaudited**, see the caveat above |

Net: of the 30 reachable press sections in the table, **2 were crawled before** (pbc, cac),
**7 are added on this branch** (samr, gov 新闻发布, mfa, mofcom 发言人谈话, nea, mot, nbs), and
21 are filed as known-missing with what each needs.

## The same audit for non-press sections named in the task

| site | section | finding | action |
|---|---|---|---|
| gov | 要闻 `/yaowen/liebiao/` | list page is a shell; rows come from `YAOWENLIEBIAO.json` (rolling 400, about 4 weeks) | **added**; 288 article rows, 273 with body. 107 feed rows are tv.cctv.com videos and are skipped |
| samr | 广告监管司 通知公告, 标准技术司 征求意见 | second listing template (`ajax分页`, 10 rows) and second body container (`zt_xilan_07`) | **added** both; 26 docs (22 with body) and 430 listed (short notices, the drafts are attachments) |
| mofcom | 领导人活动 `/xwfb/ldrhd/` | same API as 政策发布 | **added**; 669 rows, 4 held |
| mofcom | 首页新闻发布 `/syxwfb/` | works (3,247 rows) | **left on purpose**: homepage mix incl. reprinted central news; decide before a 3k backfill |
| nda | 地方动态 / 媒体声音 / 数据局动态 `/sjj/swdt/…` | same template as the crawled columns | **added**; 279 / 500 / 140 listed |
| nda | 局领导活动 `/sjj/jgsz/jld/<leader>/llhldhd/` | one list per leader | left: paths not enumerated |
| miit | 科技司 文件发布 `/jgsj/kjs/wjfb/` | script-rendered via a different jpaas webId | left: needs a column walker |
| cac | 网信发布 `/wxzw/wxfb/` | **already crawled** (479 docs); its articles live at `/YYYY-MM/DD/c_<id>.htm` so a path check cannot see them | none |
| nea | 最新文件 / 通知 / 公告 / 解读 `/policy/*.htm` | script-rendered from `ds_<id>.json` | **added** via a datasource fallback in govcms; 232 docs non-deep |

## Stalled sites

| site | newest held | cause | class | action |
|---|---|---|---|---|
| sh (Shanghai) | 2026-01-20 | The list template moved `<span class="time">` inside the `<a>`. `_parse_listing` required `</a>` first, so every page parsed to 0 rows; `0 new` was read as "year fully held" and the section stopped. Nightly log: seven sections, each `2026: 0 new … fully held`, exit 0. Two more defects under it: the newest-year link resolved to the first nav tab (`/nw2407/`) for every section, and 沪府办发 2025/2026 live in a directory whose name starts with a space (`/%20hfbf2026/`). | **broken crawler** | **fixed**. Scratch crawl: 134 new documents, 133 with body. The next nightly recovers them by itself |
| 36kr | 2026-08-04 | Since 2026-08-05 `36kr.com/feed` (and every other 36kr URL) returns HTTP 200 with a 25 KB text/html challenge page: any User-Agent, with or without curl_cffi Chrome impersonation. The crawler logged `Found 0 articles` and exited 0 every night. | **blocked host**, reported as success | crawler now exits non-zero on an empty feed. Real fix needs a non-datacenter vantage |
| zj (Zhejiang) | 2026-05-09 | TLS handshake times out on every `*.zj.gov.cn` listing URL from NYC (urllib 3 tries, then curl_cffi). Runs Monday only, under a 600 s cap, by design; 2026-11-23 run reached the second department and stored nothing. | **blocked host** + weekly schedule | none; needs a residential or HK vantage |
| moe | 2026-04-10 | Not in `daily_sync.sh` at all. Run by hand in April, and only for section `a16`: the other six configured sections (政策法规司 414 rows, 规范性文件 228, 部令 82, then 发展规划司 121 / 高等教育司 73 / 部文 198 list pages, roughly 6,000 rows in all) have never been crawled. The crawler works from the droplet (a16 lists 339 rows, bodies fetch). a16 itself has nothing newer than April in MOE's search index. | **never scheduled** | added to the nightly as a weekly (Monday) run. Under the 1800 s cap that drains the six sections over several weeks; a one-time `--db` backfill (about 3 h) does it at once |
| jiemian | (none) | no dates by design (see CLAUDE.md) | n/a | none |

Two more of the same kind, found by the registry rather than by anyone noticing:
`cnipa`, `dangyuan` and `mod` are configured in `govcms.SITES` and appear in no line of
`daily_sync.sh`. They are listed in `tests/test_section_registry.py` with that reason so
the gap is explicit; nothing was changed for them.

## Deploy notes for the sections added here

Each new section has no held rows, so its first run walks its whole listing. Do the
first run into a separate DB and merge, then let the nightly keep it current. See the
branch report for the exact commands and sizes.
