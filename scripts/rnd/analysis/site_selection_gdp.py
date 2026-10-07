"""Pilot-site selection vs provincial GDP per capita (corpus-lessons B4).

The reproducible lever behind `docs/research/site-selection-gdp.md`. A DESCRIPTIVE
replication of the site-selection finding in Wang & Yang, "Policy Experimentation
in China" (NBER w29402 / JPE 2025): >80% of central policy experiments were run in
positively-selected (richer than median) localities. This script joins a small
external panel of provincial GDP to the corpus's central pilot-guideline record.

Two subcommands:

  build-gdp   Assemble data/provincial_gdp.csv from NBS statistical-yearbook xls
              tables (editions 2009-2014, 2021) plus the NBS-revised series as
              tabulated on Wikipedia (2000, 2010, 2020-2025). Needs `xlrd`.
              Downloads nothing: point --nbs-dir and --wiki-dir at local copies
              (URLs listed in NBS_TABLES / WIKI_PAGES below).

  analyze     Read-only against documents.db (run ON the droplet). Prints every
              table the memo cites.

    python3 scripts/rnd/analysis/site_selection_gdp.py analyze --db documents.db

Method notes:
  - Central pilot guideline = same title-only detection as
    docs/research/experimentation-wang-yang.md (cue + designating genre, not news).
    `npc` is excluded (its "central" rows are local people's-congress regulations).
  - Pilot SITES are extracted from the guideline title+body by province name and a
    curated list of city / new-area names mapped to their province. A guideline
    that names >= BROAD_K provinces is a national roll-call, not a selection, and is
    reported separately.
  - GDP per capita is taken in the guideline's year (nearest available year).
    Every comparison is against the SAME-YEAR cross-provincial median, so the
    ~12x nominal growth over the window cannot drive the result.
  - The implementing side maps sub-national SITE -> PROVINCE (SITE2PROV) and
    normalizes by that province's corpus volume, because crawl depth, not
    behaviour, is the first-order driver of raw implementation counts.
"""
import argparse
import csv
import math
import random
import re
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

_p = Path(__file__).resolve().parents
ROOT = _p[3] if len(_p) > 3 else Path.cwd()
DEFAULT_DB = ROOT / "documents.db"
DEFAULT_GDP = ROOT / "data" / "provincial_gdp.csv"

PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏",
    "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西",
    "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
]
EN2CN = {
    "Beijing": "北京", "Tianjin": "天津", "Hebei": "河北", "Shanxi": "山西",
    "Inner Mongolia": "内蒙古", "Liaoning": "辽宁", "Jilin": "吉林", "Heilongjiang": "黑龙江",
    "Shanghai": "上海", "Jiangsu": "江苏", "Zhejiang": "浙江", "Anhui": "安徽",
    "Fujian": "福建", "Jiangxi": "江西", "Shandong": "山东", "Henan": "河南",
    "Hubei": "湖北", "Hunan": "湖南", "Guangdong": "广东", "Guangxi": "广西",
    "Hainan": "海南", "Chongqing": "重庆", "Sichuan": "四川", "Guizhou": "贵州",
    "Yunnan": "云南", "Tibet": "西藏", "Shaanxi": "陕西", "Gansu": "甘肃",
    "Qinghai": "青海", "Ningxia": "宁夏", "Xinjiang": "新疆",
}

# ---------------------------------------------------------------------------
# build-gdp: sources
# ---------------------------------------------------------------------------
# NBS China Statistical Yearbook tables (https://www.stats.gov.cn/sj/ndsj/<ed>/...).
# Each GDP table is a 5-year window at the vintage of that edition; the latest
# edition containing a year is used. Per-capita tables exist in HTML/xls form only
# in the 2013 and 2014 editions (2008-2013). Editions 2015-2020 publish images only.
NBS_TABLES = {
    # local filename                 : (kind, edition, url)
    "2009_html_C0214C.xls": ("gdp", 2009, "https://www.stats.gov.cn/sj/ndsj/2009/html/C0214C.xls"),
    "2010_html_C0214C.xls": ("gdp", 2010, "https://www.stats.gov.cn/sj/ndsj/2010/html/C0214C.xls"),
    "2011_html_C0214C.xls": ("gdp", 2011, "https://www.stats.gov.cn/sj/ndsj/2011/html/C0214C.xls"),
    "2012_html_C0214C.xls": ("gdp", 2012, "https://www.stats.gov.cn/sj/ndsj/2012/html/C0214C.xls"),
    "2013_html_Z0214C.xls": ("gdp", 2013, "https://www.stats.gov.cn/sj/ndsj/2013/html/Z0214C.xls"),
    "2014_zk_html_Z0314C.xls": ("gdp", 2014, "https://www.stats.gov.cn/sj/ndsj/2014/zk/html/Z0314C.xls"),
    "2013_html_Z0215C.xls": ("pc", 2013, "https://www.stats.gov.cn/sj/ndsj/2013/html/Z0215C.xls"),
    "2014_zk_html_Z0315C.xls": ("pc", 2014, "https://www.stats.gov.cn/sj/ndsj/2014/zk/html/Z0315C.xls"),
    "2013_html_Z0305C.xls": ("pop", 2013, "https://www.stats.gov.cn/sj/ndsj/2013/html/Z0305C.xls"),
    "2014_zk_html_Z0205C.xls": ("pop", 2014, "https://www.stats.gov.cn/sj/ndsj/2014/zk/html/Z0205C.xls"),
    "2021_html_C02-05.xls": ("pop", 2021, "https://www.stats.gov.cn/sj/ndsj/2021/html/C02-05.xls"),
}
# NBS-revised series (post 4th economic census) as tabulated on Wikipedia, which
# cites NBS / provincial statistical communiqués. Years 2000, 2010, 2020-2025.
WIKI_PAGES = {
    "List_of_Chinese_provincial-level_divisions_by_GDP_per_capita.html":
        ("pc", "https://en.wikipedia.org/wiki/List_of_Chinese_provincial-level_divisions_by_GDP_per_capita"),
    "List_of_Chinese_administrative_divisions_by_GDP.html":
        ("gdp", "https://en.wikipedia.org/wiki/List_of_Chinese_administrative_divisions_by_GDP"),
}


def _norm_cn(s):
    return re.sub(r"\s+", "", str(s or ""))


def _read_nbs_xls(path):
    """Return {province: {year: value}} from a NBS yearbook table (first value block)."""
    import xlrd  # optional dependency, only for build-gdp
    sh = xlrd.open_workbook(str(path)).sheet_by_index(0)
    years = None
    out = {}
    def _year(v):
        # header cells are floats (2009.0) or, occasionally, strings ('2012')
        s = str(v).strip()
        if re.fullmatch(r"(19|20)\d\d(\.0)?", s):
            return int(float(s))
        return None

    for r in range(sh.nrows):
        vals = [sh.cell_value(r, c) for c in range(sh.ncols)]
        if years is None:
            cand = [_year(v) for v in vals[1:]]
            if sum(1 for y in cand if y) >= 5 and all(y or v == "" for y, v in zip(cand, vals[1:])):
                years = cand
            continue
        name = _norm_cn(vals[0])
        if name not in PROVINCES:
            continue
        row = {}
        for y, v in zip(years, vals[1:]):
            if y is None or y in row:  # second block (indices) repeats the years
                continue
            if isinstance(v, (int, float)) and v != "":
                row[y] = float(v)
        out[name] = row
    return out


class _Tables:
    """Tiny HTML table extractor (stdlib only)."""

    def __init__(self, html):
        from html.parser import HTMLParser

        class P(HTMLParser):
            def __init__(s):
                super().__init__()
                s.tables, s.cur, s.row, s.cell = [], None, None, None

            def handle_starttag(s, t, a):
                if t == "table":
                    s.cur = []
                elif t == "tr" and s.cur is not None:
                    s.row = []
                elif t in ("td", "th") and s.row is not None:
                    s.cell = ""

            def handle_endtag(s, t):
                if t in ("td", "th") and s.cell is not None:
                    s.row.append(re.sub(r"\s+", " ", s.cell).strip())
                    s.cell = None
                elif t == "tr" and s.row is not None:
                    s.cur.append(s.row)
                    s.row = None
                elif t == "table" and s.cur is not None:
                    s.tables.append(s.cur)
                    s.cur = None

            def handle_data(s, d):
                if s.cell is not None:
                    s.cell += d

        p = P()
        p.feed(html)
        self.tables = p.tables


def _read_wiki(path):
    """Return {province: {year: value}} from the 'historical' table (header row 'year', ...)."""
    tabs = _Tables(Path(path).read_text(encoding="utf8", errors="ignore")).tables
    for tb in tabs:
        if tb and tb[0] and tb[0][0].strip().lower() == "year" and len(tb) >= 30:
            years = [int(re.sub(r"\D", "", c)) for c in tb[0][1:]]
            out = {}
            for r in tb[1:]:
                n = re.sub(r"\[.*?\]", "", r[0]).strip()
                if n in EN2CN:
                    out[EN2CN[n]] = {y: float(v.replace(",", "")) for y, v in zip(years, r[1:]) if v}
            return out
    raise SystemExit(f"no historical table in {path}")


def build_gdp(args):
    nbs_dir, wiki_dir = Path(args.nbs_dir), Path(args.wiki_dir)
    gdp_v, pc_v, pop = {}, {}, {}  # vintage (yearbook) series: prov -> {year: (val, edition)}
    for fn, (kind, ed, _url) in NBS_TABLES.items():
        d = _read_nbs_xls(nbs_dir / fn)
        tgt = {"gdp": gdp_v, "pc": pc_v, "pop": pop}[kind]
        for p, row in d.items():
            for y, v in row.items():
                cur = tgt.setdefault(p, {}).get(y)
                if cur is None or ed > cur[1]:  # latest edition wins
                    tgt[p][y] = (v, ed)
    wiki_pc = _read_wiki(wiki_dir / "List_of_Chinese_provincial-level_divisions_by_GDP_per_capita.html")
    wiki_gdp = _read_wiki(wiki_dir / "List_of_Chinese_administrative_divisions_by_GDP.html")  # CNY million
    missing = [p for p in PROVINCES if p not in wiki_pc or p not in wiki_gdp or p not in pop]
    if missing:
        raise SystemExit(f"provinces missing in sources: {missing}")

    rows = []
    for p in PROVINCES:
        series = {}  # year -> dict
        # NBS-revised anchor years (Wikipedia tabulation)
        for y, v in wiki_pc[p].items():
            g = wiki_gdp[p].get(y)
            if g is None:
                continue
            g100m = g / 100.0
            series[y] = dict(gdp=g100m, pc=v, pop=g * 1e6 / v / 1e4, src="nbs_revised_wiki",
                             note="GDP and per-capita from NBS-revised series; population derived = GDP/pc")
        # yearbook vintage years 2004-2013
        for y in range(2004, 2014):
            g = gdp_v.get(p, {}).get(y)
            pc = pc_v.get(p, {}).get(y)
            pp = pop.get(p, {}).get(y)
            if g is None or pp is None:
                continue
            if pc is not None:
                series[y] = dict(gdp=g[0], pc=pc[0], pop=pp[0], src=f"nbs_yearbook_{pc[1]}",
                                 note="per-capita as published (yearbook vintage)")
            else:
                series[y] = dict(gdp=g[0], pc=g[0] * 1e8 / (pp[0] * 1e4), pop=pp[0], src=f"nbs_yearbook_{g[1]}_derived",
                                 note="per-capita derived = GDP / year-end population (yearbook vintage)")
        # 2014-2019: images only at NBS; interpolate per-capita log-linearly 2013 -> 2020,
        # population from the 2021 yearbook, GDP derived.
        if 2013 in series and 2020 in series:
            a, b = series[2013]["pc"], series[2020]["pc"]
            for y in range(2014, 2020):
                f = (y - 2013) / 7.0
                pc = math.exp(math.log(a) * (1 - f) + math.log(b) * f)
                pp = pop.get(p, {}).get(y)
                ppv = pp[0] if pp else None
                series[y] = dict(gdp=(pc * ppv * 1e4 / 1e8) if ppv else None, pc=pc, pop=ppv,
                                 src="interp_2013_2020",
                                 note="per-capita log-linear interpolation between NBS 2013 (vintage) and 2020 (revised); population NBS yearbook 2021")
        for y in sorted(series):
            s = series[y]
            rows.append(dict(province=p, year=y,
                             gdp_total_100m_yuan=round(s["gdp"], 2) if s["gdp"] is not None else "",
                             gdp_per_capita_yuan=round(s["pc"]),
                             population_10k=round(s["pop"], 1) if s["pop"] is not None else "",
                             source=s["src"], note=s["note"]))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf8", newline="") as f:
        f.write("# provincial_gdp.csv — 31 provincial-level units, current prices.\n")
        f.write("# Built by scripts/rnd/analysis/site_selection_gdp.py build-gdp. Sources:\n")
        for fn, (kind, ed, url) in NBS_TABLES.items():
            f.write(f"#   NBS China Statistical Yearbook {ed} [{kind}]: {url}\n")
        for fn, (kind, url) in WIKI_PAGES.items():
            f.write(f"#   NBS-revised series as tabulated on Wikipedia [{kind}]: {url}\n")
        f.write("# gdp_total_100m_yuan = 亿元; gdp_per_capita_yuan = 元; population_10k = 万人 (year-end resident population,\n")
        f.write("#   or GDP/per-capita for the revised-series years). `source` tells which vintage a row comes from;\n")
        f.write("#   rows with source=interp_2013_2020 are interpolated (2014-2019) and should be treated as ranks, not levels.\n")
        w = csv.DictWriter(f, fieldnames=["province", "year", "gdp_total_100m_yuan", "gdp_per_capita_yuan",
                                          "population_10k", "source", "note"])
        w.writeheader()
        w.writerows(rows)
    yrs = sorted({r["year"] for r in rows})
    print(f"wrote {out}: {len(rows)} rows, {len({r['province'] for r in rows})} provinces, years {yrs[0]}-{yrs[-1]} ({len(yrs)} years)")
    by_src = defaultdict(set)
    for r in rows:
        by_src[r["source"]].add(r["year"])
    for s, ys in sorted(by_src.items(), key=lambda kv: min(kv[1])):
        print(f"  {s:<32} years {min(ys)}-{max(ys)} ({len(ys)})")
    # vintage sensitivity: 2010 exists in both the yearbook (2014 ed.) and the revised series
    v = [pc_v[p][2010][0] for p in PROVINCES if 2010 in pc_v.get(p, {})]
    w = [wiki_pc[p][2010] for p in PROVINCES if 2010 in pc_v.get(p, {})]
    if len(v) == 31:
        print(f"  2010 per-capita, yearbook vintage vs NBS-revised: Spearman = {spearman(v, w):.3f}; "
              f"median revision = {statistics.median(100 * (b / a - 1) for a, b in zip(v, w)):+.1f}%")


# ---------------------------------------------------------------------------
# analyze: corpus side
# ---------------------------------------------------------------------------
PILOT_RE = re.compile(r"试点|试验区|先行先试|示范区")
NEWS_RE = re.compile(r"图解|解读|答记者问|新闻发布|访谈|媒体|吹风会|发布会|问答|一图")
DESIG_RE = re.compile(r"方案|通知|意见|决定|批复|公告|办法|规定|印发|的函|工作")
DATE_OK = "length(d.date_published)>=10 AND substr(d.date_published,1,4) BETWEEN '2000' AND '2026'"

# Province aliases (regex). 海南 must not match 海南藏族自治州 (Qinghai).
PROV_PATTERNS = {p: re.compile(p) for p in PROVINCES}
PROV_PATTERNS["海南"] = re.compile(r"海南(?!藏族)")
PROV_PATTERNS["吉林"] = re.compile(r"吉林")  # 吉林市 is in 吉林 anyway

# City / new-area -> province. Capitals, plan-listed cities, large prefecture cities,
# national new areas and well-known pilot zones. Short generic names are avoided.
CITY2PROV = {
    # municipalities' zones
    "浦东": "上海", "临港新片区": "上海", "滨海新区": "天津", "两江新区": "重庆", "雄安": "河北",
    # capitals / plan-listed / major
    "石家庄": "河北", "唐山": "河北", "廊坊": "河北", "太原": "山西", "大同": "山西",
    "呼和浩特": "内蒙古", "包头": "内蒙古", "鄂尔多斯": "内蒙古",
    "沈阳": "辽宁", "大连": "辽宁", "鞍山": "辽宁", "长春": "吉林", "哈尔滨": "黑龙江", "大庆": "黑龙江",
    "南京": "江苏", "苏州": "江苏", "无锡": "江苏", "常州": "江苏", "南通": "江苏", "徐州": "江苏",
    "镇江": "江苏", "扬州": "江苏", "泰州": "江苏", "盐城": "江苏", "连云港": "江苏", "宿迁": "江苏", "淮安": "江苏",
    "杭州": "浙江", "宁波": "浙江", "温州": "浙江", "嘉兴": "浙江", "湖州": "浙江", "绍兴": "浙江",
    "金华": "浙江", "义乌": "浙江", "舟山": "浙江", "台州": "浙江", "丽水": "浙江", "衢州": "浙江",
    "合肥": "安徽", "芜湖": "安徽", "马鞍山": "安徽", "蚌埠": "安徽", "滁州": "安徽",
    "福州": "福建", "厦门": "福建", "泉州": "福建", "漳州": "福建", "平潭": "福建",
    "南昌": "江西", "赣州": "江西", "九江": "江西",
    "济南": "山东", "青岛": "山东", "烟台": "山东", "潍坊": "山东", "威海": "山东", "淄博": "山东", "临沂": "山东",
    "郑州": "河南", "洛阳": "河南", "开封": "河南", "许昌": "河南",
    "武汉": "湖北", "宜昌": "湖北", "襄阳": "湖北", "长沙": "湖南", "株洲": "湖南", "湘潭": "湖南", "岳阳": "湖南",
    "广州": "广东", "深圳": "广东", "珠海": "广东", "佛山": "广东", "东莞": "广东", "中山": "广东",
    "惠州": "广东", "江门": "广东", "汕头": "广东", "湛江": "广东", "肇庆": "广东", "横琴": "广东",
    "前海": "广东", "南沙": "广东", "粤港澳大湾区": "广东",
    "南宁": "广西", "柳州": "广西", "桂林": "广西", "北海": "广西", "海口": "海南", "三亚": "海南", "洋浦": "海南",
    "成都": "四川", "绵阳": "四川", "宜宾": "四川", "天府新区": "四川",
    "贵阳": "贵州", "遵义": "贵州", "贵安新区": "贵州", "昆明": "云南", "曲靖": "云南", "拉萨": "西藏",
    "西安": "陕西", "咸阳": "陕西", "宝鸡": "陕西", "西咸新区": "陕西", "兰州": "甘肃", "兰州新区": "甘肃",
    "西宁": "青海", "银川": "宁夏", "乌鲁木齐": "新疆", "克拉玛依": "新疆", "喀什": "新疆", "霍尔果斯": "新疆",
}
CITY_RE = re.compile("|".join(sorted(map(re.escape, CITY2PROV), key=len, reverse=True)))

BROAD_K = 20  # >= this many provinces named = national roll-call, not a selection

# Sub-national site_key -> province. Prefix rules first, then exact keys.
PREFIX2PROV = [
    ("bjb_", "北京"), ("bjd_", "北京"), ("shb_", "上海"), ("cq_", "重庆"), ("cqd_", "重庆"),
    ("fj_", "福建"), ("hn_", "湖南"), ("jl_", "吉林"), ("js_", "江苏"), ("ln_", "辽宁"),
    ("nx_", "宁夏"), ("sd_", "山东"), ("xz_", "西藏"), ("njd_", "江苏"), ("whd_", "湖北"),
    ("gd", "广东"), ("sz", "广东"), ("xj", "新疆"),
]
SITE2PROV = {
    # provincial portals
    "bj": "北京", "sh": "上海", "cq": "重庆", "gd": "广东", "js": "江苏", "hlj": "黑龙江", "zj": "浙江",
    "fujian": "福建", "hunan": "湖南", "jilin": "吉林", "liaoning": "辽宁", "ningxia": "宁夏",
    "qinghai": "青海", "shandong": "山东", "xinjiang": "新疆", "xizang": "西藏",
    # Shenzhen bureaus (admin_level=department) and districts
    "audit": "广东", "fgw": "广东", "ga": "广东", "hrss": "广东", "jtys": "广东", "mzj": "广东",
    "sf": "广东", "stic": "广东", "swj": "广东", "szeb": "广东", "wjw": "广东", "yjgl": "广东", "zjj": "广东",
    "laiwu": "山东",
    # Guangdong cities (gkmlpt)
    "gz": "广东", "zhuhai": "广东", "jiangmen": "广东", "huizhou": "广东", "zhongshan": "广东",
    "jieyang": "广东", "shanwei": "广东", "shaoguan": "广东", "heyuan": "广东", "yangjiang": "广东",
    "yunfu": "广东", "shantou": "广东", "zhanjiang": "广东", "zhaoqing": "广东", "maoming": "广东",
    # other cities
    "abazhou": "四川", "ahsz": "安徽", "al": "西藏", "ale": "新疆", "ankang": "陕西", "baiyin": "甘肃",
    "baoji": "陕西", "baoshan": "云南", "bozhou": "安徽", "bts": "新疆", "bynr": "内蒙古",
    "changchun": "吉林", "changde": "湖南", "changdu": "西藏", "changzhi": "山西", "changzhou": "江苏",
    "chaoyang": "辽宁", "chengdu": "四川", "cj": "新疆", "dandong": "辽宁", "dingxi": "甘肃",
    "dxal": "黑龙江", "fushun": "辽宁", "fuxin": "辽宁", "fuyang": "安徽", "fuzhou_fj": "福建",
    "ganzhou": "江西", "gnzrmzf": "甘肃", "haikou": "海南", "hainanzhou": "青海", "hami": "新疆",
    "hangzhou": "浙江", "hanzhong": "陕西", "hbqj": "湖北", "hegang": "黑龙江", "heihe": "黑龙江",
    "heze": "山东", "hh": "云南", "huaian": "江苏", "huaibei": "安徽", "huaihua": "湖南",
    "huainan": "安徽", "huangshi": "湖北", "jcgov": "山西", "jdz": "江西", "jinan": "山东",
    "jining": "山东", "jixi": "黑龙江", "jiyuan": "河南", "kashi": "新疆", "klmy": "新疆",
    "lasa": "西藏", "leshan": "四川", "lf": "河北", "liaocheng": "山东", "liaoyuan": "吉林",
    "linxia": "甘肃", "linyi": "山东", "linzhi": "西藏", "liuzhou": "广西", "longyan": "福建",
    "luan": "安徽", "lvliang": "山西", "lyg": "江苏", "nantong": "江苏", "naqu": "西藏",
    "nqs": "新疆", "ordos": "内蒙古", "panjin": "辽宁", "pds": "河南", "pingliang": "甘肃",
    "qianjiang": "湖北", "qingdao": "山东", "qj": "云南", "quanzhou": "福建", "shannan": "西藏",
    "shenyang": "辽宁", "shijiazhuang": "河北", "shizuishan": "宁夏", "shuangyashan": "黑龙江",
    "shuozhou": "山西", "shuozhou_c2": "山西", "siping": "吉林", "sm": "福建", "smx": "河南",
    "suihua": "黑龙江", "suizhou": "湖北", "suzhou": "江苏", "suzhou_ah": "安徽", "taian": "山东",
    "taizhou_js": "江苏", "tianmen": "湖北", "tl": "安徽", "tlf": "新疆", "tonghua": "吉林",
    "tongliao": "内蒙古", "weihai": "山东", "wjq": "新疆", "wlmq": "新疆", "wuhai": "内蒙古",
    "wuhan": "湖北", "wuhu": "安徽", "wuxi": "江苏", "wuzhong": "宁夏", "xa": "陕西",
    "xinxiang": "河南", "xlgl": "内蒙古", "xuancheng": "安徽", "xuchang": "河南", "yanbian": "吉林",
    "yancheng": "江苏", "yantai": "山东", "yc": "黑龙江", "yichang": "湖北", "yinchuan": "宁夏",
    "yingkou": "辽宁", "yueyang": "湖南", "yushu": "青海", "yuxi": "云南", "zhangye": "甘肃",
    "zhengzhou": "河南", "zhoukou": "河南", "zibo": "山东",
}


def site_province(site_key):
    if site_key in SITE2PROV:
        return SITE2PROV[site_key]
    for pre, prov in PREFIX2PROV:
        if site_key.startswith(pre):
            return prov
    return None


class GDP:
    def __init__(self, path):
        self.pc = defaultdict(dict)   # prov -> year -> per-capita
        self.pop = defaultdict(dict)
        self.src = defaultdict(dict)
        with open(path, encoding="utf8") as f:
            rows = [l for l in f if not l.startswith("#")]
        for r in csv.DictReader(rows):
            p, y = r["province"], int(r["year"])
            self.pc[p][y] = float(r["gdp_per_capita_yuan"])
            if r["population_10k"]:
                self.pop[p][y] = float(r["population_10k"])
            self.src[p][y] = r["source"]
        self.years = sorted({y for p in self.pc for y in self.pc[p]})
        self.observed_years = sorted({y for p in self.pc for y in self.pc[p] if not self.src[p][y].startswith("interp")})

    def nearest(self, year, observed_only=False):
        pool = self.observed_years if observed_only else self.years
        return min(pool, key=lambda y: (abs(y - year), y))

    def pc_year(self, year, observed_only=False):
        y = self.nearest(year, observed_only)
        return y, {p: self.pc[p][y] for p in PROVINCES if y in self.pc[p]}

    def pop_year(self, year):
        ys = [y for y in self.years if all(y in self.pop[p] for p in PROVINCES)]
        y = min(ys, key=lambda yy: (abs(yy - year), yy))
        return y, {p: self.pop[p][y] for p in PROVINCES}


def hr(title):
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def ranks(xs):
    """Average ranks (1-based) with ties."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


# Text that names a province without designating it as a site, stripped before matching:
#   《…》           titles of cited instruments (e.g. 《关于支持深圳…的意见》 in a Hainan doc)
#   新疆生产建设兵团  appears in the standard distribution list of nearly every NDRC/ministry notice
#   地址/邮编 lines   issuer addresses (北京市西城区…)
BOILERPLATE_RE = re.compile(
    r"《[^》\n]{0,120}》|新疆生产建设兵团|（?新疆兵团）?|地址[:：][^\n。；;]{0,80}|邮政?编码?[:：]\s*\d{6}"
)


def clean_text(text):
    return BOILERPLATE_RE.sub("", text)


def extract_sites(text):
    """Provinces named in text, via province names and curated city names (boilerplate stripped)."""
    text = clean_text(text)
    found = Counter()
    for p, rx in PROV_PATTERNS.items():
        n = len(rx.findall(text))
        if n:
            found[p] += n
    for m in CITY_RE.findall(text):
        found[CITY2PROV[m]] += 1
    return found


def load_guidelines(conn):
    rows = conn.execute(f"""
        SELECT d.id, d.title, substr(d.date_published,1,10), d.site_key, d.body_text_cn, d.document_number
        FROM documents d JOIN sites s ON s.site_key=d.site_key
        WHERE s.admin_level='central' AND d.site_key!='npc' AND {DATE_OK}
    """).fetchall()
    out = []
    for id_, title, dt, site, body, docnum in rows:
        t = title or ""
        if PILOT_RE.search(t) and not NEWS_RE.search(t) and DESIG_RE.search(t):
            out.append(dict(id=id_, title=t, date=dt, year=int(dt[:4]), site=site, body=body or "", docnum=docnum or ""))
    # De-duplicate mirror copies (gov.cn republishes ministry texts; some rows are crawled twice):
    # one row per normalized title, keeping the earliest-dated copy with the longest body.
    best, members = {}, defaultdict(list)
    for g in out:
        key = re.sub(r"[\s《》（）()〔〕\[\]【】]", "", g["title"])
        members[key].append(g["id"])
        cur = best.get(key)
        if cur is None or (g["date"], -len(g["body"])) < (cur["date"], -len(cur["body"])):
            best[key] = g
    for key, g in best.items():
        g["all_ids"] = members[key]  # mirror copies, kept so citation/diffusion joins see every copy
    deduped = sorted(best.values(), key=lambda g: g["date"])
    print(f"  (de-duplicated {len(out)} guideline rows -> {len(deduped)} distinct titles)")
    return deduped


def pct(a, b):
    return f"{100.0 * a / b:.1f}%" if b else "n/a"


def analyze(args):
    gdp = GDP(args.gdp)
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    random.seed(7)

    hr("0. DATA")
    print(f"GDP panel: {len(gdp.pc)} provinces, years {gdp.years[0]}-{gdp.years[-1]} ({len(gdp.years)} years), "
          f"observed (non-interpolated) years: {gdp.observed_years}")
    # vintage sensitivity: 2010 is present both as yearbook-vintage (2014 ed) and revised (wiki) only if
    # built that way; here report rank stability across years instead.
    y10, pc10 = gdp.pc_year(2010)
    y20, pc20 = gdp.pc_year(2020)
    print(f"Spearman(GDPpc {y10}, GDPpc {y20}) across 31 provinces = "
          f"{spearman([pc10[p] for p in PROVINCES], [pc20[p] for p in PROVINCES]):.3f} (rank stability)")

    G = load_guidelines(conn)
    print(f"Central pilot guidelines (title cue + designating genre, not news, npc excluded): {len(G)}; "
          f"with body>200 chars: {sum(1 for g in G if len(g['body']) > 200)}")

    # --- site extraction -----------------------------------------------------
    hr("1. WHICH GUIDELINES NAME PILOT SITES")
    for g in G:
        g["title_sites"] = extract_sites(g["title"])
        g["body_sites"] = extract_sites(g["title"] + "\n" + g["body"])
        g["n_body"] = len(g["body_sites"])
        g["n_title"] = len(g["title_sites"])
    n_title = sum(1 for g in G if g["n_title"])
    n_body = sum(1 for g in G if g["n_body"])
    n_broad = sum(1 for g in G if g["n_body"] >= BROAD_K)
    n_sel = sum(1 for g in G if 1 <= g["n_body"] < BROAD_K)
    print(f"name >=1 province in TITLE: {n_title} ({pct(n_title, len(G))})")
    print(f"name >=1 province in TITLE+BODY: {n_body} ({pct(n_body, len(G))})")
    print(f"  of which selective (1..{BROAD_K - 1} provinces): {n_sel}; national roll-call (>={BROAD_K}): {n_broad}")
    dist = Counter(min(g["n_body"], BROAD_K) for g in G)
    print("distribution of provinces named (title+body):",
          ", ".join(f"{k if k < BROAD_K else str(BROAD_K) + '+'}:{dist[k]}" for k in sorted(dist)))
    print("\nper period (selective guidelines / all guidelines):")
    for lo, hi in ((2000, 2007), (2008, 2012), (2013, 2017), (2018, 2022), (2023, 2026)):
        a = [g for g in G if lo <= g["year"] <= hi]
        s = [g for g in a if 1 <= g["n_body"] < BROAD_K]
        print(f"  {lo}-{hi}: {len(s):4d} / {len(a):4d}  ({pct(len(s), len(a))})")

    # --- positive selection ---------------------------------------------------
    hr("2. POSITIVE SELECTION: pilot provinces vs same-year provincial median GDP per capita")

    for g in G:
        # "strong" sites: named in the title, or at least twice in the body (drops one-off asides
        # such as 借鉴上海经验)
        g["strong_sites"] = Counter({p: n for p, n in g["body_sites"].items() if n >= 2 or p in g["title_sites"]})
        g["n_strong"] = len(g["strong_sites"])

    def selection_stats(gs, observed_only=False, weight_by_mentions=False, sites_key="body_sites"):
        res = []
        for g in gs:
            y, pc = gdp.pc_year(g["year"], observed_only)
            med = statistics.median(pc.values())
            sites = g[sites_key]
            vals = [pc[p] for p in sites if p in pc]
            if not vals:
                continue
            if weight_by_mentions:
                w = [sites[p] for p in sites if p in pc]
                mean_pc = sum(v * ww for v, ww in zip(vals, w)) / sum(w)
            else:
                mean_pc = statistics.mean(vals)
            above = sum(1 for v in vals if v > med)
            # percentile rank of each pilot province among the 31
            srt = sorted(pc.values())
            prs = [sum(1 for v in srt if v < x) / (len(srt) - 1) for x in vals]
            res.append(dict(id=g["id"], year=g["year"], k=len(vals), pos_mean=mean_pc > med,
                            pos_majority=above / len(vals) > 0.5, share_above=above / len(vals),
                            mean_pr=statistics.mean(prs), gdp_year=y))
        return res

    def report(res, label):
        if not res:
            print(f"{label}: n=0")
            return
        n = len(res)
        print(f"{label}: n={n}  positively selected (mean pilot GDPpc > median) = {pct(sum(r['pos_mean'] for r in res), n)}"
              f"  | majority of pilot set above median = {pct(sum(r['pos_majority'] for r in res), n)}"
              f"  | mean percentile rank of pilot provinces = {statistics.mean(r['mean_pr'] for r in res):.3f} (random=0.500)")

    SEL = [g for g in G if 1 <= g["n_body"] < BROAD_K]
    res_all = selection_stats(SEL)
    report(res_all, "ALL selective guidelines (title+body sites)")
    SEL_STRONG = [g for g in G if 1 <= g["n_strong"] < BROAD_K]
    report(selection_stats(SEL_STRONG, sites_key="strong_sites"), "  strong sites only (in title, or >=2 body mentions)")
    report(selection_stats([g for g in SEL if g["n_title"]], sites_key="title_sites"), "  title-named sites only (cleanest)")
    report(selection_stats([g for g in SEL if g["n_title"]]), "  title names a site (all its body sites)")
    report(selection_stats([g for g in SEL if g["n_body"] == 1]), "  exactly 1 province named")
    report(selection_stats([g for g in SEL if 2 <= g["n_body"] <= 5]), "  2-5 provinces named")
    report(selection_stats([g for g in SEL if 6 <= g["n_body"] < BROAD_K]), f"  6-{BROAD_K - 1} provinces named")
    report(selection_stats(SEL, weight_by_mentions=True), "  mention-weighted pilot mean")
    report(selection_stats(SEL, observed_only=True), "  GDP from observed (non-interpolated) years only")
    report(selection_stats([g for g in SEL if re.search(r"试点", g["title"])]), "  strict 试点 cue in title")
    report(selection_stats([g for g in SEL if not re.search(r"示范区|试验区", g["title"])]), "  excluding 示范区/试验区 zone names")
    report(selection_stats([g for g in SEL if g["site"] == "gov"]), "  State Council portal (gov) anchors only")
    report(selection_stats([g for g in SEL if g["site"] != "gov"]), "  ministry-site anchors only")
    report(selection_stats([g for g in SEL if re.search(r"批复", g["title"])]), "  批复 (locality-requested replies)")
    report(selection_stats([g for g in SEL if not re.search(r"批复", g["title"])]), "  non-批复 (assigned designations)")
    print("\nby period:")
    for lo, hi in ((2000, 2007), (2008, 2012), (2013, 2017), (2018, 2022), (2023, 2026)):
        report(selection_stats([g for g in SEL if lo <= g["year"] <= hi]), f"  {lo}-{hi}")
    print("\nnational roll-calls (>= %d provinces) for reference:" % BROAD_K)
    report(selection_stats([g for g in G if g["n_body"] >= BROAD_K]), "  roll-calls")

    # population-weighted random baseline: draw k provinces with prob ∝ population
    print("\nRandom baselines (what 'positively selected' would be under no selection on income):")
    yb, popb = gdp.pop_year(2015)
    yb2, pcb = gdp.pc_year(2015)
    med = statistics.median(pcb.values())
    provs = list(PROVINCES)
    wts = [popb[p] for p in provs]
    ks = [r["k"] for r in res_all]
    srt = sorted(pcb.values())
    for label, weights in (("uniform over 31 provinces", None), (f"population-weighted ({yb})", wts)):
        h_mean = h_maj = 0
        prs = []
        T = 20000
        for _ in range(T):
            k = random.choice(ks)
            if weights is None:
                draw = random.sample(provs, k)
            else:
                draw = set()
                while len(draw) < k:
                    draw.add(random.choices(provs, weights=weights)[0])
            vals = [pcb[p] for p in draw]
            h_mean += statistics.mean(vals) > med
            h_maj += sum(1 for v in vals if v > med) / len(vals) > 0.5
            prs.append(statistics.mean(sum(1 for v in srt if v < x) / (len(srt) - 1) for x in vals))
        print(f"  {label}: mean>median {100.0 * h_mean / T:.1f}% | majority above median {100.0 * h_maj / T:.1f}%"
              f" | mean percentile rank {statistics.mean(prs):.3f}")
    print("  (mean>median is biased upward by the right-skewed GDPpc distribution: Beijing/Shanghai/Tianjin pull any set's mean;"
          " the majority and percentile-rank metrics are the fair comparison)")

    # --- over-selection by province -----------------------------------------
    hr("3. WHICH PROVINCES ARE OVER-SELECTED (selection ratio vs population share)")
    desig = Counter()
    desig_title = Counter()
    for g in SEL:
        for p in g["body_sites"]:
            desig[p] += 1
        for p in g["title_sites"]:
            desig_title[p] += 1
    tot = sum(desig.values())
    yb, popb = gdp.pop_year(2015)
    totpop = sum(popb.values())
    yb2, pcb = gdp.pc_year(2015)
    rows = []
    for p in PROVINCES:
        share = desig[p] / tot if tot else 0
        pshare = popb[p] / totpop
        rows.append((p, desig[p], desig_title[p], share / pshare if pshare else float("nan"), pcb[p], popb[p]))
    rows.sort(key=lambda r: -r[3])
    print(f"designations counted over {len(SEL)} selective guidelines ({tot} province-designations); "
          f"population {yb}, GDPpc {yb2}")
    print(f"{'province':<8}{'desig':>7}{'title':>7}{'sel.ratio':>11}{'GDPpc':>9}{'pop(万)':>9}")
    for p, d, dt_, ratio, pc, pop in rows:
        print(f"{p:<8}{d:>7}{dt_:>7}{ratio:>11.2f}{pc:>9.0f}{pop:>9.0f}")
    xs = [r[3] for r in rows]
    print(f"\nSpearman(selection ratio, GDP per capita {yb2}) = {spearman(xs, [r[4] for r in rows]):.3f}  (n=31)")
    print(f"Spearman(raw designation count, GDP per capita) = {spearman([r[1] for r in rows], [r[4] for r in rows]):.3f}")
    print(f"Spearman(raw designation count, population)     = {spearman([r[1] for r in rows], [r[5] for r in rows]):.3f}")
    xs_t = [desig_title[p] / max(sum(desig_title.values()), 1) / (popb[p] / totpop) for p in PROVINCES]
    print(f"Spearman(TITLE-only selection ratio, GDPpc)     = {spearman(xs_t, [pcb[p] for p in PROVINCES]):.3f}")
    # by tercile
    order = sorted(PROVINCES, key=lambda p: pcb[p])
    terc = {p: ("low" if i < 10 else "mid" if i < 21 else "high") for i, p in enumerate(order)}
    print("\nby GDPpc tercile (10/11/10 provinces): designation share vs population share")
    for t in ("low", "mid", "high"):
        ps = [p for p in PROVINCES if terc[p] == t]
        print(f"  {t:<5} desig share {pct(sum(desig[p] for p in ps), tot):>6}  pop share {pct(sum(popb[p] for p in ps), totpop):>6}"
              f"  provinces: {' '.join(ps)}")

    # --- implementing side ----------------------------------------------------
    hr("4. IMPLEMENTING SIDE: who echoes central pilot instruments (diffusion_events, source_implementing=1)")
    # sub-national docs per province (coverage denominator)
    docs_by_prov = Counter()
    sites_by_prov = defaultdict(set)
    unmapped = Counter()
    for site, lvl, n in conn.execute(f"""
        SELECT d.site_key, s.admin_level, count(*) FROM documents d JOIN sites s ON s.site_key=d.site_key
        WHERE s.admin_level IN ('provincial','municipal','department','district') AND {DATE_OK}
        GROUP BY 1,2"""):
        p = site_province(site)
        if p:
            docs_by_prov[p] += n
            sites_by_prov[p].add(site)
        else:
            unmapped[site] += n
    if unmapped:
        print("UNMAPPED sub-national sites (excluded):", dict(unmapped))
    pilot_ids = {i for g in G for i in g["all_ids"]}  # every mirror copy of every guideline
    ev = conn.execute("""
        SELECT de.anchor_id, de.source_id, de.lag_days, d.site_key, de.match_type
        FROM diffusion_events de JOIN documents d ON d.id=de.source_id
        WHERE de.anchor_level='central' AND de.source_implementing=1 AND de.lag_days IS NOT NULL AND de.lag_days>=0
    """).fetchall()
    print(f"implementing events (central anchors, lag>=0): {len(ev)}; of which anchor is a pilot guideline: "
          f"{sum(1 for e in ev if e[0] in pilot_ids)}")

    def impl_table(events, label):
        by = defaultdict(lambda: dict(n=0, anchors=set(), lags=[]))
        for a, s, lag, site, _mt in events:
            p = site_province(site)
            if not p:
                continue
            by[p]["n"] += 1
            by[p]["anchors"].add(a)
            by[p]["lags"].append(lag)
        yb2, pcb = gdp.pc_year(2015)
        order = sorted(PROVINCES, key=lambda p: pcb[p])
        terc = {p: ("low" if i < 10 else "mid" if i < 21 else "high") for i, p in enumerate(order)}
        print(f"\n{label}")
        print(f"{'province':<8}{'terc':>5}{'events':>8}{'anchors':>8}{'docs':>8}{'ev/1k docs':>11}{'med lag':>9}")
        rows = []
        for p in sorted(by, key=lambda p: -by[p]["n"]):
            d = by[p]
            rows.append((p, terc[p], d["n"], len(d["anchors"]), docs_by_prov[p],
                         1000.0 * d["n"] / docs_by_prov[p] if docs_by_prov[p] else float("nan"),
                         statistics.median(d["lags"])))
        for r in rows:
            print(f"{r[0]:<8}{r[1]:>5}{r[2]:>8}{r[3]:>8}{r[4]:>8}{r[5]:>11.2f}{r[6]:>9.0f}")
        print("by GDPpc tercile (provinces with any corpus coverage):")
        for t in ("low", "mid", "high"):
            ps = [p for p in PROVINCES if terc[p] == t and docs_by_prov[p] > 0]
            n = sum(by[p]["n"] for p in ps)
            dd = sum(docs_by_prov[p] for p in ps)
            lags = [l for p in ps for l in by[p]["lags"]]
            anchors = set().union(*(by[p]["anchors"] for p in ps)) if ps else set()
            print(f"  {t:<5} provinces covered {len(ps):2d}  events {n:5d}  docs {dd:6d}  ev/1k docs {1000.0 * n / dd if dd else float('nan'):6.2f}"
                  f"  distinct anchors {len(anchors):4d}  median lag {statistics.median(lags) if lags else float('nan'):5.0f}d")
        # same, excluding Guangdong
        ps_ng = [p for p in PROVINCES if p != "广东" and docs_by_prov[p] > 0]
        print("  excluding 广东: Spearman(ev/1k docs, GDPpc) over covered provinces = "
              f"{spearman([1000.0 * by[p]['n'] / docs_by_prov[p] for p in ps_ng], [pcb[p] for p in ps_ng]):.3f} (n={len(ps_ng)})")
        ps_all = [p for p in PROVINCES if docs_by_prov[p] > 0]
        print("  all covered: Spearman(ev/1k docs, GDPpc) = "
              f"{spearman([1000.0 * by[p]['n'] / docs_by_prov[p] for p in ps_all], [pcb[p] for p in ps_all]):.3f} (n={len(ps_all)})"
              f"; Spearman(median lag, GDPpc) = "
              f"{spearman([statistics.median(by[p]['lags']) if by[p]['lags'] else 9e9 for p in ps_all], [pcb[p] for p in ps_all]):.3f}")

    impl_table([e for e in ev if e[0] in pilot_ids], "4a. anchors = pilot guidelines only")
    impl_table(ev, "4b. all central anchors (any instrument)")
    # continuous-coverage provinces only (R2 set from recentralization memo: bj sh gd js hlj gz zhongshan huizhou jieyang wuhan)
    cont_sites = {"bj", "sh", "gd", "js", "hlj", "gz", "zhongshan", "huizhou", "jieyang", "wuhan"}
    impl_table([e for e in ev if e[3] in cont_sites], "4c. continuously-crawled sub-national sites only (R2 set)")

    # --- designated vs implementing: do named pilot provinces actually echo? ----
    hr("5. DESIGNATION -> IMPLEMENTATION: do the provinces a guideline names show up as its implementers?")
    impl_by_anchor = defaultdict(set)
    for a, s, lag, site, _mt in ev:
        p = site_province(site)
        if p:
            impl_by_anchor[a].add(p)
    both = []
    for g in SEL:
        imp = set().union(*(impl_by_anchor.get(i, set()) for i in g["all_ids"]))
        if imp:
            both.append((g, imp))
    print(f"selective guidelines with >=1 mapped implementing event: {len(both)} / {len(SEL)}")
    if both:
        hit = sum(1 for g, imp in both if set(g["body_sites"]) & imp)
        print(f"  of these, implementer set overlaps the named pilot set: {hit} ({pct(hit, len(both))})")
        covered = Counter()
        for g, imp in both:
            for p in g["body_sites"]:
                covered[p] += 1
        print("  (named provinces among these anchors, by corpus coverage of that province: "
              + ", ".join(f"{p}:{covered[p]}/{'yes' if docs_by_prov[p] else 'NO'}" for p, _ in covered.most_common(12)) + ")")

    # --- examples -------------------------------------------------------------
    hr("6. EXAMPLES (most-named provinces per guideline, for audit)")
    ex = sorted(SEL, key=lambda g: -sum(g["body_sites"].values()))[:12]
    for g in ex:
        top = ", ".join(f"{p}×{n}" for p, n in g["body_sites"].most_common(6))
        print(f"  {g['date']}  [{g['site']}] {g['title'][:60]}  -> {top}")
    print("\nsingle-province designations, sample:")
    for g in [g for g in SEL if g["n_body"] == 1][:10]:
        print(f"  {g['date']}  [{g['site']}] {g['title'][:60]}  -> {list(g['body_sites'])[0]}")

    if args.dump:
        with open(args.dump, "w", encoding="utf8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "date", "site", "title", "n_provinces", "provinces", "pos_mean", "mean_percentile"])
            byid = {r["id"]: r for r in res_all}
            for g in SEL:
                r = byid.get(g["id"])
                w.writerow([g["id"], g["date"], g["site"], g["title"], g["n_body"],
                            " ".join(f"{p}:{n}" for p, n in g["body_sites"].most_common()),
                            r["pos_mean"] if r else "", f"{r['mean_pr']:.3f}" if r else ""])
        print(f"\nper-guideline table written to {args.dump}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-gdp", help="assemble data/provincial_gdp.csv from local NBS xls + Wikipedia html")
    b.add_argument("--nbs-dir", required=True, help="dir holding the NBS xls files named as in NBS_TABLES")
    b.add_argument("--wiki-dir", required=True, help="dir holding the two Wikipedia html pages named as in WIKI_PAGES")
    b.add_argument("--out", default=str(DEFAULT_GDP))
    a = sub.add_parser("analyze", help="run the descriptive site-selection test (read-only)")
    a.add_argument("--db", default=str(DEFAULT_DB))
    a.add_argument("--gdp", default=str(DEFAULT_GDP))
    a.add_argument("--dump", default=None, help="optional CSV of per-guideline pilot sets")
    args = ap.parse_args()
    if args.cmd == "build-gdp":
        build_gdp(args)
    else:
        analyze(args)


if __name__ == "__main__":
    main()
