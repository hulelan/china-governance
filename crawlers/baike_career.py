"""Career-text parser for Baidu Baike biographies (officials.db).

Pure stdlib, no network: `crawlers/baike.py --parse` re-parses the text already
stored in `officials.baike_career_text`.

What a record is
----------------
ONE ROW PER HELD POST BODY, not one row per text line. A line such as

    2017-2022年 中央政治局委员，北京市委书记，北京2022年冬奥会…组织委员会主席、党组书记

yields three rows with the same dates and raw_text:

    organization=中央政治局   position=委员
    organization=北京市委     position=书记
    organization=北京2022年冬奥会和冬残奥会组织委员会  position=主席、党组书记

`organization` is a CANONICAL KEY, so two officials in the same body get the
same string and `scripts/compute_overlaps.py` can pair them by equality:

  * locality bodies     北京市委 / 北京市政府 / 浙江省委组织部 / 三明市委
                        (the deepest locality names the body; a 区 keeps its
                        parent city because district names repeat nationally)
  * elided prefixes     "省委常委、组织部部长" after 浙江省… -> 浙江省委, 浙江省委组织部;
                        "市长" after 北京市委… -> 北京市政府
  * institutions        cut at the first institution suffix: 清华大学化工系 -> 清华大学,
                        外交部国际司 -> 外交部
  * 党组/党委 suffixes    fold into the host body (环境保护部党组书记 -> 环境保护部)

Dropped on purpose: education lines (学习/攻读/毕业…), awards and honours
(获…奖/称号/评为/授予/院士), births and deaths, publications, and any clause
with no recognisable post title.

Date prefixes handled (298 shapes were measured in the stored text): `Y.M-Y.M`,
`Y-Y年`, `Y年-Y年`, `Y年M月至Y年M月`, `Y.M——Y.M，`, `Y － Y`, single `Y年M月，任…`
and the open-ended `Y.M-` / `Y-` / `Y年至今`, with any of - — – － ~ 至 到 as the
separator and optional `，`/`：` after the range.

Open-ended ranges keep end_year NULL (the web page prints "now"). A single-date
entry ("1952年7月任…") gets its end from the next dated line, capped at 5 years.
"""

import re

# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

_FW = str.maketrans("０１２３４５６７８９．：，；（）", "0123456789.:,;()")

_DATE = (
    r"(\d{4})"
    r"(?:\s*[./]\s*(\d{1,2})(?:[./]\d{1,2})?(?!\d)"
    r"|\s*年(?:\s*(\d{1,2})\s*月)?(?:\s*\d{1,2}\s*日)?(?:[初底末春夏秋冬]|上半年|下半年)?)?"
)
_SEP = r"\s*(?:[-—–－─~～]+|至|到)\s*"
_PREFIX = re.compile(
    r"^" + _DATE +
    r"(?:(?P<sep>" + _SEP + r")(?:" + _DATE + r"|(?P<m2>\d{1,2})\s*月(?:底|初)?|(?P<now>至?今|现在|现今))?)?"
    r"\s*年?\s*[,:;、\s]*"
)

MIN_YEAR, MAX_YEAR = 1900, 2030


def split_date_prefix(line):
    """Return (start_y, start_m, end_y, end_m, open_ended, is_range, rest) or None."""
    m = _PREFIX.match(line)
    if not m:
        return None
    g = m.groups()
    sy = int(g[0])
    sm = g[1] or g[2]
    sm = int(sm) if sm else None
    sep = m.group("sep")
    ey = em = None
    open_ended = False
    if sep:
        if g[4]:
            ey = int(g[4])
            em = g[5] or g[6]
            em = int(em) if em else None
        elif m.group("m2"):
            ey, em = sy, int(m.group("m2"))
        else:
            open_ended = True
    if not (MIN_YEAR <= sy <= MAX_YEAR):
        return None
    if sm is not None and not (1 <= sm <= 12):
        sm = None
    if em is not None and not (1 <= em <= 12):
        em = None
    if ey is not None and (ey < sy or ey - sy > 45 or ey > MAX_YEAR):
        return None
    return sy, sm, ey, em, open_ended, bool(sep), line[m.end():]


# --------------------------------------------------------------------------
# Localities
# --------------------------------------------------------------------------

PROVINCES = {
    "北京": "Beijing", "天津": "Tianjin", "上海": "Shanghai", "重庆": "Chongqing",
    "河北": "Hebei", "山西": "Shanxi", "辽宁": "Liaoning", "吉林": "Jilin",
    "黑龙江": "Heilongjiang", "江苏": "Jiangsu", "浙江": "Zhejiang", "安徽": "Anhui",
    "福建": "Fujian", "江西": "Jiangxi", "山东": "Shandong", "河南": "Henan",
    "湖北": "Hubei", "湖南": "Hunan", "广东": "Guangdong", "海南": "Hainan",
    "四川": "Sichuan", "贵州": "Guizhou", "云南": "Yunnan", "陕西": "Shaanxi",
    "甘肃": "Gansu", "青海": "Qinghai", "台湾": "Taiwan",
    "内蒙古": "Inner Mongolia", "广西": "Guangxi", "西藏": "Tibet",
    "宁夏": "Ningxia", "新疆": "Xinjiang",
}
_MUNI = ("北京", "天津", "上海", "重庆")
_AUTO = {"内蒙古": "", "广西": "壮族", "西藏": "", "宁夏": "回族", "新疆": "维吾尔"}


def _prov_alternatives():
    alts = []
    for p in PROVINCES:
        if p in _MUNI:
            alts.append((p + "市", p + "市"))
        elif p in _AUTO:
            canon = p + "自治区"
            alts.append((p + _AUTO[p] + "自治区", canon))
            alts.append((canon, canon))
        else:
            alts.append((p + "省", p + "省"))
    alts.sort(key=lambda a: -len(a[0]))
    return alts


_PROV_ALTS = _prov_alternatives()
_PROV_RE = re.compile("^(?:" + "|".join(re.escape(a) for a, _ in _PROV_ALTS) + ")")
_PROV_CANON = dict(_PROV_ALTS)

_HAN = r"[一-龥]"
_CITY_RE = re.compile(r"^(" + _HAN + r"{2,8}?(?:自治州|地区|市|盟))")
_COUNTY_RE = re.compile(
    r"^(" + _HAN + r"{1,8}?(?:自治县|自治旗|县(?!级)|(?<![军战社防分片地山矿林灌特专辖发范园校小库灾牧渔])区(?![域别分间划])|旗))"
)
# A "city"/"county" name containing any of these is an institution, not a place.
_NOT_PLACE = re.compile(
    r"中国|国家|中央|全国|共产|人民|政府|大学|学院|公司|集团|银行|解放|革命|工作|管理|建设|委员|"
    r"[部委局院厅省办会党团军处室厂矿社队站所校系司科和与及的任在于兼为从到由]"
)

_PARTY_HEAD = re.compile(r"^(?:党委|委员会|委(?!员))")
_GOV_HEAD = re.compile(r"^(?:人民政府|政府|人民委员会|行政公署|行署)")
_NPC_HEAD = re.compile(r"^(?:人民代表大会常务委员会|人民代表大会|人大常委会|人大)")
_CPPCC_HEAD = re.compile(r"^(?:政协|政治协商会议)")
_DISC_HEAD = re.compile(r"^(?:纪律检查委员会|纪委|纪检委)")
_REV_HEAD = re.compile(r"^(?:革命委员会|革委会)")
_SUP_HEAD = re.compile(r"^(?:监察委员会|监委)")

# --------------------------------------------------------------------------
# Titles
# --------------------------------------------------------------------------

_TITLE_CORES = sorted("""
总书记 第一书记 书记 省长 市长 县长 区长 州长 盟长 旗长 乡长 镇长 专员 部长 厅长 局长 司长 处长
科长 股长 署长 关长 行长 院长 校长 所长 馆长 社长 台长 站长 厂长 矿长 队长 组长 团长 师长 旅长
军长 营长 连长 排长 舰长 会长 理事长 董事长 委员长 秘书长 检察长 审计长 参谋长 庭长 总理 主席
主任委员 主任 国务委员 委员 常委 总经理 经理 总裁 总编辑 总编 主编 编辑 记者 总工程师 工程师 总会计师
总经济师 技术员 研究员 教授 讲师 教师 教员 助教 秘书 干事 干部 科员 职员 职工 工人 知青 社员 战士
司令员 司令 政治委员 政委 教导员 指导员 参谋 巡视员 调研员 督学 参事 顾问 大使 公使 领事 参赞
成员 负责人 检察员 审判员 法官 理事 医师 医生 会计 办事员 文书 学徒 技师 厂医 助理 总监 监事长
行署专员 政务委员 检察官 警员 民警 总队长 支队长 大队长 中队长 站长 段长 校务委员
董事 主任科员 设计员 资料员 助工 一秘 二秘 三秘 随员 宣传员 通讯员 保管员 统计员 辅导员 教练员
飞行员 驾驶员 调度员 检验员 化验员 施工员 工作人员 翻译 实习员 研究实习员 副教授 博士后 教练 队员
炊事员 卫生员 通信员 警卫员 勤务员 话务员 报务员 译电员 机要员 文化教员 特派员 巡视组组长 监事 行员
推事 县令 知事 厅务会议成员 发言人 工长 班长 车间主任 劳动锻炼
""".split(), key=len, reverse=True)
_RANK = (
    r"(?:(?:第[一二三四五六七八九十]|常务|执行|代理|代|名誉|首席|常驻|总|副|正|见习|主持[^,，、]{0,10}?的"
    r"|[正副]?(?:省|部|厅|局|司|处|科|军|师|团|营|连)级)+)?"
)
_TITLE_RE = re.compile(
    "(" + _RANK + "(?:" + "|".join(_TITLE_CORES) + "))"
    r"(?:[、/和及兼](?:" + _RANK + "(?:" + "|".join(_TITLE_CORES) + ")))*$"
)
_REP_TITLE_RE = re.compile(r"((?:首席|常驻|总|副|谈判)+代表)$")
_GOV_HEAD_TITLE = re.compile(r"(?:省长|市长|县长|区长|州长|盟长|旗长|专员)")

# --------------------------------------------------------------------------
# What is not a post
# --------------------------------------------------------------------------

EDU_RE = re.compile(
    r"学习|攻读|读书|就读|进修|毕业|入学|考入|考取|培训|留学|研修|深造|求学|上学|"
    r"学位|学历|本科|大专|中专|研究生(?!院|部|处|工作|会)|博士生|硕士生|学生(?!会|工作|处|部)|学员(?!队|大队)"
)
AWARD_RE = re.compile(
    r"荣?获(?!准|释|救)|奖(?!励办|惩|学金管理)|称号|评为|被评|授予|被授|勋章|军衔|院士|入选|享受|津贴|"
    r"逝世|去世|病逝|病故|牺牲|出生|生于|诞辰|出版|发表|《|追悼|遗体|开除|处分|判处|立案|逮捕|审查|调查"
)
_NARRATIVE_VERB = re.compile(
    r"(?:当选为?|增选为|补选为|被?选为|晋升为?|升为|任命\S{0,4}?为|(?<![主责信委放上常])任(?![务命职期何免教用内]))"
)
_LEAD_JUNK = re.compile(
    r"^(?:(?:先后|历|曾|又|并|后|现|时|改|调|升|转|出|担|继|仍|还|同时|再次|连续|正式)*"
    r"(?:兼任|担任|任命为|任|当选为|当选|增选为|补选为|选为|被任命为|被选为|晋升为|晋升|升为|兼|为|是)"
    r"|在|于|到|赴|回|入|进入|调入|调至|调|原|同年|同时|下放|借调)"
)
_REMOVAL = re.compile(r"任免|免去|不再担任|不再兼任|卸任|辞去|离任|撤销|罢免|免职|被捕|入狱|离休|退休|退居")
_SUBJECT_IN = re.compile(r"^[\u4e00-\u9fa5·]{0,6}?(?:先后|曾)?在(?=.{4})")
_TAIL_JUNK = re.compile(r"(?:等职务?|职务|一职|等|[。.;；,，、:：\s])+$")
_SESSION = re.compile(
    r"(?:中共|党的|中国共产党)?第?[一二三四五六七八九十百\d]+(?:[、至到—\-][一二三四五六七八九十百\d]+)*"
    r"(?:届(?:[、和及]第?[一二三四五六七八九十百\d]+届)*|大)(?!队)"
)
_PAREN = re.compile(r"[（(][^（()）]*[)）]")

# --------------------------------------------------------------------------
# Organisation keys
# --------------------------------------------------------------------------

_ALIASES = [
    (re.compile(r"^中华人民共和国(?=.{2})"), ""),
    (re.compile(r"^政协全国委员会"), "全国政协"),
    (re.compile(r"^(?:中国共产党|中共)(?=中央)"), ""),
    (re.compile(r"^(?:中国共产党|中共)"), ""),
    (re.compile(r"^中央委员会(?=政治局|书记处|总书记|办公厅|组织部|宣传部|统战部|党校)"), "中央"),
    (re.compile(r"^党中央"), "中央"),
    (re.compile(r"^中组部"), "中央组织部"),
    (re.compile(r"^中宣部"), "中央宣传部"),
    (re.compile(r"^中联部"), "中央对外联络部"),
    (re.compile(r"^中办"), "中央办公厅"),
    (re.compile(r"^(?:中纪委|中央纪律检查委员会)"), "中央纪委"),
    (re.compile(r"^(?:中央军事委员会|中共中央军委)(?!员)"), "中央军委"),
    (re.compile(r"^(?:全国人民代表大会常务委员会|全国人大常委会)"), "全国人大常委会"),
    (re.compile(r"^全国人民代表大会"), "全国人大"),
    (re.compile(r"^(?:中国人民政治协商会议全国委员会|中国人民政治协商会议|人民政协全国委员会)"), "全国政协"),
    (re.compile(r"^(?:国家发改委|国家发展改革委|国家发展和改革委)(?!员)"), "国家发展和改革委员会"),
    (re.compile(r"^国家计委"), "国家计划委员会"),
    (re.compile(r"^中顾委"), "中央顾问委员会"),
    (re.compile(r"^中科院"), "中国科学院"),
    (re.compile(r"^国家经委"), "国家经济委员会"),
    (re.compile(r"^(?:共青团中央|团中央)"), "共青团中央"),
    (re.compile(r"^新华社"), "新华通讯社"),
]

# Institution suffixes, longest first. The LEFTMOST occurrence ends the key.
_SUFFIXES = sorted("""
集团有限公司 集团公司 有限责任公司 股份有限公司 有限公司 总公司 公司 集团 大学 学院 党校 学校 中学 小学
委员会 总局 管理局 局 总署 署 研究院 科学院 设计院 法院 检察院 医院 院 通讯社 报社 出版社 杂志社 公社 合作社
分社 研究所 所 办公厅 办公室 研究室 中心 协会 学会 联合会 总工会 工会 基金会 研究会 促进会 联盟 银行
总行 分行 电视台 电台 广播电台 油田 农场 林场 大队 军区 战区 舰队 集团军 野战军 方面军 兵团 军团
纵队 总部 总队 支队 妇联 工商联 文联 侨联 残联 科协 作协 青联 台联 社科联 记协 贸促会 领导小组 指挥部 司令部 政治部 后勤部 装备部 参谋部 工委 团委 党委 乡 镇 街道 报 馆 站
""".split(), key=len, reverse=True)
_SUFFIX_RE = re.compile(
    "(?:" + "|".join(_SUFFIXES) + r"|(?<![干全西东南北中内外本分总支])部(?![队长署门分落])"
    r"|厂(?!长)|矿(?!业|山|产|务|冶|区|物)|委(?!员|托|派)|厅|办(?!公|事|法|理|学|案)|军(?!事|队|工|委|政|需|械|医|分|人|民|垦|转)|师(?!范|傅|资)|旅(?!游|行))"
)
_PARTY_SUFFIX = re.compile(r"(?:机关党委|党组|党委|党总支|党支部|临时党委|分党组|党的核心小组|核心小组)$")
_GENERIC_DEPTS = {
    "组织部", "宣传部", "统战部", "政法委", "政法委员会", "办公厅", "办公室", "研究室", "政研室",
    "政策研究室", "秘书处", "团委", "工会", "纪委", "纪检组", "党校", "体委", "人事处", "干部处",
    "综合处", "农工部", "工业部", "财贸部", "农村工作部", "统一战线工作部", "机关工委", "直属机关工委",
    "党史研究室", "讲师团", "老干部局", "机要局", "保密局", "信访局", "督查室",
}
_PARTY_DEPTS = {
    "组织部", "宣传部", "统战部", "政法委", "政法委员会", "政研室", "政策研究室", "农工部", "工业部",
    "财贸部", "农村工作部", "统一战线工作部", "机关工委", "直属机关工委", "党史研究室", "讲师团",
    "老干部局", "党校",
}
_ELIDED_INST = re.compile(
    r"^(?:校|院|系|所|厂|矿|公司|集团|总公司|行|社|部|厅|局|委|办|署|台|馆|会|团|总行|分行|本)"
    r"(?=党委|党组|党总支|党支部|团委|工会|纪委|纪检|机关|办公室|学术|务委|务会|长|直|领导|编委|董事|监事)"
)
_ELIDED_LOC = re.compile(r"^(自治区|省|市|地|州|盟|县|区|旗)(?=党委|委|政府|人民政府|人大|政协|纪委|纪律|监委|革委|革命委|直|[^场域级部际内外属])")
_STOP_KEYS = {
    "中央", "国家", "全国", "中国", "解放军", "中国人民解放军", "人民解放军", "党委", "党组", "政府",
    "委员会", "办公室", "办公厅", "公司", "集团", "大学", "学院", "部队", "机关", "地方", "军队",
}
CENTRAL_ORGS = [
    "国务院", "中央", "全国人大", "全国政协", "中纪委", "国家", "最高人民法院", "最高人民检察院",
    "中国人民银行", "外交部", "国防部", "财政部", "商务部", "教育部", "科技部", "公安部", "民政部",
    "司法部", "水利部", "农业部", "卫生部", "文化部", "铁道部", "交通部", "监察部", "人事部", "建设部",
    "审计署", "总局", "中国科学院", "中国工程院", "中国社会科学院", "新华通讯社", "人民日报",
    "解放军", "总参", "总政", "总后", "总装", "共青团中央", "全国总工会", "全国妇联",
]


class _Ctx:
    __slots__ = ("prov", "city", "county", "last", "inst", "party", "year")

    def __init__(self, year=None):
        self.prov = self.city = self.county = self.last = self.inst = self.party = None
        self.year = year


def _parse_locality(rem, ctx):
    """Consume a leading locality chain. Returns (prov, city, county, rest) or None."""
    prov = city = county = None
    rest = rem
    m = _PROV_RE.match(rest)
    if m:
        prov = _PROV_CANON[m.group(0)]
        rest = rest[m.end():]
    m = _CITY_RE.match(rest)
    if m and not _NOT_PLACE.search(m.group(1)[:-1]) and not _PROV_RE.match(m.group(1)):
        city = m.group(1)
        rest = rest[m.end():]
    for _ in range(2):
        m = _COUNTY_RE.match(rest)
        if not (m and not _NOT_PLACE.search(m.group(1)[:-1])):
            break
        if county:
            city = city or county
        county = m.group(1)
        rest = rest[m.end():]
    if not (prov or city or county):
        return None
    return prov, city, county, rest


def _loc_name(prov, city, county):
    """Deepest locality names the body; a 区 keeps its parent."""
    if county:
        if county.endswith("区") or county.endswith("旗"):
            return (city or prov or "") + county
        return county
    return city or prov


def _cut(text):
    """Cut `text` after its first institution suffix. Returns (head, tail)."""
    m = _SUFFIX_RE.search(text, 1)
    if not m:
        return text, ""
    return text[:m.end()], text[m.end():]


def _locality_body(loc, rest, ctx, gov_title):
    """Key for `loc` + `rest` (rest is what follows the place name)."""
    for head, name in ((_DISC_HEAD, "纪委"), (_SUP_HEAD, "监委"), (_REV_HEAD, "革委会"),
                       (_NPC_HEAD, "人大"), (_CPPCC_HEAD, "政协"), (_GOV_HEAD, "政府"),
                       (_PARTY_HEAD, "委")):
        m = head.match(rest)
        if not m:
            continue
        body = loc + ("党委" if name == "委" and loc.endswith("自治区") else name)
        tail = rest[m.end():]
        if name == "委":
            ctx.party = body
        tail = _PARTY_SUFFIX.sub("", tail)
        if name in ("委", "政府") and tail:
            dept, tail2 = _cut(tail)
            if 2 <= len(dept) <= 14 and _SUFFIX_RE.search(dept):
                return body + dept, tail2
        return body, tail
    rest = _PARTY_SUFFIX.sub("", rest)
    if not rest:
        return (loc + "政府", "") if gov_title else (None, "")
    head, tail = _cut(rest)
    if not _SUFFIX_RE.search(head) or len(head) > 20:
        return None, ""
    return loc + head, tail


def _ctx_locality(level, ctx):
    if level in ("省", "自治区"):
        p = ctx.prov
        if p and (p.endswith("自治区") == (level == "自治区")) and not p.endswith("市"):
            return p
        return None
    if level == "市":
        if ctx.city and ctx.city.endswith("市"):
            return ctx.city
        if ctx.prov and ctx.prov.endswith("市"):
            return ctx.prov
        if ctx.county and ctx.county.endswith("市"):
            return ctx.county
        return None
    if level in ("地", "州", "盟"):
        suffix = {"地": "地区", "州": "州", "盟": "盟"}[level]
        return ctx.city if ctx.city and ctx.city.endswith(suffix) else None
    if level in ("县", "区", "旗"):
        c = ctx.county
        if c and c.endswith(level):
            return _loc_name(ctx.prov, ctx.city, c)
        return None
    return None


def resolve_org(rem, title, ctx):
    """Map the organisation part of one post clause to (key, leftover-for-position)."""
    gov_title = bool(_GOV_HEAD_TITLE.search(title)) or title.endswith("主席") and rem.endswith("自治区")
    rem = _SESSION.sub("", rem)
    for pat, rep in _ALIASES:
        rem = pat.sub(rep, rem, count=1)
    # bare 军委: the Central Military Commission only after 1949 (红七军军委, 省委军委 before)
    if rem.startswith("军委") and not rem.startswith("军委员") and (ctx.year or 0) >= 1949:
        rem = "中央" + rem
    rem = rem.strip("·•的 ")

    # 国务委员 / 中央委员 / 中央候补委员
    if title.endswith("国务委员") and not rem:
        return "国务院", ""
    if rem in ("中央", "中央候补", "中央委员会") and title.endswith("委员"):
        return "中央委员会", ""
    if rem == "中央顾问委员会":
        return rem, ""

    if rem == "书记处":
        # 中央政治局委员、书记处书记 -> 中央书记处; 全国妇联…、书记处第一书记 -> 全国妇联
        if not ctx.last:
            return None, ""
        return ("中央书记处", "") if ctx.last.startswith("中央") else (ctx.last, rem)
    if rem in _BARE_UNITS:
        return (ctx.last, rem) if ctx.last else (None, "")
    pla = re.match(r"^(?:中国人民解放军|人民解放军|解放军)(?=.{2})", rem)
    if pla:
        rem = rem[pla.end():]
    if pla or _is_military(rem):
        if rem.startswith("省军区") and ctx.prov and ctx.prov.endswith("省"):
            return ctx.prov + "军区", rem[3:]
        return _military_key(rem)

    youth = ""
    if rem.startswith("共青团") and not rem.startswith("共青团中央"):
        youth, rem = "共青团", rem[3:]

    # Elided locality head: 省委 / 市政府 / 县长 …
    m = _ELIDED_LOC.match(rem) if not _PROV_RE.match(rem) else None
    if m and not _parse_locality_is_real(rem):
        loc = _ctx_locality(m.group(1), ctx)
        if loc:
            key, tail = _locality_body(youth + loc, rem[m.end():], ctx, gov_title)
            if key:
                return key, tail
        return None, ""

    parsed = _parse_locality(rem, ctx)
    if parsed:
        prov, city, county, rest = parsed
        ctx_before = (ctx.prov, ctx.city, ctx.county)
        if prov:
            ctx.prov, ctx.city, ctx.county = prov, city, county
        elif city:
            ctx.city, ctx.county = city, county
        else:
            ctx.county = county
        loc = _loc_name(prov, city or (None if prov else ctx.city), county)
        key, tail = _locality_body(youth + loc, rest, ctx, gov_title)
        if key:
            return key, tail
        ctx.prov, ctx.city, ctx.county = ctx_before
        if not rest:
            return None, ""

    # Bare gov head: 市长 / 副省长 with no organisation text
    stripped = _PARTY_SUFFIX.sub("", rem)
    if not stripped and gov_title:
        level = _GOV_HEAD_TITLE.search(title).group(0)[0]
        level = {"专": "地"}.get(level, level)
        loc = _ctx_locality(level, ctx)
        return (loc + "政府", "") if loc else (None, "")
    if not stripped:
        return (ctx.last, rem) if ctx.last else (None, "")

    # Elided institution head: 校党委 / 部党组 / 系主任
    if _ELIDED_INST.match(rem):
        return (ctx.inst or ctx.last, rem) if (ctx.inst or ctx.last) else (None, "")

    if stripped in _GENERIC_DEPTS:
        parent = ctx.party if (stripped in _PARTY_DEPTS and ctx.party) else ctx.last
        if not parent:
            return None, ""
        if re.search(r"(?:委|政府)$", parent):
            return parent + stripped, ""
        return parent, rem

    for top in ("国务院", "全国人大常委会", "全国人大", "全国政协", "中央军委"):
        if stripped.startswith(top):
            sub = stripped[len(top):]
            if not sub or re.match(r"^(?:机关|常委会|常务委员会)", sub):
                return top, sub
            head, tail = _cut(sub)
            if _SUFFIX_RE.search(head) and len(head) <= 16:
                return top + head, tail
            return top, sub

    head, tail = _cut(stripped)
    if not _NATIONAL_HEAD.match(head) and (
            _SUBUNIT.search(head) or (len(head) <= 4 and head[-1] in "司局厅处室科组队")):
        parent = ctx.inst or ctx.last
        return (parent, rem) if parent else (None, "")
    if not _SUFFIX_RE.search(head):
        if 3 <= len(head) <= 12 and re.search(r"(?:政治局|书记处|社|团|台|队|会|组|室|处|司|科|店|铺|坊|场|园|库|港|关|庭|网|刊)$", head):
            return head, ""
        return (ctx.last, rem) if (ctx.last and len(stripped) <= 6) else (None, "")
    if head in _STOP_KEYS or len(head) < 2 or len(head) > 24:
        return None, ""
    # an enterprise or institute under a ministry is its own workplace:
    # 兵器工业部第五五九厂 and 兵器工业部216厂 are not one body
    if _PARENT_BODY.search(head) and tail:
        m = _CHILD_UNIT.search(tail, 1)
        if m and m.end() <= 16:
            return head + tail[:m.end()], tail[m.end():]
    if len(head) <= 2 and ctx.last:
        return ctx.last, rem
    return head, tail


# A clause that names only a sub-unit (学生工作部, 人事处, 办公室) belongs to the body before it.
_SUBUNIT = re.compile(
    r"(?:(?:工作|管理|事务|研究|保卫|联络|干部|学生|教务|人事|后勤|总务|财务|科研|武装|军体|群工|青工|学工|基建|生产|技术|计划)部"
    r"|处|室|科|系|组|办公室|办|车间|分厂|分公司|分院|分校|支部|总支)$"
)
_NATIONAL_HEAD = re.compile(r"^(?:中央|国家|国务院|全国|中国|中华|最高)")

_PARENT_BODY = re.compile(r"(?:部|委员会|总局|总公司|科学院|集团公司|集团)$")
_CHILD_UNIT = re.compile(r"厂|公司|研究院|设计院|研究所|大学|学院|矿(?!业)|油田|基地|铁路局|管理局|工程局|分局|医院|出版社")

_MIL_RE = re.compile(r"军区|战区|舰队|集团军|野战军|方面军|兵团|军团|纵队|解放军|红军|八路军|新四军|武警|部队|空军|海军|陆军|炮兵|志愿军")


_BARE_UNITS = {"政治部", "后勤部", "司令部", "装备部", "参谋部", "联勤部", "干部部", "组织部门"}
_MINISTRIES = set("外交 财政 水利 公安 商务 铁道 农业 监察 教育 文化 国防 司法 民政 劳动 交通 航天 建设 卫生 冶金 "
                  "邮电 石油 商业 林业 化工 能源 科技 水电 机械 建工 农林 农垦 高教 航空 经贸 人事 地质 煤炭 电力 "
                  "纺织 轻工 内务 粮食 外贸 一机 二机 三机 四机 五机 六机 七机 八机".split())
_SHORT_OK = {"国务院", "陆军", "空军", "海军", "武警", "火箭军", "八路军", "新四军", "红军", "志愿军", "政务院",
             "证监会", "银监会", "保监会", "审计署", "国资委", "发改委", "新华社"}
_JUNK_KEY = re.compile(r"[的:：他她该某]|决定|免去|负责|主持|代理|参加|担任|期间|时期|以后|之后|先后|同志")


def _key_ok(key):
    if not key or key in _STOP_KEYS or _JUNK_KEY.search(key):
        return False
    if len(key) <= 3 and key not in _SHORT_OK:
        return len(key) == 3 and key[2] == "部" and key[:2] in _MINISTRIES
    return True
_SERVICE = re.compile(
    r"^(陆军|空军|海军|第二炮兵|二炮|火箭军|战略支援部队|武警部队|武警|八路军|新四军|中国工农红军|工农红军|红军"
    r"|中国人民志愿军|志愿军|东北民主联军|东北野战军|华东野战军|中原野战军|西北野战军|华北野战军"
    r"|第[一二三四]野战军|[一二三四]野)"
)
_MIL_SUFFIX = re.compile(
    r"学校|学院|大学|军区|战区|舰队|集团军|野战军|方面军|兵团|军团|纵队|总部|总队|支队|基地|研究院|"
    r"总政治部|总参谋部|总后勤部|总装备部|师(?!范)|旅|团(?!长)|军(?![区学校官事分政委需械医团种])"
)


def _is_military(rem):
    return bool(_MIL_RE.search(rem))


def _military_key(rem):
    rem = _PARTY_SUFFIX.sub("", rem)
    m = _SERVICE.match(rem)
    svc = ""
    if m:
        svc = "第二炮兵" if m.group(1) == "二炮" else m.group(1)
        rem = rem[m.end():]
        if not rem:
            return svc, ""
    ms = _MIL_SUFFIX.search(rem, 1)
    if not ms:
        return (svc, rem) if svc else (None, "")
    head = rem[:ms.end()]
    if len(head) > 18:
        return (svc, rem) if svc else (None, "")
    return svc + head, rem[ms.end():]


def _parse_locality_is_real(rem):
    """True when `rem` opens with a real place name rather than an elided 省/市/县."""
    return False


_WORK_TAIL = re.compile(r"(?<!主持)(?<!负责)(?<!分管)(?<!协助)(?<!领导)(?<!参加)(工作|任教|执教|任职|供职)$")


def _split_title(seg):
    m = _TITLE_RE.search(seg)
    if not m:
        m = _REP_TITLE_RE.search(seg)
    if not m:
        m = _WORK_TAIL.search(seg)
        if m and _SUFFIX_RE.search(seg[:m.start()]):
            return seg[:m.start()], m.group(1)
        return None
    return seg[:m.start()], seg[m.start():]


def _detect_province(text):
    for cn in PROVINCES:
        if cn in text:
            return cn
    return None


def _admin_level(key, prov, city, county):
    if county:
        return "district"
    if city:
        return "municipal"
    if prov:
        return "provincial"
    if any(key.startswith(o) or o in key[:8] for o in CENTRAL_ORGS):
        return "central"
    if re.search(r"(?<!分)部$", key) and len(key) <= 9:
        return "central"
    return "unknown"


def _locality_of_key(key):
    """Re-derive (prov, city, county) from a canonical key, for province/admin_level."""
    k = key[3:] if key.startswith("共青团") else key
    p = _parse_locality(k, _Ctx())
    return p[:3] if p else (None, None, None)


def parse_posts(text, year=None):
    """Split the text after a date prefix into [(organization, position, prov_short, level)].

    One entry per distinct organisation key, in order of first appearance.
    """
    text = text.translate(_FW)
    prev = None
    while prev != text:
        prev = text
        text = _PAREN.sub("", text)
    text = re.split(r"[。]", text)[0] if "。" in text[:-1] and len(text) > 60 else text
    ctx = _Ctx(year)
    out = {}
    provs = {}
    order = []
    pending = []          # organisation clauses waiting for a trailing shared title
    for clause in re.split(r"[,;，；]", text):
        pending = []
        for seg in re.split(r"[、]|(?<=[长记任员席委])兼(?!职)|(?<=[长记任员席委])和(?=.{0,8}[委部局厅])|并兼|同时兼任|兼任", clause):
            seg = _TAIL_JUNK.sub("", seg.strip())
            prevseg = None
            while prevseg != seg:
                prevseg = seg
                seg = _LEAD_JUNK.sub("", seg)
            if len(seg) < 2 or len(seg) > 60:
                continue
            if EDU_RE.search(seg) or AWARD_RE.search(seg) or _REMOVAL.search(seg):
                continue
            seg = _SUBJECT_IN.sub("", seg)
            st = _split_title(seg)
            if not st:
                if _SUFFIX_RE.search(seg) and seg[-1] in "部委局院厅办处室会社校司组科队所系":
                    pending.append(seg)
                continue
            rem, title = st
            # an appointment verb inside the clause ("李四光先后任…"): keep what follows it
            mv = None
            for mv in _NARRATIVE_VERB.finditer(rem):
                pass
            if mv:
                rem = rem[mv.end():]
            for org_text in pending + [rem]:
                key, left = resolve_org(org_text, title, ctx)
                if not _key_ok(key):
                    if key and len(key) <= 3 and ctx.last:
                        key, left = ctx.last, org_text
                    else:
                        continue
                sfx = _PARTY_SUFFIX.search(org_text)
                if sfx and not left.endswith(sfx.group(0)) and not key.endswith(sfx.group(0)):
                    left += sfx.group(0)
                provs[key] = ctx.prov if _locality_of_key(key)[0] is None else None
                ctx.last = key
                if re.search(r"(?:大学|学院|学校|公司|集团|银行|厂|院|所|部|局|委员会|社)$", key) and not re.search(r"(?:委|政府)$", key):
                    ctx.inst = key
                pos = (left + title) if org_text is rem else title
                if key not in out:
                    out[key] = []
                    order.append(key)
                if pos and pos not in out[key]:
                    out[key].append(pos)
            pending = []
    posts = []
    for key in order:
        prov, city, county = _locality_of_key(key)
        if not prov and (city or county):
            prov = provs.get(key)
        prov_short = None
        if prov:
            prov_short = next((p for p in PROVINCES if prov.startswith(p)), None)
        elif not (city or county):
            prov_short = _detect_province(key)
        posts.append((key, "、".join(out[key]), prov_short, _admin_level(key, prov, city, county)))
    return posts


_SENT_SPLIT = re.compile(r"(?<=[。；;])\s*(?=\d{4}\s*年)")


def parse_career_text(career_text):
    """Parse stored Baike career text into career-record dicts (one per held post)."""
    if not career_text:
        return []
    groups = []      # one per dated line: dict(dates..., posts=[...])
    for raw in career_text.split("\n"):
        raw = raw.strip()
        if not raw or raw[0] in "（(":
            continue
        norm = raw.translate(_FW).replace("　", " ")
        for piece in _SENT_SPLIT.split(norm):
            d = split_date_prefix(piece)
            if not d:
                continue
            sy, sm, ey, em, open_ended, is_range, rest = d
            rest = rest.strip()
            if not rest:
                continue
            if not is_range:
                # narrative single-date entry: needs an appointment verb, or be a terse CV line
                mv = _NARRATIVE_VERB.search(rest)
                if mv and _REMOVAL.search(rest[:mv.end() + 2]):
                    continue
                if mv and mv.start() <= 12:
                    rest = re.split(r"[。]", rest[mv.end():])[0]
                elif len(rest) > 45 or "。" in rest[:-1] or not _split_title(_TAIL_JUNK.sub("", rest)):
                    continue
            posts = parse_posts(rest, sy)
            if not posts:
                continue
            prov_fallback = _detect_province(rest)
            groups.append(dict(sy=sy, sm=sm, ey=ey, em=em, open=open_ended, range=is_range,
                               posts=posts, raw=raw, prov=prov_fallback))

    # single-date entries: end at the next dated entry, capped at 5 years
    for i, g in enumerate(groups):
        if g["ey"] is None and not g["open"]:
            for nxt in groups[i + 1:]:
                if (nxt["sy"], nxt["sm"] or 0) > (g["sy"], g["sm"] or 0):
                    if nxt["sy"] - g["sy"] <= 5:
                        g["ey"], g["em"] = nxt["sy"], nxt["sm"]
                    break

    records = []
    seen = set()
    for g in groups:
        for key, pos, prov_short, level in g["posts"]:
            sig = (key, g["sy"], g["sm"], g["ey"], g["em"])
            if sig in seen:
                continue
            seen.add(sig)
            records.append({
                "position": pos,
                "organization": key,
                "province": prov_short,
                "admin_level": level,
                "start_year": g["sy"],
                "start_month": g["sm"],
                "end_year": g["ey"],
                "end_month": g["em"],
                "raw_text": g["raw"],
            })
    return records
