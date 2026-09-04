# City configs — chunk 3 (final third of NEW cities)

**Agent:** city-agent-3 (final-third slice). **Built:** 2026-09-04.
**Vantage:** droplet NYC datacenter IP (104.236.88.45) — reachability is IP-specific.
**Method:** `reachability_sweep.sh` (byte-check + follow redirects; HTTP status ignored)
run on the droplet, then a per-site `dialect_probe.py` / `section_finder.py` pass that
applies the govcms A–T article-link regexes to real listing pages. No document crawling,
no DB writes.

## Chunk scope

The final 115 NEW cities in `source-map-cities.csv` file order (rows 蚌埠市…白杨市),
i.e. NEW rows 231–345 of 345. Includes the special county-level units
(自治州 / 自治县 / 地区 / 林区 / 盟 flagged `(verify)`), Tianjin (the one NEW
municipality), the XPCC/兵团 + Hainan-county `special` tier, and Hong Kong / Macau.

## Headline result

- **115 cities probed.**
- **12 REACHABLE + config-ready** (real content >2KB AND a known govcms dialect on a
  real listing page) → configs below.
- **9 REACHABLE but NO known dialect** (JS-rendered or an article-URL shape not in A–T)
  → flagged "needs new dialect".
- **2 SAR reachable but OUT OF SCOPE** (Hong Kong, Macau — different gov structure).
- **92 blocked** from the NYC IP: 86 BLACKHOLE (TCP geo-fence), 4 WAF (403/412),
  1 origin-error (502), 1 stub/redirect. All would need a residential-CN proxy.
- Matches the corpus-wide finding: only ~1 in 5 NEW cities is directly crawlable from
  the datacenter IP; the rest are proxy-gated.

## READY-TO-MERGE govcms configs (12 cities)

All droplet-reachable with no proxy, so they can join the nightly `group="city"` batch
(a new group — or fold into `group="dept"` if you prefer one municipal loop). `sections`
are verified listing paths where the named dialect's article links were found (counts in
comments). Special county-level cities (济源/潜江/天门) use `admin_level="municipal"` per
the task; switch to `"district"`/`"special"` if you track them separately.

```python
    # ── City tier, chunk-3 (2026-09-04): droplet-reachable NEW cities, existing dialects.
    #    group="city" → add to the nightly govcms loop. All verified via dialect_probe.
    # Dialect A (t-date /…/tYYYYMMDD_ID.html):
    "changzhi": {"name": "Changzhi (长治市)", "base_url": "https://www.changzhi.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/xxgkml/czsrmzf/zfwj_3465/", "/xxgkml/czsrmzf/zbwj_3466/", "/xxgkml/czsrmzf/zcjd/", "/xwzx/tzgg/"]},
    "huangshi": {"name": "Huangshi (黄石市)", "base_url": "https://www.huangshi.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/xxxgk/2020_zc/", "/xwdt/2020_gggs/"]},
    "liaoyuan": {"name": "Liaoyuan (辽源市)", "base_url": "https://www.liaoyuan.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/xxgk/zwxxgkfl/zfwj/", "/xxgk/"]},
    "longyan": {"name": "Longyan (龙岩市)", "base_url": "https://www.longyan.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/gk/flgk/gg/", "/gk/flgk/jd/"]},
    "ordos": {"name": "Ordos (鄂尔多斯市)", "base_url": "https://www.ordos.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/xw_127672/gsgg/", "/gk_128120/zfxxgkzl/zdgksxmlqd/"]},
    "tongliao": {"name": "Tongliao (通辽市)", "base_url": "https://www.tongliao.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/zwgk/", "/xwzx/"]},
    "yinchuan": {"name": "Yinchuan (银川市)", "base_url": "https://www.yinchuan.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/xxgk/zcwj/zcjd/ycszc/", "/xwzx/gsgg/", "/xxgk/zcwj/qtzfwj/wjlist.html"]},
    "tianmen": {"name": "Tianmen (天门市)", "base_url": "https://www.tianmen.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/zwgk/zc/tzgg/", "/zwgk/zc/zcjd/"]},
    "qianjiang": {"name": "Qianjiang (潜江市)", "base_url": "https://www.qianjiang.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/zwgk_210/zfxxgkml/zcwj_qzf/qzfgfxwj/", "/zwgk_210/zfxxgkml/zcwj_qzf/qtwj/", "/zwxx_210/gsgg/"]},
    "jiyuan": {"name": "Jiyuan (济源市)", "base_url": "https://www.jiyuan.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/zwgk/zcwjk/", "/zwgk/"]},
    # Dialect I (hexmon /…/<YYYYMM>/<32-hex>.shtml):
    "ganzhou": {"name": "Ganzhou (赣州市)", "base_url": "https://www.ganzhou.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/gzszf/c100051/2021_zwgk.shtml", "/gzszf/c100023/list.shtml", "/zwgk/zcwj/", "/zwgk/tzgg/"]},
    "hegang": {"name": "Hegang (鹤岗市)", "base_url": "https://www.hegang.gov.cn", "admin_level": "municipal", "group": "city", "sections": ["/hegang/szfgfxwj/zwgk_zc.shtml", "/hegang/tzgg/list.shtml", "/hegang/zcjd/zcjd_sec.shtml"]},
```

**Per-config notes**
- Dialect A cities all server-render `tYYYYMMDD_ID.html` rows on the listed sections
  (probe counts 10–49 links/section). `index_N.html` pagination is usually a stub, so
  page-0 is the reliable window (standard govcms behaviour).
- `ganzhou` article URLs live under `/gzszf/cNNNNNN/…/<32-hex>.shtml` (hexmon I); the
  `/art/` (B) regex also matches a few, harmless — the crawler de-dupes.
- `qianjiang` sections carry a numeric suffix (`zwgk_210`, `zwxx_210`); verified those
  are the live column ids (t-date articles present, e.g. `.../qzfgfxwj/202607/t20260731_15878528.html`).
- `jiyuan` (special/county-level city, Henan) real articles are `/zwgk/.../tN.html` — its
  homepage also emits `/channel/NNNNN/index.html` nav that the numid (G) regex would grab,
  but the operative dialect is A; sections point at the t-date document library.

## REACHABLE but NO known dialect — needs new dialect / bespoke handling (9)

Real content served from the NYC IP, but the article-link shape is not one of A–T
(mostly JS-rendered lists or a numeric-file / TRS-column pattern). No config emitted.

| City | Domain | Article pattern found | Suggested action |
|---|---|---|---|
| 西安市 Xi'an | www.xa.gov.cn | `/gk/zcfg/zcwj/xaszfwj/<numid>.html` (bare numeric file, no date/index) | **High value (sub-provincial).** Add a simple "numeric-file" dialect: `/<path>/\d+\.html` scoped by section. |
| 阜新市 Fuxin | www.fuxin.gov.cn | epoint CMS `/content/YYYY/<id>.html` (nav = `/channel/NNNNN/index.html`) | New "epoint /content/" dialect. |
| 许昌市 Xuchang | www.xuchang.gov.cn | mixed: `/yaowen/liebiao/N/content_N.htm`, `/ywdt/N/N/<uuid>.html` | Needs bespoke; multiple templates. |
| 郑州市 Zhengzhou | www.zhengzhou.gov.cn | homepage JS-rendered; only `/zt/…/index.html` topics exposed | Needs a JS/list-API crawler. |
| 黑河市 Heihe | www.heihe.gov.cn | TRS `/hhs/cNNN/YYYY/cNNN_<id>.shtml` | New "cCOL/YYYY/cCOL_id.shtml" dialect (shared by Heilongjiang cities). |
| 鸡西市 Jixi | www.jixi.gov.cn | TRS `/jixi/cNNN/YYYY/cNNN_<id>.shtml` (same family as Heihe) | Same new dialect as Heihe. |
| 铜仁市 Tongren | www.tongren.gov.cn | `/N/N/N.shtml` generic + occasional ARTI/`<hex>/c.html` | Needs verification of the real doc column. |
| 阜阳市 Fuyang | www.fuyang.gov.cn | http homepage is a ~6.5KB JS shell (https blackholes) | JS-rendered; needs browser fetch. |
| 贵阳市 Guiyang | www.gy.gov.cn | http homepage is a ~4.6KB JS shell (https 405) | JS-rendered; needs browser fetch. |

Note: a single new **"cCOL/YYYY/cCOL_id.shtml" TRS dialect** would unlock Heihe + Jixi
(and likely other Heilongjiang municipal portals) at once — the best marginal add here.

## Hong Kong / Macau (SAR — separate note)

| Unit | Real portal | Status |
|---|---|---|
| 香港特别行政区 Hong Kong | **www.gov.hk** (candidate `www.hong.gov.cn` was bogus) | Reachable (~6.8KB landing shell), but a GovHK CMS with an entirely different structure (English/繁中, no `.gov.cn` t-date columns). **Out of scope** for govcms. |
| 澳门特别行政区 Macau | **www.gov.mo** (candidate `www.macau.gov.cn` was bogus) | Reachable (~114KB), Portuguese/中文 SAR portal, different structure. **Out of scope** for govcms. |

Both are SARs with their own legal/publishing systems; they do not fit the mainland
gov-CMS dialects and should be handled (if ever) by dedicated crawlers, not govcms.

## Domain corrections (CSV `candidate_domain` was the wrong `www.<pinyin>.gov.cn` heuristic)

Verified by DNS. These stay **BLACKHOLE** from the droplet regardless (CN gov geo-fence),
but the corrected domain matters when a residential proxy is used later:

| City | CSV candidate (NXDOMAIN) | Real domain |
|---|---|---|
| 西双版纳傣族自治州 | www.xishuangbanna.gov.cn | **www.xsbn.gov.cn** |
| 那曲(市/地区) | www.nagqu.gov.cn | **www.naqu.gov.cn** |
| 锡林郭勒盟 | www.xilin.gov.cn | **www.xlgl.gov.cn** |
| 阿坝藏族羌族自治州 | www.ngawa.gov.cn | **www.abazhou.gov.cn** |
| 阿拉善盟 | www.alxa.gov.cn | **www.als.gov.cn** |
| 黔东南苗族侗族自治州 | www.qiandongnan.gov.cn | **www.qdn.gov.cn** |
| 黔西南布依族苗族自治州 | www.qianxinan.gov.cn | **www.qxn.gov.cn** |
| 阿勒泰地区 | www.altay.gov.cn | **www.xjalt.gov.cn** |
| 阿里地区 | www.ngari.gov.cn | **UNRESOLVED** — no standard `.gov.cn` portal found (Tibet Ngari; flag) |

(These resolve at the CSV candidate and are geofenced: diqing `www.diqing.gov.cn`,
黄南 `www.huangnan.gov.cn`, 黔南 `www.qiannan.gov.cn`, 阿克苏 `www.aksu.gov.cn`.)

## Full reachability table — chunk 3 (all 115)

Status legend: **REACH-CFG** = reachable + config-ready · **REACH-NODIA** = reachable,
no known dialect · **REACH (SAR)** = reachable but out-of-scope · **BLACKHOLE** = TCP
geo-fence (000) · **WAFxxx** = WAF geo-block · **ORIGIN-ERR / STUB** = origin/redirect
failure. All non-REACH rows are proxy-gated (need a residential-CN vantage).

| City (CN) | pinyin | domain | tier | status | dialect / note |
|---|---|---|---|---|---|
| 长治市 | changzhi | www.changzhi.gov.cn | city | REACH-CFG | A t-date |
| 赣州市 | ganzhou | www.ganzhou.gov.cn | city | REACH-CFG | I hexmon |
| 鹤岗市 | hegang | www.hegang.gov.cn | city | REACH-CFG | I hexmon |
| 黄石市 | huangshi | www.huangshi.gov.cn | city | REACH-CFG | A t-date |
| 济源市 | jiyuan | www.jiyuan.gov.cn | special | REACH-CFG | A t-date |
| 辽源市 | liaoyuan | www.liaoyuan.gov.cn | city | REACH-CFG | A t-date |
| 龙岩市 | longyan | www.longyan.gov.cn | city | REACH-CFG | A t-date |
| 鄂尔多斯市 | ordos | www.ordos.gov.cn | city | REACH-CFG | A t-date |
| 潜江市 | qianjiang | www.qianjiang.gov.cn | special | REACH-CFG | A t-date |
| 天门市 | tianmen | www.tianmen.gov.cn | special | REACH-CFG | A t-date |
| 通辽市 | tongliao | www.tongliao.gov.cn | city | REACH-CFG | A t-date |
| 银川市 | yinchuan | www.yinchuan.gov.cn | city | REACH-CFG | A t-date |
| 阜新市 | fuxin | www.fuxin.gov.cn | city | REACH-NODIA | epoint /content/YYYY/id.html |
| 阜阳市 | fuyang | www.fuyang.gov.cn | city | REACH-NODIA | small JS shell ~6.5KB |
| 贵阳市 | guiyang | www.gy.gov.cn | city | REACH-NODIA | small JS shell ~4.6KB |
| 黑河市 | heihe | www.heihe.gov.cn | city | REACH-NODIA | TRS /cN/YYYY/cN_id.shtml |
| 鸡西市 | jixi | www.jixi.gov.cn | city | REACH-NODIA | TRS /cN/YYYY/cN_id.shtml |
| 铜仁市 | tongren | www.tongren.gov.cn | city | REACH-NODIA | /N/N/N.shtml + ARTI mix |
| 西安市 | xian | www.xa.gov.cn | city | REACH-NODIA | /gk/zcfg/.../<numid>.html (no dialect) |
| 许昌市 | xuchang | www.xuchang.gov.cn | city | REACH-NODIA | mixed CMS /liebiao/content_N.htm |
| 郑州市 | zhengzhou | www.zhengzhou.gov.cn | city | REACH-NODIA | JS homepage (only /zt/ topics) |
| 香港特别行政区 | hong | www.gov.hk (verify→fixed) | special | REACH (SAR) | out-of-scope |
| 澳门特别行政区 | macau | www.gov.mo (verify→fixed) | special | REACH (SAR) | out-of-scope |
| 蚌埠市 | bengbu | www.bengbu.gov.cn | city | WAF403 | - |
| 衡阳市 | hengyang | www.hengyang.gov.cn | city | WAF412 | - |
| 黄山市 | huangshan | www.huangshan.gov.cn | city | WAF412 | - |
| 西宁市 | xining | www.xining.gov.cn | city | WAF403 | - |
| 鄂州市 | ezhou | www.ezhou.gov.cn | city | STUB/redirect 73b | - |
| 邵阳市 | shaoyang | www.shaoyang.gov.cn | city | ORIGIN-ERR 502 | - |
| 阿克苏地区 | aksu | www.aksu.gov.cn (verify) | city | BLACKHOLE | - |
| 阿拉尔市 | alar | www.alar.gov.cn | special | BLACKHOLE | - |
| 阿勒泰地区 | altay | www.xjalt.gov.cn (verify→fixed) | city | BLACKHOLE | - |
| 阿拉善盟 | alxa | www.als.gov.cn (verify→fixed) | city | BLACKHOLE | - |
| 鞍山市 | anshan | www.anshan.gov.cn | city | BLACKHOLE | - |
| 白沙黎族自治县 | baisha | www.baisha.gov.cn (verify) | special | BLACKHOLE | - |
| 白杨市 | baiyang | www.baiyang.gov.cn | special | BLACKHOLE | - |
| 保亭黎族苗族自治县 | baoting | www.baoting.gov.cn (verify) | special | BLACKHOLE | - |
| 包头市 | baotou | www.baotou.gov.cn | city | BLACKHOLE | - |
| 巴彦淖尔市 | bayannur | www.bayannur.gov.cn | city | BLACKHOLE | - |
| 北屯市 | beitun | www.beitun.gov.cn | special | BLACKHOLE | - |
| 长春市 | changchun | www.cc.gov.cn | city | BLACKHOLE | - |
| 昌江黎族自治县 | changjiang | www.changjiang.gov.cn (verify) | special | BLACKHOLE | - |
| 长沙市 | changsha | www.changsha.gov.cn | city | BLACKHOLE | - |
| 澄迈县 | chengmai | www.chengmai.gov.cn | special | BLACKHOLE | - |
| 郴州市 | chenzhou | www.chenzhou.gov.cn | city | BLACKHOLE | - |
| 赤峰市 | chifeng | www.chifeng.gov.cn | city | BLACKHOLE | - |
| 达州市 | dazhou | www.dazhou.gov.cn | city | BLACKHOLE | - |
| 定安县 | dingan | www.dingan.gov.cn | special | BLACKHOLE | - |
| 迪庆藏族自治州 | diqing | www.diqing.gov.cn (verify) | city | BLACKHOLE | - |
| 东方市 | dongfang | www.dongfang.gov.cn | special | BLACKHOLE | - |
| 东莞市 | dongguan | www.dg.gov.cn | city | BLACKHOLE | - |
| 防城港市 | fangchenggang | www.fangchenggang.gov.cn | city | BLACKHOLE | - |
| 贵港市 | guigang | www.guigang.gov.cn | city | BLACKHOLE | - |
| 邯郸市 | handan | www.handan.gov.cn | city | BLACKHOLE | - |
| 鹤壁市 | hebi | www.hebi.gov.cn | city | BLACKHOLE | - |
| 衡水市 | hengshui | www.hengshui.gov.cn | city | BLACKHOLE | - |
| 贺州市 | hezhou | www.hezhou.gov.cn | city | BLACKHOLE | - |
| 呼和浩特市 | hohhot | www.hohhot.gov.cn | city | BLACKHOLE | - |
| 黄冈市 | huanggang | www.huanggang.gov.cn | city | BLACKHOLE | - |
| 黄南藏族自治州 | huangnan | www.huangnan.gov.cn (verify) | city | BLACKHOLE | - |
| 呼伦贝尔市 | hulunbuir | www.hulunbuir.gov.cn | city | BLACKHOLE | - |
| 胡杨河市 | huyanghe | www.huyanghe.gov.cn | special | BLACKHOLE | - |
| 金昌市 | jinchang | www.jinchang.gov.cn | city | BLACKHOLE | - |
| 金华市 | jinhua | www.jinhua.gov.cn | city | BLACKHOLE | - |
| 锦州市 | jinzhou | www.jinzhou.gov.cn | city | BLACKHOLE | - |
| 酒泉市 | jiuquan | www.jiuquan.gov.cn | city | BLACKHOLE | - |
| 乐东黎族自治县 | ledong | www.ledong.gov.cn (verify) | special | BLACKHOLE | - |
| 连云港市 | lianyungang | www.lianyungang.gov.cn | city | BLACKHOLE | - |
| 辽阳市 | liaoyang | www.liaoyang.gov.cn | city | BLACKHOLE | - |
| 临高县 | lingao | www.lingao.gov.cn | special | BLACKHOLE | - |
| 陵水黎族自治县 | lingshui | www.lingshui.gov.cn (verify) | special | BLACKHOLE | - |
| 陇南市 | longnan | www.longnan.gov.cn | city | BLACKHOLE | - |
| 马鞍山市 | maanshan | www.maanshan.gov.cn | city | BLACKHOLE | - |
| 那曲地区 | nagqu | www.naqu.gov.cn (verify→fixed) | city | BLACKHOLE | - |
| 阿里地区 | ngari | UNRESOLVED (verify→fixed) | city | BLACKHOLE | - |
| 阿坝藏族羌族自治州 | ngawa | www.abazhou.gov.cn (verify→fixed) | city | BLACKHOLE | - |
| 黔东南苗族侗族自治州 | qiandongnan | www.qdn.gov.cn (verify→fixed) | city | BLACKHOLE | - |
| 黔南布依族苗族自治州 | qiannan | www.qiannan.gov.cn (verify) | city | BLACKHOLE | - |
| 黔西南布依族苗族自治州 | qianxinan | www.qxn.gov.cn (verify→fixed) | city | BLACKHOLE | - |
| 钦州市 | qinzhou | www.qinzhou.gov.cn | city | BLACKHOLE | - |
| 琼海市 | qionghai | www.qionghai.gov.cn | special | BLACKHOLE | - |
| 琼中黎族苗族自治县 | qiongzhong | www.qiongzhong.gov.cn (verify) | special | BLACKHOLE | - |
| 齐齐哈尔市 | qiqihar | www.qiqihar.gov.cn | city | BLACKHOLE | - |
| 衢州市 | quzhou | www.quzhou.gov.cn | city | BLACKHOLE | - |
| 三沙市 | sansha | www.sansha.gov.cn | city | BLACKHOLE | - |
| 神农架林区 | shennongjia | www.shennongjia.gov.cn (verify) | special | BLACKHOLE | - |
| 石河子市 | shihezi | www.shihezi.gov.cn | special | BLACKHOLE | - |
| 遂宁市 | suining | www.suining.gov.cn | city | BLACKHOLE | - |
| 随州市 | suizhou | www.suizhou.gov.cn | city | BLACKHOLE | - |
| 天津市 | tianjin | www.tianjin.gov.cn | municipality | BLACKHOLE | - |
| 铁岭市 | tieling | www.tieling.gov.cn | city | BLACKHOLE | - |
| 铜川市 | tongchuan | www.tongchuan.gov.cn | city | BLACKHOLE | - |
| 通化市 | tonghua | www.tonghua.gov.cn | city | BLACKHOLE | - |
| 铜陵市 | tongling | www.tongling.gov.cn | city | BLACKHOLE | - |
| 图木舒克市 | tumxuk | www.tumxuk.gov.cn | special | BLACKHOLE | - |
| 屯昌县 | tunchang | www.tunchang.gov.cn | special | BLACKHOLE | - |
| 乌兰察布市 | ulanqab | www.ulanqab.gov.cn | city | BLACKHOLE | - |
| 万宁市 | wanning | www.wanning.gov.cn | special | BLACKHOLE | - |
| 文昌市 | wenchang | www.wenchang.gov.cn | special | BLACKHOLE | - |
| 乌海市 | wuhai | www.wuhai.gov.cn | city | BLACKHOLE | - |
| 五家渠市 | wujiaqu | www.wujiaqu.gov.cn | special | BLACKHOLE | - |
| 五指山市 | wuzhishan | www.wuzhishan.gov.cn | special | BLACKHOLE | - |
| 襄阳市 | xiangyang | www.xiangyang.gov.cn | city | BLACKHOLE | - |
| 仙桃市 | xiantao | www.xiantao.gov.cn | special | BLACKHOLE | - |
| 锡林郭勒盟 | xilin | www.xlgl.gov.cn (verify→fixed) | city | BLACKHOLE | - |
| 邢台市 | xingtai | www.xingtai.gov.cn | city | BLACKHOLE | - |
| 西双版纳傣族自治州 | xishuangbanna | www.xsbn.gov.cn (verify→fixed) | city | BLACKHOLE | - |
| 雅安市 | yaan | www.yaan.gov.cn | city | BLACKHOLE | - |
| 阳泉市 | yangquan | www.yangquan.gov.cn | city | BLACKHOLE | - |
| 鹰潭市 | yingtan | www.yingtan.gov.cn | city | BLACKHOLE | - |
| 运城市 | yuncheng | www.yuncheng.gov.cn | city | BLACKHOLE | - |
| 镇江市 | zhenjiang | www.zhenjiang.gov.cn | city | BLACKHOLE | - |
| 驻马店市 | zhumadian | www.zhumadian.gov.cn | city | BLACKHOLE | - |
| 资阳市 | ziyang | www.ziyang.gov.cn | city | BLACKHOLE | - |
| 遵义市 | zunyi | www.zunyi.gov.cn | city | BLACKHOLE | - |
