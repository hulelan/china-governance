"""Shared administrative geography for the analysis layer.

One place for the facts both `scripts/build_doc_identity.py` (jurisdiction_chain,
the genre flip) and `scripts/rnd/analysis/build_diffusion_events.py` (province_of,
the provincial-anchor join) need, so neither hand-maintains its own copy:

  CITY_PROVINCE   prefecture-level division (地级市/自治州/地区/盟) -> province name,
                  from data/city_province.csv (354 rows; the four 直辖市 map to
                  themselves). Province NAMES as the CSV writes them (广东省,
                  内蒙古自治区, 北京市).
  DISTRICT_CITY   bare district names the corpus emits WITHOUT a city prefix
                  (龙华区 -> 深圳市; 硚口区 -> 武汉市) + the 16 Beijing districts.
  PROVINCE_CODE   province name -> the 2-letter code `province_of` returns. Existing
                  codes (gd js bj sh cq fj hn jl ln nx sd xz zj hlj qh xj) are kept
                  verbatim because `diffusion_events` / the tracker join on them; the
                  rest follow ISO 3166-2:CN (贵州 gz, 河南 ha, 海南 hi, 陕西 sn, 河北 he)
                  so 山西 sx vs 陕西 sn and 湖北 hb vs 河北 he stay distinct. No 兵团
                  unit: the CSV maps its cities (阿拉尔/北屯/…) to 新疆.
  province_code_of_site_name(name)
                  derives the code from a site's display name in `sites.name`
                  ("晋城市", "Suzhou, Anhui (宿州市)", "Wuhan Qiaokou District
                  (武汉硚口区)", "Wuhan Municipality"). The Chinese place is taken
                  from the parenthesised part first, else the leading CJK run, else
                  the English alias table below; then resolved as province / city /
                  bare district / '<city-prefix><district>'. Unknown -> None.

    python3 scripts/rnd/analysis/geo.py --self-test
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CITY_PROVINCE_CSV = ROOT / "data" / "city_province.csv"


def load_city_province(path=CITY_PROVINCE_CSV):
    """city -> province for every prefecture-level division (地级市/自治州/地区/盟);
    the four 直辖市 map to themselves (they ARE their province)."""
    out = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[row["city"].strip()] = row["province"].strip()
    return out


CITY_PROVINCE = load_city_province()

# Bare district names the corpus emits WITHOUT a city prefix (Shenzhen district sites
# write 龙华区X / 坪山区X; Wuhan / Nanjing / Qingdao / Chongqing bureaus likewise).
# A '<city><district>' locality (深圳市龙华区, 北京市密云区) is parsed by prefix instead.
DISTRICT_CITY = {
    "福田区": "深圳市", "罗湖区": "深圳市", "南山区": "深圳市", "盐田区": "深圳市",
    "宝安区": "深圳市", "龙岗区": "深圳市", "龙华区": "深圳市", "坪山区": "深圳市",
    "光明区": "深圳市", "光明新区": "深圳市", "大鹏新区": "深圳市", "前海合作区": "深圳市",
    "硚口区": "武汉市", "洪山区": "武汉市", "江汉区": "武汉市", "东湖高新区": "武汉市",
    "江宁区": "南京市", "崂山区": "青岛市", "福山区": "烟台市", "仲恺高新区": "惠州市",
    "龙门县": "惠州市", "周矶管理区": "潜江市", "后湖管理区": "潜江市",
    "重庆高新区": "重庆市", "重庆经开区": "重庆市", "万盛经开区": "重庆市",
    "莱芜": "济南市", "莱芜区": "济南市",  # 莱芜市 was merged into 济南 in 2019 (not in the CSV)
}
_BJ_DISTRICTS = ("东城区 西城区 朝阳区 丰台区 石景山区 海淀区 门头沟区 房山区 通州区 顺义区 "
                 "昌平区 大兴区 怀柔区 平谷区 密云区 延庆区 北京经济技术开发区").split()
DISTRICT_CITY.update({d: "北京市" for d in _BJ_DISTRICTS})

# Province name -> 2-letter code (see module docstring for the stability rule).
PROVINCE_CODE = {
    "北京市": "bj", "天津市": "tj", "河北省": "he", "山西省": "sx", "内蒙古自治区": "nm",
    "辽宁省": "ln", "吉林省": "jl", "黑龙江省": "hlj",
    "上海市": "sh", "江苏省": "js", "浙江省": "zj", "安徽省": "ah", "福建省": "fj",
    "江西省": "jx", "山东省": "sd",
    "河南省": "ha", "湖北省": "hb", "湖南省": "hn",
    "广东省": "gd", "广西壮族自治区": "gx", "海南省": "hi",
    "重庆市": "cq", "四川省": "sc", "贵州省": "gz", "云南省": "yn", "西藏自治区": "xz",
    "陕西省": "sn", "甘肃省": "gs", "青海省": "qh", "宁夏回族自治区": "nx",
    "新疆维吾尔自治区": "xj",
}
PROVINCE_NAME = {v: k for k, v in PROVINCE_CODE.items()}
assert len(PROVINCE_NAME) == len(PROVINCE_CODE) == 31, "province codes must be unique"
_missing = set(CITY_PROVINCE.values()) - set(PROVINCE_CODE)
assert not _missing, f"city_province.csv names provinces without a code: {_missing}"

# English-only `sites.name` values (no Chinese anywhere in the string) -> Chinese place.
# Only the sites that actually need it (listed from the live `sites` table, 2026-10);
# a name with a parenthesised Chinese part never consults this table.
SITE_NAME_ALIASES = {
    "Chongqing Municipality": "重庆市",
    "Guangzhou": "广州市",
    "Hangzhou Municipality": "杭州市",
    "Suzhou Municipality": "苏州市",
    "Wuhan Municipality": "武汉市",
    "Heyuan": "河源市", "Huizhou": "惠州市", "Jiangmen": "江门市", "Jieyang": "揭阳市",
    "Shantou": "汕头市", "Shanwei": "汕尾市", "Shaoguan": "韶关市", "Yangjiang": "阳江市",
    "Yunfu": "云浮市", "Zhaoqing": "肇庆市", "Zhongshan": "中山市", "Zhuhai": "珠海市",
    "Shenzhen Main Portal": "深圳市", "Shenzhen Investment Portal": "深圳市",
    "Dapeng New District": "深圳市", "Futian District": "深圳市", "Guangming District": "深圳市",
    "Longgang District": "深圳市", "Luohu District": "深圳市", "Longhua District": "深圳市",
    "Nanshan District": "深圳市", "Pingshan District": "深圳市", "Yantian District": "深圳市",
}

_CJK_PAREN = re.compile(r"[（(]\s*([一-鿿][^（）()]*?)\s*[)）]")
_CJK_LEAD = re.compile(r"^[一-鿿]+")
_DIVISION_TAIL = re.compile(r"(?:市|区|县|旗|园区|新区|管理区|高新区|经开区)$")


def chinese_place(site_name):
    """The Chinese place name inside a `sites.name` value, or None."""
    if not site_name:
        return None
    s = site_name.strip()
    m = _CJK_PAREN.search(s)
    if m:
        return m.group(1)
    m = _CJK_LEAD.match(s)
    if m:
        return m.group(0)
    return SITE_NAME_ALIASES.get(s)


def province_name_of_place(place):
    """Province NAME of a Chinese place: a province itself, a prefecture-level city,
    a bare district (DISTRICT_CITY), or '<city-prefix><district>' (武汉硚口区,
    苏州张家港市, 北京大兴区, 深圳市龙华区). None when unknown."""
    if not place:
        return None
    if place in PROVINCE_CODE:
        return place
    if place in CITY_PROVINCE:
        return CITY_PROVINCE[place]
    city = DISTRICT_CITY.get(place)
    if city:
        return CITY_PROVINCE.get(city)
    if _DIVISION_TAIL.search(place):
        # Strip a leading city (with or without its own 市) and resolve the city.
        for k in range(2, min(5, len(place) - 1) + 1):
            head = place[:k]
            for cand in (head, head + "市"):
                if cand in CITY_PROVINCE and len(place) > len(cand):
                    return CITY_PROVINCE[cand]
    return None


def province_code_of_site_name(site_name):
    """2-letter province code derived from a site's display name, or None."""
    prov = province_name_of_place(chinese_place(site_name))
    return PROVINCE_CODE.get(prov) if prov else None


def _self_test():
    cases = [
        ("晋城市", "sx"), ("西安市", "sn"),                      # Shanxi vs Shaanxi
        ("潜江市", "hb"), ("Shijiazhuang (石家庄市)", "he"),     # Hubei vs Hebei
        ("Suzhou, Anhui (宿州市)", "ah"), ("Suzhou Municipality", "js"),
        ("Wuhan Municipality", "hb"), ("Wuhan Qiaokou District (武汉硚口区)", "hb"),
        ("Zhangjiagang (苏州张家港市)", "js"), ("Beijing Daxing District (北京大兴区)", "bj"),
        ("锡林郭勒盟", "nm"), ("阿坝藏族羌族自治州", "sc"),
        ("Linxia Hui Prefecture (临夏回族自治州)", "gs"), ("Laiwu (莱芜)", "sd"),
        ("Chongqing Municipality", "cq"), ("Dapeng New District", "gd"),
        ("广东省", "gd"), ("Nowhere Portal", None), ("", None), (None, None),
    ]
    bad = [(n, want, province_code_of_site_name(n)) for n, want in cases
           if province_code_of_site_name(n) != want]
    for n, want, got in bad:
        print(f"  FAIL {n!r}: want {want!r} got {got!r}")
    print(f"geo self-test: {len(cases) - len(bad)}/{len(cases)} passed")
    return not bad


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(0 if _self_test() else 1)
    print(__doc__)
