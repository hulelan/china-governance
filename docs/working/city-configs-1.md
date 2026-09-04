# City configs — chunk 1 (first-third of NEW prefecture cities)

**Built 2026-09-04.** Vantage = the droplet's NYC datacenter IP (104.236.88.45,
AS14061 DigitalOcean). Reachability via `scripts/rnd/discovery/reachability_sweep.sh`
(byte-check + redirect-follow, <2 KB = stub); dialects confirmed by fetching each
reachable city's policy-listing page from the droplet and matching article-URL shapes
against `crawlers/govcms.py` dialects A–T.

**Scope of this chunk:** the first 115 NEW (not-yet-crawled) cities in
`source-map-cities.csv` file order — 七台河 (row 17) through 德阳 (row 133).

## Result

- **22 / 115 reachable** from the droplet (real content > 2 KB) — the rest are
  blackhole (81), WAF403 (6: anqing, kaifeng, nantong, nanyang, ningde, xinyang),
  stub (2: nanjing 642 B, yueyang 0 B), or odd WAF codes (bozhou/tangshan 405,
  suqian 493). ~19 % crawlable — in line with the ~28 % sampled ceiling.
- **10 / 115 config-ready** (reachable **and** matching a known govcms dialect with a
  server-rendered listing section):
  - **Dialect A (t-date):** baoji, shannan, wuzhong, zhangye, zhoukou
  - **Dialect B (/art/):** linxia, pingliang, weihai, dingxi
  - **Dialect I (hexmon):** suzhou_ah (宿州, Anhui)
- **1 dialect-known but not config-ready:** taizhou_zj (台州) is dialect B, but every
  listing page I hit is JS-rendered (Hanweb client-side datacall, like Jinan's
  通知公告) — needs a `--discover`/browser pass to find a server-rendered `/col/` list.
- **2 need a NEW dialect (don't build bespoke):** xuancheng (宣城, Openness `showList`
  AJAX CMS), leshan (乐山, `/<section>/<numeric-dir>/<15-digit>.html`).
- **9 reachable but dialect unconfirmed:** ankang, baoshan, changde, changzhou,
  dandong, linyi, luan, yichang, hami. Their homepages surface province/national
  (gov.cn, hunan/yn/jiangsu) news and their own policy lists are JS-rendered — no
  server-rendered native article rows found under standard `/zwgk/*` paths. Worth a
  browser-network pass later; several (changzhou=Jiangsu, linyi/weihai-neighbor=
  Shandong, yichang=Hubei) are very likely A/B once the list endpoint is found.

## Naming collisions (important for merge)

- **宿州 Suzhou (Anhui)** shares pinyin with **苏州 Suzhou (Jiangsu)** — the latter has
  its own `crawlers.suzhou` module. Proposed govcms key: **`suzhou_ah`**.
- **台州 Taizhou (Zhejiang)** shares pinyin with **泰州 Taizhou (Jiangsu)**. Proposed
  key: **`taizhou_zj`** (not built — see above).

## (a) Config block — ready to merge into `crawlers/govcms.py` SITES

Sections listed were each confirmed to server-render native article rows from the
droplet on 2026-09-04. They follow the standalone-municipal style (like `qingdao`,
no `group`), so each is crawled with `python3 -m crawlers.govcms --site <key>`. Add
`"group": "city"` if you want them swept as a batch. Recommend a `--discover` pass to
widen `sections` to the full 政策文件/规范性文件 subtree before a deep crawl.

```python
    # ── NEW prefecture cities, chunk 1 (2026-09-04, droplet-reachable) ─────────
    # Dialect A (t-date /…/YYYYMM/tYYYYMMDD_ID.html):
    "baoji": {"name": "Baoji (宝鸡市)", "base_url": "https://www.baoji.gov.cn",
        "admin_level": "municipal", "sections": ["/col46/col47/", "/col46/col52/"]},
    "shannan": {"name": "Shannan (山南市)", "base_url": "https://www.shannan.gov.cn",
        "admin_level": "municipal", "sections": ["/zwgk/", "/jytadf/"]},
    "wuzhong": {"name": "Wuzhong (吴忠市)", "base_url": "https://www.wuzhong.gov.cn",
        "admin_level": "municipal", "sections": ["/sy/zcjd/"]},
    "zhangye": {"name": "Zhangye (张掖市)", "base_url": "https://www.zhangye.gov.cn",
        "admin_level": "municipal", "sections": ["/dzdt/tzgg/", "/zyszfxxgk/zfwj_5652/zcjd_8944/sjzcjd_8947/"]},
    "zhoukou": {"name": "Zhoukou (周口市)", "base_url": "https://www.zhoukou.gov.cn",
        "admin_level": "municipal", "sections": ["/sitesources/zksrmzf/page_pc/xwzx/tzgg/"]},
    # Dialect B (/art/YYYY[/M/D]/art_<id>.html — Hanweb /col/ index → /art/ articles):
    "dingxi": {"name": "Dingxi (定西市)", "base_url": "https://www.dingxi.gov.cn",
        "admin_level": "municipal", "sections": ["/col/col15863/", "/col/col15887/"]},
    "weihai": {"name": "Weihai (威海市)", "base_url": "https://www.weihai.gov.cn",
        "admin_level": "municipal", "sections": ["/col/col102604/"]},
    "linxia": {"name": "Linxia Hui Prefecture (临夏回族自治州)", "base_url": "https://www.linxia.gov.cn",
        "admin_level": "municipal", "sections": ["/lxz/zwgk/fdzdgknr/lzyj/gfxwj/", "/lxz/ywdt/tzgg/"]},
    "pingliang": {"name": "Pingliang (平凉市)", "base_url": "https://www.pingliang.gov.cn",
        "admin_level": "municipal", "sections": ["/zfxxgk/fdzdgknr/lzyj/zcwj/", "/xwzx/tzgg/"]},
    # Dialect I (hexmon /<section>/YYYYMM/<32-hex>.shtml). KEY = suzhou_ah (宿州≠苏州):
    "suzhou_ah": {"name": "Suzhou, Anhui (宿州市)", "base_url": "https://www.suzhou.gov.cn",
        "admin_level": "municipal", "sections": ["/col/col168035/"]},
```

## (b) Full reachability table — all 115 cities in this chunk

Feeds the CSV/access-map refresh. `Real domain` = the abbreviation-corrected portal
where applicable (all abbreviation cities in this chunk — 兰州 lz, 南昌 nc, 厦门 xm,
大连 dl, 宁波 nb — were already correct in the CSV; all five still blackhole).

| # | City | Pinyin | Real domain | Status | Dialect / note |
|---|------|--------|-------------|--------|----------------|
| 1 | 七台河市 | qitaihe | www.qitaihe.gov.cn | blackhole | — |
| 2 | 三亚市 | sanya | www.sanya.gov.cn | blackhole | — |
| 3 | 三明市 | sanming | www.sanming.gov.cn | blackhole | — |
| 4 | 三门峡市 | sanmenxia | www.sanmenxia.gov.cn | blackhole | — |
| 5 | 上饶市 | shangrao | www.shangrao.gov.cn | blackhole | — |
| 6 | 东营市 | dongying | www.dongying.gov.cn | blackhole | — |
| 7 | 中卫市 | zhongwei | www.zhongwei.gov.cn | blackhole | — |
| 8 | 临夏回族自治州 | linxia | www.linxia.gov.cn | REACHABLE | B /art/ — **config-ready** |
| 9 | 临汾市 | linfen | www.linfen.gov.cn | blackhole | — |
| 10 | 临沂市 | linyi | www.linyi.gov.cn | REACHABLE | unconfirmed — homepage links out, list JS-rendered |
| 11 | 临沧市 | lincang | www.lincang.gov.cn | blackhole | — |
| 12 | 丹东市 | dandong | www.dandong.gov.cn | REACHABLE | unconfirmed — homepage links out, list JS-rendered |
| 13 | 丽水市 | lishui | www.lishui.gov.cn | blackhole | — |
| 14 | 丽江市 | lijiang | www.lijiang.gov.cn | blackhole | — |
| 15 | 乌鲁木齐市 | urumqi | www.urumqi.gov.cn | blackhole | — |
| 16 | 乐山市 | leshan | www.leshan.gov.cn | REACHABLE | NEEDS NEW DIALECT (numeric dir/file) |
| 17 | 九江市 | jiujiang | www.jiujiang.gov.cn | blackhole | — |
| 18 | 亳州市 | bozhou | www.bozhou.gov.cn | other(405) | — |
| 19 | 伊春市 | yichun | www.yichun.gov.cn | blackhole | — |
| 20 | 伊犁哈萨克自治州 | ili | www.ili.gov.cn | blackhole | — |
| 21 | 佛山市 | foshan | www.foshan.gov.cn | blackhole | — |
| 22 | 佳木斯市 | jiamusi | www.jiamusi.gov.cn | blackhole | — |
| 23 | 保定市 | baoding | www.baoding.gov.cn | blackhole | — |
| 24 | 保山市 | baoshan | www.baoshan.gov.cn | REACHABLE | unconfirmed — homepage links out, list JS-rendered |
| 25 | 信阳市 | xinyang | www.xinyang.gov.cn | WAF403 | — |
| 26 | 儋州市 | danzhou | www.danzhou.gov.cn | blackhole | — |
| 27 | 克孜勒苏柯尔克孜自治州 | kizilsu | www.kizilsu.gov.cn | blackhole | — |
| 28 | 克拉玛依市 | karamay | www.karamay.gov.cn | blackhole | — |
| 29 | 六安市 | luan | www.luan.gov.cn | REACHABLE | unconfirmed — homepage links out, list JS-rendered |
| 30 | 六盘水市 | liupanshui | www.liupanshui.gov.cn | blackhole | — |
| 31 | 兰州市 | lanzhou | www.lz.gov.cn | blackhole | — |
| 32 | 兴安盟 | xingan | www.xingan.gov.cn | blackhole | — |
| 33 | 内江市 | neijiang | www.neijiang.gov.cn | blackhole | — |
| 34 | 凉山彝族自治州 | liangshan | www.liangshan.gov.cn | blackhole | — |
| 35 | 北海市 | beihai | www.beihai.gov.cn | blackhole | — |
| 36 | 十堰市 | shiyan | www.shiyan.gov.cn | blackhole | — |
| 37 | 南京市 | nanjing | www.nanjing.gov.cn | stub | — |
| 38 | 南充市 | nanchong | www.nanchong.gov.cn | blackhole | — |
| 39 | 南宁市 | nanning | www.nanning.gov.cn | blackhole | — |
| 40 | 南平市 | nanping | www.nanping.gov.cn | blackhole | — |
| 41 | 南昌市 | nanchang | www.nc.gov.cn | blackhole | — |
| 42 | 南通市 | nantong | www.nantong.gov.cn | WAF403 | — |
| 43 | 南阳市 | nanyang | www.nanyang.gov.cn | WAF403 | — |
| 44 | 博尔塔拉蒙古自治州 | bortala | www.bortala.gov.cn | blackhole | — |
| 45 | 厦门市 | xiamen | www.xm.gov.cn | blackhole | — |
| 46 | 双鸭山市 | shuangyashan | www.shuangyashan.gov.cn | blackhole | — |
| 47 | 台州市 | taizhou | www.taizhou.gov.cn | REACHABLE | B /art/ (key `taizhou_zj`) — lists JS-rendered, needs `--discover` |
| 48 | 合肥市 | hefei | www.hefei.gov.cn | blackhole | — |
| 49 | 吉安市 | jian | www.jian.gov.cn | blackhole | — |
| 50 | 吉林市 | jilin | www.jilin.gov.cn | blackhole | — |
| 51 | 吐鲁番市 | turpan | www.turpan.gov.cn | blackhole | — |
| 52 | 吕梁市 | lliang | www.lliang.gov.cn | blackhole | — |
| 53 | 吴忠市 | wuzhong | www.wuzhong.gov.cn | REACHABLE | A t-date — **config-ready** |
| 54 | 周口市 | zhoukou | www.zhoukou.gov.cn | REACHABLE | A t-date — **config-ready** |
| 55 | 和田地区 | hotan | www.hotan.gov.cn | blackhole | — |
| 56 | 咸宁市 | xianning | www.xianning.gov.cn | blackhole | — |
| 57 | 咸阳市 | xianyang | www.xianyang.gov.cn | blackhole | — |
| 58 | 哈密市 | hami | www.hami.gov.cn | REACHABLE | unconfirmed — marginal ~3KB homepage |
| 59 | 哈尔滨市 | harbin | www.harbin.gov.cn | blackhole | — |
| 60 | 唐山市 | tangshan | www.tangshan.gov.cn | other(405) | — |
| 61 | 商丘市 | shangqiu | www.shangqiu.gov.cn | blackhole | — |
| 62 | 商洛市 | shangluo | www.shangluo.gov.cn | blackhole | — |
| 63 | 喀什地区 | kashgar | www.kashgar.gov.cn | blackhole | — |
| 64 | 嘉兴市 | jiaxing | www.jiaxing.gov.cn | blackhole | — |
| 65 | 嘉峪关市 | jiayuguan | www.jiayuguan.gov.cn | blackhole | — |
| 66 | 四平市 | siping | www.siping.gov.cn | blackhole | — |
| 67 | 固原市 | guyuan | www.guyuan.gov.cn | blackhole | — |
| 68 | 塔城地区 | tacheng | www.tacheng.gov.cn | blackhole | — |
| 69 | 大兴安岭地区 | daxinganling | www.daxinganling.gov.cn | blackhole | — |
| 70 | 大同市 | datong | www.datong.gov.cn | blackhole | — |
| 71 | 大庆市 | daqing | www.daqing.gov.cn | blackhole | — |
| 72 | 大理白族自治州 | dali | www.dali.gov.cn | blackhole | — |
| 73 | 大连市 | dalian | www.dl.gov.cn | blackhole | — |
| 74 | 天水市 | tianshui | www.tianshui.gov.cn | blackhole | — |
| 75 | 太原市 | taiyuan | www.taiyuan.gov.cn | blackhole | — |
| 76 | 威海市 | weihai | www.weihai.gov.cn | REACHABLE | B /art/ — **config-ready** |
| 77 | 娄底市 | loudi | www.loudi.gov.cn | blackhole | — |
| 78 | 孝感市 | xiaogan | www.xiaogan.gov.cn | blackhole | — |
| 79 | 宁德市 | ningde | www.ningde.gov.cn | WAF403 | — |
| 80 | 宁波市 | ningbo | www.nb.gov.cn | blackhole | — |
| 81 | 安庆市 | anqing | www.anqing.gov.cn | WAF403 | — |
| 82 | 安康市 | ankang | www.ankang.gov.cn | REACHABLE | unconfirmed — homepage links out, list JS-rendered |
| 83 | 安阳市 | anyang | www.anyang.gov.cn | blackhole | — |
| 84 | 安顺市 | anshun | www.anshun.gov.cn | blackhole | — |
| 85 | 定西市 | dingxi | www.dingxi.gov.cn | REACHABLE | B /art/ — **config-ready** |
| 86 | 宜宾市 | yibin | www.yibin.gov.cn | blackhole | — |
| 87 | 宜昌市 | yichang | www.yichang.gov.cn | REACHABLE | unconfirmed — homepage links out, list JS-rendered |
| 88 | 宜春市 | yichun | www.yichun.gov.cn | blackhole | — |
| 89 | 宝鸡市 | baoji | www.baoji.gov.cn | REACHABLE | A t-date — **config-ready** |
| 90 | 宣城市 | xuancheng | www.xuancheng.gov.cn | REACHABLE | NEEDS NEW DIALECT (Openness `showList` CMS) |
| 91 | 宿州市 | suzhou | www.suzhou.gov.cn | REACHABLE | I hexmon — **config-ready** (key `suzhou_ah`) |
| 92 | 宿迁市 | suqian | www.suqian.gov.cn | other(493) | — |
| 93 | 山南市 | shannan | www.shannan.gov.cn | REACHABLE | A t-date — **config-ready** |
| 94 | 岳阳市 | yueyang | www.yueyang.gov.cn | stub | — |
| 95 | 崇左市 | chongzuo | www.chongzuo.gov.cn | blackhole | — |
| 96 | 巴中市 | bazhong | www.bazhong.gov.cn | blackhole | — |
| 97 | 巴音郭楞蒙古自治州 | bayingolin | www.bayingolin.gov.cn | blackhole | — |
| 98 | 常州市 | changzhou | www.changzhou.gov.cn | REACHABLE | unconfirmed — homepage links out, list JS-rendered |
| 99 | 常德市 | changde | www.changde.gov.cn | REACHABLE | unconfirmed — homepage links out, list JS-rendered |
| 100 | 平凉市 | pingliang | www.pingliang.gov.cn | REACHABLE | B /art/ — **config-ready** |
| 101 | 平顶山市 | pingdingshan | www.pingdingshan.gov.cn | blackhole | — |
| 102 | 广元市 | guangyuan | www.guangyuan.gov.cn | blackhole | — |
| 103 | 广安市 | guangan | www.guangan.gov.cn | blackhole | — |
| 104 | 庆阳市 | qingyang | www.qingyang.gov.cn | blackhole | — |
| 105 | 廊坊市 | langfang | www.langfang.gov.cn | blackhole | — |
| 106 | 延安市 | yanan | www.yanan.gov.cn | blackhole | — |
| 107 | 延边朝鲜族自治州 | yanbian | www.yanbian.gov.cn | blackhole | — |
| 108 | 开封市 | kaifeng | www.kaifeng.gov.cn | WAF403 | — |
| 109 | 张家口市 | zhangjiakou | www.zhangjiakou.gov.cn | blackhole | — |
| 110 | 张家界市 | zhangjiajie | www.zhangjiajie.gov.cn | blackhole | — |
| 111 | 张掖市 | zhangye | www.zhangye.gov.cn | REACHABLE | A t-date — **config-ready** |
| 112 | 徐州市 | xuzhou | www.xuzhou.gov.cn | blackhole | — |
| 113 | 德宏傣族景颇族自治州 | dehong | www.dehong.gov.cn | blackhole | — |
| 114 | 德州市 | dezhou | www.dezhou.gov.cn | blackhole | — |
| 115 | 德阳市 | deyang | www.deyang.gov.cn | blackhole | — |

## Method notes / caveats

- Statuses are droplet-IP-specific; a residential-CN proxy would flip most `blackhole`
  rows. `WAF403` / `405` / `493` are geo-blocks at the edge, also proxy-gated.
- `bozhou` (405) and `tangshan` (405), `suqian` (493) returned non-standard codes on a
  plain GET — likely a WAF; treated as proxy-gated, not retried.
- Article-shape classification used server-rendered listing pages only. "Unconfirmed"
  means the portal is reachable but I could not find a server-rendered native list
  under `/`, `/zwgk/*`, `/xxgk/*`, `/zfxxgk/*` — the rows are AJAX-loaded. Not a dead
  end, just needs browser-network inspection (the Jinan/Tianjin datacall pattern).
- No documents were crawled and no DB was touched; only homepage + a few listing-page
  fetches per reachable city.
