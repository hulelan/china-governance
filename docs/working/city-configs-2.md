# City configs — chunk 2 (middle third of NEW cities)

Built 2026-09-04. Vantage: droplet NYC IP (104.236.88.45). Method = byte-check +
follow redirects (`scripts/rnd/discovery/reachability_sweep.sh`), then per-reachable
listing fetches to identify the govcms article-URL dialect. **No document crawling,
no DB writes.** Dialects reference `crawlers/govcms.py` letters A–T (`_ART_*_RE`).

## Scope

Middle third of `coverage=NEW` cities in `source-map-cities.csv` file order:
**115 units** (indices 115–229 of the 345 NEW rows).

## Headline

- **34 reachable** distinct city portals (real content >2 KB from the NYC IP).
- **13 config-ready** (reachable + a server-rendered listing in a known dialect).
- The other ~21 reachable are JS/Hanweb-datacall listing pages, `post_`/ASP
  (Guangdong gkmlpt family), or bespoke shapes — reachable but **not** a govcms
  dialect without new code.
- ~78 blackhole/WAF/stub — proxy-gated (matches the ~72% datacenter-IP-block rule).

`crawl_site` runs every `_ART_*_RE` over each section page and keeps whatever
matches, so a config needs only `base_url` + `sections`; the dialect note is
informational. All 13 sections below were byte-verified to server-render article
anchors (count in comment).

---

## Config-ready blocks (paste into `crawlers/govcms.py` SITES)

### Tier 1 — verified server-rendered policy/section pages (7)

```python
    "yushu": {  # 玉树州 (Qinghai) — t-date dialect A (/xxgk/.../YYYYMM/tYYYYMMDD_ID.html)
        "name": "Yushu (玉树藏族自治州)", "base_url": "http://www.yushu.gov.cn",
        "admin_level": "municipal",
        "sections": ["/xxgk/qwfb/gsgg/"],  # 公示公告, ~20 t-date/page
    },
    "shuozhou": {  # 朔州 (Shanxi) — t-date dialect A on the 信息公开 subdomain
        "name": "Shuozhou (朔州市)", "base_url": "http://szxxgk.shuozhou.gov.cn",
        "admin_level": "municipal",
        "sections": ["/szfxxgk/fdzdgknr/gzwj/gfxwj/",   # 规范性文件, ~18
                     "/szfxxgk/fdzdgknr/gzwj/zfwj/",     # 政府文件
                     "/szfxxgk/fdzdgknr/zcjd/"],         # 政策解读, ~20
    },
    "quanzhou": {  # 泉州 (Fujian) — t-date dialect A (.htm). Policy 目录 pages are JS;
        # the 泉州要闻 + 信息公开目录 news list server-renders. Run --discover for more.
        "name": "Quanzhou (泉州市)", "base_url": "http://www.quanzhou.gov.cn",
        "admin_level": "municipal",
        "sections": ["/zfb/xxgk/zfxxgkzl/qzdt/qzyw/"],   # ~15 t-date/page
    },
    "yuxi": {  # 玉溪 (Yunnan) — ymd8 dialect Q (/yxs/<sec>/YYYYMMDD/<numid>.html)
        "name": "Yuxi (玉溪市)", "base_url": "http://www.yuxi.gov.cn",
        "admin_level": "municipal",
        "sections": ["/yxs/tzgg/", "/yxs/tzggsy/"],      # 通知公告, ~21 each
    },
    "suihua": {  # 绥化 (Heilongjiang) — hexmon dialect I (/sh/<sec>/YYYYMM/<32hex>.shtml)
        "name": "Suihua (绥化市)", "base_url": "http://www.suihua.gov.cn",
        "admin_level": "municipal",
        "sections": ["/sh/gfxwj/zfxxgk.shtml",           # 规范性文件
                     "/sh/zfxxgkzd/zfxxgk.shtml"],       # 重点公开
    },
    "huaihua": {  # 怀化 (Hunan) — hexmon dialect I (/huaihua/c<col>/YYYYMM/<32hex>.shtml).
        # Listing pages are the TRS zfxxgkMultiList.shtml column indexes.
        "name": "Huaihua (怀化市)", "base_url": "http://www.huaihua.gov.cn",
        "admin_level": "municipal",
        "sections": ["/huaihua/c100231/zfxxgkMultiList.shtml",   # ~6
                     "/huaihua/c100238/zfxxgkMultiList.shtml"],  # ~15
    },
    "laiwu": {  # 莱芜 (now a Jinan district; static archive) — /art/ dialect B
        # (/col116924/art/YYYY/art_116924_ID.html). Low value: merged into Jinan 2019.
        "name": "Laiwu (莱芜)", "base_url": "http://www.laiwu.gov.cn",
        "admin_level": "district",
        "sections": ["/col116924/index.html"],           # ~61 art_ links
    },
```

### Tier 2 — homepage-rendered (section index pages are JS; use `/` + run `--discover`) (5)

Each homepage server-renders a large recent-docs list in the noted dialect; the
deeper `/zwgk/` section pages are Hanweb-datacall (JS, 0 static links). `/` alone
gives the recent policy window (the same pattern as the `caac` config). Run
`python3 -m crawlers.govcms --site <k> --discover` to find any static leaf lists.

```python
    "liuzhou": {  # 柳州 (Guangxi) — t-date dialect A (.shtml). Homepage ~204 t-date links
        # (www + dept subdomains). Deeper /zwgk/fdzdgknr/ is JS.
        "name": "Liuzhou (柳州市)", "base_url": "http://www.liuzhou.gov.cn",
        "admin_level": "municipal", "sections": ["/"],
    },
    "fuzhou_fj": {  # 福州 (Fujian capital) — t-date dialect A (.htm). Homepage ~66 t-date.
        "name": "Fuzhou (福州市)", "base_url": "http://www.fuzhou.gov.cn",
        "admin_level": "municipal", "sections": ["/"],
    },
    "hanzhong": {  # 汉中 (Shaanxi) — hexmon dialect I (/hzszf/.../YYYYMM/<32hex>.shtml).
        # Homepage ~84 hexmon links; /hzszf/xwzx/gsgg/ index is JS.
        "name": "Hanzhong (汉中市)", "base_url": "http://www.hanzhong.gov.cn",
        "admin_level": "municipal", "sections": ["/"],
    },
    "taizhou_js": {  # 泰州 (Jiangsu) — /art/ dialect B, hex ids (/xwzx/tzgg/art/YYYY/art_<32hex>.html).
        # Homepage ~41 art links. NOTE key suffixed _js to avoid the Zhejiang 台州 clash.
        "name": "Taizhou (泰州市)", "base_url": "http://www.taizhou.gov.cn",
        "admin_level": "municipal", "sections": ["/"],
    },
    "yantai": {  # 烟台 (Shandong) — /art/ dialect B (numeric art_99959_ID + hex variants).
        # Homepage ~79 own-domain art links; /col/col*/index.html is JS.
        "name": "Yantai (烟台市)", "base_url": "http://www.yantai.gov.cn",
        "admin_level": "municipal", "sections": ["/"],
    },
```

### Tier 3 — tentative (dialect shape matches, article rendering needs a live test) (1)

```python
    "shijiazhuang": {  # 石家庄 (Hebei; abbreviation domain sjz) — hbuuid dialect S shape
        # (/zfxxgk/columns/<UUID>/index.html), SAME CMS as the `hebei` province config.
        # Column index pages returned 0 static links (JS), but the homepage renders ~91
        # article links. VERIFY with --discover before wiring into the nightly.
        "name": "Shijiazhuang (石家庄市)", "base_url": "http://www.sjz.gov.cn",
        "admin_level": "municipal",
        "sections": ["/zfxxgk/columns/0f9f6cdc-69ca-4a72-bd39-66b553cc0674/index.html",
                     "/zfxxgk/columns/6ac6458a-126e-47ce-a1eb-12930061231e/index.html",
                     "/"],
    },
```

---

## Reachable-but-not-govcms (needs new code / other crawler) — 21

| City | Domain | Why not a govcms config |
|---|---|---|
| 抚顺 fushun | www.fushun.gov.cn | `/YYYYMMDD/<uuid>.html` + `govInfoPub.html` JS — new dialect (uuid) |
| 朝阳 chaoyang | www.chaoyang.gov.cn | `glist.html` JS lists (辽宁 Chaoyang) |
| 新乡 xinxiang | www.xinxiang.gov.cn | `/zwgk/public/column/…` JS column API |
| 淮北 huaibei | www.huaibei.gov.cn | `/zwgk/public/column/…` JS column API |
| 无锡 wuxi | www.wuxi.gov.cn | `/zfxxgk/…/index.shtml` lists are JS-rendered |
| 淮南 huainan | www.huainan.gov.cn | `/zwgk/…/index.html` lists are JS-rendered |
| 淮安 huaian | www.huaian.gov.cn | `/cmsweb/zwgk/…?topic=` Hanweb JS |
| 菏泽 heze | www.heze.gov.cn | listing JS (Hanweb datacall) |
| 芜湖 wuhu | www.wuhu.gov.cn | `/xwzx/tzgg/` list is JS-rendered |
| 盘锦 panjin | www.panjin.gov.cn | `/zwgk/` list is JS-rendered |
| 营口 yingkou | www.yingkou.gov.cn | `/zfxxgk/` returns 3.6 KB JS shell |
| 淄博 zibo | www.zibo.gov.cn | `/gongkai/channel_c*/` Hanweb datacall JS |
| 泰安 taian | www.taian.gov.cn | /art/ dialect B, but own col unknown — needs --discover |
| 盐城 yancheng | www.yancheng.gov.cn | /art/ dialect B, but own col unknown — needs --discover |
| 聊城 liaocheng | www.liaocheng.gov.cn | `channel_…?open=` Hanweb + `doc_<hex>.html` JS |
| 白银 baiyin | www.baiyin.gov.cn | `/zwgk/` 10.9 KB JS shell (no static article links) |
| 海口 haikou | www.haikou.gov.cn | `/` 2.9 KB shell — JS/near-proxy (Hainan) |
| 石嘴山 shizuishan | www.shizuishan.gov.cn | `/` 4.6 KB shell — JS/near-proxy (Ningxia) |
| 茂名 maoming | www.maoming.gov.cn | `post_<id>.html` — Guangdong **gkmlpt** family, not govcms |
| 清远 qingyuan | www.qingyuan.gov.cn | `/zfxxgk/list.asp?s=…` ASP — Guangdong gkmlpt family |
| 湛江 zhanjiang | www.zhanjiang.gov.cn | `post_<id>.html` — Guangdong gkmlpt family (KNOWN_BROKEN) |

`chengdu` (2.3 KB, sec=302) and `haikou` (2.9 KB) sit just over the 2 KB floor but
serve anti-bot/JS shells, not real listings — treat as not-yet-reachable.

---

## Full reachability table (all 115 in chunk order)

status: REACHABLE = real content >2 KB · STUB = <2 KB shell/dead redirect ·
WAF = 403/406/412 · BLACKHOLE = 000 TCP geo-fence · other(code) = as noted.
`dialect` filled only where a govcms config was produced.

| # | City | pinyin | domain (real) | status | dialect / note |
|---|---|---|---|---|---|
| 1 | 忻州市 | xinzhou | www.xinzhou.gov.cn | BLACKHOLE | — |
| 2 | 怀化市 | huaihua | www.huaihua.gov.cn | REACHABLE 88KB | **I** (config: huaihua) |
| 3 | 怒江州 | nujiang | www.nujiang.gov.cn | BLACKHOLE | — |
| 4 | 恩施州 | enshi | www.enshi.gov.cn | BLACKHOLE | — |
| 5 | 成都市 | chengdu | www.chengdu.gov.cn | STUB 2.3KB | anti-bot shell (was `waf`) |
| 6 | 扬州市 | yangzhou | www.yangzhou.gov.cn | WAF403 | proxy-gated |
| 7 | 承德市 | chengde | www.chengde.gov.cn | BLACKHOLE | — |
| 8 | 抚州市 | fuzhou(JX) | www.fuzhou.gov.cn ✗ | COLLISION | domain is 福州's; 抚州(Jiangxi) real domain differs — verify |
| 9 | 抚顺市 | fushun | www.fushun.gov.cn | REACHABLE 145KB | uuid — new dialect |
| 10 | 拉萨市 | lhasa | www.lhasa.gov.cn | BLACKHOLE | — |
| 11 | 攀枝花市 | panzhihua | www.panzhihua.gov.cn | BLACKHOLE | — |
| 12 | 文山州 | wenshan | www.wenshan.gov.cn | BLACKHOLE | — |
| 13 | 新乡市 | xinxiang | www.xinxiang.gov.cn | REACHABLE 64KB | JS column API |
| 14 | 新余市 | xinyu | www.xinyu.gov.cn | BLACKHOLE | — |
| 15 | 无锡市 | wuxi | www.wuxi.gov.cn | REACHABLE 145KB | JS lists |
| 16 | 日喀则市 | shigatse | www.shigatse.gov.cn | BLACKHOLE | — |
| 17 | 日照市 | rizhao | www.rizhao.gov.cn | BLACKHOLE | — |
| 18 | 昆明市 | kunming | www.km.gov.cn | STUB 0b | dead redirect |
| 19 | 昌吉州 | changji | www.changji.gov.cn | other(422) | proxy-gated |
| 20 | 昌都市 | qamdo | www.qamdo.gov.cn | BLACKHOLE | — |
| 21 | 昭通市 | zhaotong | www.zhaotong.gov.cn | BLACKHOLE | — |
| 22 | 晋中市 | jinzhong | www.jinzhong.gov.cn | BLACKHOLE | — |
| 23 | 晋城市 | jincheng | www.jincheng.gov.cn | BLACKHOLE | — |
| 24 | 普洱市 | puer | www.puer.gov.cn | BLACKHOLE | — |
| 25 | 景德镇市 | jingdezhen | www.jingdezhen.gov.cn | BLACKHOLE | — |
| 26 | 曲靖市 | qujing | www.qujing.gov.cn | BLACKHOLE | — |
| 27 | 朔州市 | shuozhou | szxxgk.shuozhou.gov.cn | REACHABLE 153KB | **A** (config: shuozhou) |
| 28 | 朝阳市 | chaoyang | www.chaoyang.gov.cn | REACHABLE 123KB | JS glist |
| 29 | 本溪市 | benxi | www.benxi.gov.cn | BLACKHOLE | — |
| 30 | 来宾市 | laibin | www.laibin.gov.cn | BLACKHOLE | — |
| 31 | 松原市 | songyuan | www.songyuan.gov.cn | BLACKHOLE | — |
| 32 | 林芝市 | nyingchi | www.nyingchi.gov.cn | BLACKHOLE | — |
| 33 | 果洛州 | golog | www.golog.gov.cn | BLACKHOLE | — |
| 34 | 枣庄市 | zaozhuang | www.zaozhuang.gov.cn | other(404) | — |
| 35 | 柳州市 | liuzhou | www.liuzhou.gov.cn | REACHABLE 253KB | **A** (config: liuzhou, homepage) |
| 36 | 株洲市 | zhuzhou | www.zhuzhou.gov.cn | BLACKHOLE | — |
| 37 | 桂林市 | guilin | www.guilin.gov.cn | BLACKHOLE | — |
| 38 | 梅州市 | meizhou | www.meizhou.gov.cn | ANTI-BOT(521) | origin/anti-bot |
| 39 | 梧州市 | wuzhou | www.wuzhou.gov.cn | BLACKHOLE | — |
| 40 | 楚雄州 | chuxiong | www.chuxiong.gov.cn | BLACKHOLE | — |
| 41 | 榆林市 | yulin(SN) | www.yulin.gov.cn | BLACKHOLE | shared w/ 玉林 |
| 42 | 武威市 | wuwei | www.wuwei.gov.cn | BLACKHOLE | — |
| 43 | 毕节市 | bijie | www.bijie.gov.cn | BLACKHOLE | — |
| 44 | 永州市 | yongzhou | www.yongzhou.gov.cn | STUB 376b | dead redirect |
| 45 | 汉中市 | hanzhong | www.hanzhong.gov.cn | REACHABLE 110KB | **I** (config: hanzhong, homepage) |
| 46 | 池州市 | chizhou | www.chizhou.gov.cn | BLACKHOLE | — |
| 47 | 沧州市 | cangzhou | www.cangzhou.gov.cn | BLACKHOLE | — |
| 48 | 河池市 | hechi | www.hechi.gov.cn | BLACKHOLE | — |
| 49 | 泉州市 | quanzhou | www.quanzhou.gov.cn | REACHABLE 132KB | **A** (config: quanzhou) |
| 50 | 泰安市 | taian | www.taian.gov.cn | REACHABLE 99KB | B-likely, section TBD |
| 51 | 泰州市 | taizhou(JS) | www.taizhou.gov.cn | REACHABLE 50KB | **B** (config: taizhou_js, homepage) |
| 52 | 泸州市 | luzhou | www.luzhou.gov.cn | BLACKHOLE | — |
| 53 | 洛阳市 | luoyang | www.luoyang.gov.cn | BLACKHOLE | — |
| 54 | 济宁市 | jining | www.jining.gov.cn | STUB 0b | dead redirect |
| 55 | 海东市 | haidong | www.haidong.gov.cn | other(307) | redirect loop |
| 56 | 海北州 | haibei | www.haibei.gov.cn | BLACKHOLE | — |
| 57 | 海南州 | hainan(QH) | www.hainan.gov.cn | BLACKHOLE | shared w/ 海南省 |
| 58 | 海口市 | haikou | www.haikou.gov.cn | STUB 2.9KB | JS shell (Hainan) |
| 59 | 海西州 | haixi | www.haixi.gov.cn | BLACKHOLE | — |
| 60 | 淄博市 | zibo | www.zibo.gov.cn | REACHABLE 71KB | Hanweb JS |
| 61 | 淮北市 | huaibei | www.huaibei.gov.cn | REACHABLE 150KB | JS column API |
| 62 | 淮南市 | huainan | www.huainan.gov.cn | REACHABLE 110KB | JS lists |
| 63 | 淮安市 | huaian | www.huaian.gov.cn | REACHABLE 33KB | Hanweb JS |
| 64 | 清远市 | qingyuan | www.qingyuan.gov.cn | REACHABLE 65KB | gkmlpt/ASP family |
| 65 | 温州市 | wenzhou | www.wenzhou.gov.cn | BLACKHOLE | — |
| 66 | 渭南市 | weinan | www.weinan.gov.cn | BLACKHOLE | — |
| 67 | 湖州市 | huzhou | www.huzhou.gov.cn | BLACKHOLE | — |
| 68 | 湘潭市 | xiangtan | www.xiangtan.gov.cn | BLACKHOLE | — |
| 69 | 湘西州 | xiangxi | www.xiangxi.gov.cn | BLACKHOLE | — |
| 70 | 湛江市 | zhanjiang | www.zhanjiang.gov.cn | REACHABLE 95KB | gkmlpt family (KNOWN_BROKEN) |
| 71 | 滁州市 | chuzhou | www.chuzhou.gov.cn | WAF403 | proxy-gated |
| 72 | 滨州市 | binzhou | www.binzhou.gov.cn | BLACKHOLE | — |
| 73 | 漯河市 | luohe | www.luohe.gov.cn | BLACKHOLE | — |
| 74 | 漳州市 | zhangzhou | www.zhangzhou.gov.cn | BLACKHOLE | — |
| 75 | 潍坊市 | weifang | www.weifang.gov.cn | BLACKHOLE | — |
| 76 | 潮州市 | chaozhou | www.chaozhou.gov.cn | BLACKHOLE | — |
| 77 | 濮阳市 | puyang | www.puyang.gov.cn | BLACKHOLE | — |
| 78 | 烟台市 | yantai | www.yantai.gov.cn | REACHABLE 67KB | **B** (config: yantai, homepage) |
| 79 | 焦作市 | jiaozuo | www.jiaozuo.gov.cn | WAF403 | proxy-gated |
| 80 | 牡丹江市 | mudanjiang | www.mudanjiang.gov.cn | BLACKHOLE | — |
| 81 | 玉林市 | yulin(GX) | www.yulin.gov.cn | BLACKHOLE | shared w/ 榆林 |
| 82 | 玉树自治县 | yushu | www.yushu.gov.cn | REACHABLE 40KB | **A** (config: yushu) |
| 83 | 玉树州 | yushu | www.yushu.gov.cn | REACHABLE 40KB | same portal as #82 |
| 84 | 玉溪市 | yuxi | www.yuxi.gov.cn | REACHABLE 129KB | **Q** (config: yuxi) |
| 85 | 甘南州 | gannan | www.gannan.gov.cn | BLACKHOLE | — |
| 86 | 甘孜州 | garz | www.garz.gov.cn | BLACKHOLE | — |
| 87 | 白城市 | baicheng | www.baicheng.gov.cn | BLACKHOLE | — |
| 88 | 白山市 | baishan | www.baishan.gov.cn | BLACKHOLE | — |
| 89 | 白银市 | baiyin | www.baiyin.gov.cn | REACHABLE 11KB | JS shell |
| 90 | 百色市 | baise | www.baise.gov.cn | BLACKHOLE | — |
| 91 | 益阳市 | yiyang | www.yiyang.gov.cn | STUB 1KB | dead redirect |
| 92 | 盐城市 | yancheng | www.yancheng.gov.cn | REACHABLE 57KB | B-likely, section TBD |
| 93 | 盘锦市 | panjin | www.panjin.gov.cn | REACHABLE 87KB | JS lists |
| 94 | 眉山市 | meishan | www.meishan.gov.cn | BLACKHOLE | — |
| 95 | 石嘴山市 | shizuishan | www.shizuishan.gov.cn | STUB 4.6KB | JS shell (Ningxia) |
| 96 | 石家庄市 | shijiazhuang | www.sjz.gov.cn | REACHABLE 114KB | **S** (config: shijiazhuang, tentative) |
| 97 | 福州市 | fuzhou(FJ) | www.fuzhou.gov.cn | REACHABLE 200KB | **A** (config: fuzhou_fj, homepage) |
| 98 | 秦皇岛市 | qinhuangdao | www.qinhuangdao.gov.cn | BLACKHOLE | — |
| 99 | 红河州 | honghe | www.honghe.gov.cn | BLACKHOLE | — |
| 100 | 绍兴市 | shaoxing | www.shaoxing.gov.cn | BLACKHOLE | — |
| 101 | 绥化市 | suihua | www.suihua.gov.cn | REACHABLE 50KB | **I** (config: suihua) |
| 102 | 绵阳市 | mianyang | www.mianyang.gov.cn | BLACKHOLE | — |
| 103 | 聊城市 | liaocheng | www.liaocheng.gov.cn | REACHABLE 213KB | Hanweb JS |
| 104 | 自贡市 | zigong | www.zigong.gov.cn | BLACKHOLE | — |
| 105 | 舟山市 | zhoushan | www.zhoushan.gov.cn | BLACKHOLE | — |
| 106 | 芜湖市 | wuhu | www.wuhu.gov.cn | REACHABLE 85KB | JS lists |
| 107 | 茂名市 | maoming | www.maoming.gov.cn | REACHABLE 82KB | gkmlpt (post_) family |
| 108 | 荆州市 | jingzhou | www.jingzhou.gov.cn | BLACKHOLE | — |
| 109 | 荆门市 | jingmen | www.jingmen.gov.cn | BLACKHOLE | — |
| 110 | 莆田市 | putian | www.putian.gov.cn | BLACKHOLE | — |
| 111 | 莱芜 | laiwu | www.laiwu.gov.cn | REACHABLE 74KB | **B** (config: laiwu) |
| 112 | 菏泽市 | heze | www.heze.gov.cn | REACHABLE 251KB | Hanweb JS |
| 113 | 萍乡市 | pingxiang | www.pingxiang.gov.cn | STUB 560b | dead redirect |
| 114 | 营口市 | yingkou | www.yingkou.gov.cn | REACHABLE 127KB | JS shell |
| 115 | 葫芦岛市 | huludao | www.huludao.gov.cn | BLACKHOLE | — |

## Notes for the merger

- **Domain collisions in this chunk:** 抚州(Jiangxi) vs 福州(Fujian) both carry
  `www.fuzhou.gov.cn` in the CSV — that domain is **福州**; 抚州's real portal needs
  a separate lookup (config produced is for 福州, keyed `fuzhou_fj`). 榆林(Shaanxi)/
  玉林(Guangxi) share `www.yulin.gov.cn` and 海南州(Qinghai)/海南省 share
  `www.hainan.gov.cn` — all blackholed here, so moot for now.
- `taizhou_js` is keyed to avoid the Zhejiang 台州 (`taizhou`, other chunk) clash.
- Tier 2 configs use `sections:["/"]` because their deep `/zwgk/` lists are
  Hanweb-datacall JS; `--discover` may surface static leaf lists to tighten them.
- `laiwu` is a defunct prefecture (merged into Jinan 2019) — a static archive;
  include only if backfilling historical docs.
