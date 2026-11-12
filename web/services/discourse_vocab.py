"""Global-discourse vocabulary: the ONE source of truth for concept regexes and the
speaker-type classifier.

Used by
  * scripts/build_discourse_weekly.py   (the nightly concept x speaker x week table)
  * web/services/discourse.py           (/discourse; labels only come from the DB)
  * scripts/rnd/analysis/global_discourse/{speakers,concept_scan,counter_terms}.py
    (the cross-section scans behind docs/research/global-discourse-map.md, which
    now import from here instead of carrying their own copies)

Pure Python, no app dependencies, so a script can import it without FastAPI.

Each concept: key (the Chinese label the memo uses) -> (regex, label_en, family, anchor).
``anchor`` is a LITERAL substring every match of the regex must contain. The weekly
builder tests ``anchor in text`` (a memchr-speed scan) before running the regex,
which is what keeps a full-corpus rebuild cheap; ``tests/test_discourse_weekly.py``
asserts the anchor really is implied by the regex for every concept, so the
prefilter cannot silently drop matches.
"""
import re

# --- speaker type -----------------------------------------------------------
PARTY = {"qstheory", "dangyuan"}
STATE = {"xinhua", "people", "ce", "jjckb", "stdaily", "cnr", "cctv", "chinanews", "people_rmrb",
         "peopleapp", "newscn", "xinhua_lw", "xinhua_en"}
COMM = {"guancha", "ifeng"}
BIZ = {"yicai", "jiemian", "36kr", "latepost", "qbitai", "eeo", "huxiu", "tmtpost", "elsewhere",
       "21jingji", "cnfin", "eastmoney", "guandian", "qqnews", "thepaper"}
RES = {"cass", "amr", "tsinghua_aiig", "cast", "isc"}
SUBNATIONAL_LEVELS = ("provincial", "municipal", "district", "department")

SPEAKERS = ["central", "party_theory", "diplomacy", "state_media", "commentary",
            "business_press", "research", "subnational"]
SPEAKER_LABELS = {
    "central": "Central (non-media)", "party_theory": "Party theory", "diplomacy": "Diplomacy (MFA)",
    "state_media": "State media", "commentary": "Commentary", "business_press": "Business press",
    "research": "Research", "subnational": "Sub-national",
}


def speaker(site, lvl):
    """Speaker type of a document from its site_key and doc_identity.admin_level_doc.
    None = not a speaker we count (foreign media, unlevelled rows)."""
    if site in PARTY: return "party_theory"
    if site == "mfa": return "diplomacy"
    if site in STATE: return "state_media"
    if site in COMM: return "commentary"
    if site in BIZ: return "business_press"
    if site in RES: return "research"
    if lvl == "central": return "central"
    if lvl in SUBNATIONAL_LEVELS: return "subnational"
    return None


# --- concepts (global-discourse-map.md, 38 concepts) ------------------------
# key: (regex, label_en, family, literal anchor)
CONCEPTS = {
 "命运共同体": (r"人类命运共同体", "Community with a shared future for mankind", "doctrine", "命运共同体"),
 "全人类共同价值": (r"全人类共同价值", "Common values of all humanity", "doctrine", "全人类共同价值"),
 "普世价值": (r"普世价值", "Universal values (foil)", "foil", "普世价值"),
 "GDI发展倡议": (r"全球发展倡议", "Global Development Initiative", "initiatives", "全球发展倡议"),
 "GSI安全倡议": (r"全球安全倡议", "Global Security Initiative", "initiatives", "全球安全倡议"),
 "GCI文明倡议": (r"全球文明倡议", "Global Civilization Initiative", "initiatives", "全球文明倡议"),
 "GGI治理倡议": (r"全球治理倡议", "Global Governance Initiative", "initiatives", "全球治理倡议"),
 "四大全球倡议": (r"[四三]大全球倡议", "The three/four global initiatives", "initiatives", "大全球倡议"),
 "胸怀天下": (r"胸怀天下", "Keeping the world in mind", "doctrine", "胸怀天下"),
 "人类文明新形态": (r"人类文明新形态", "New form of human civilization", "civilization", "人类文明新形态"),
 "文明互鉴": (r"文明(?:交流)?互鉴", "Mutual learning among civilizations", "civilization", "互鉴"),
 "文明冲突": (r"文明冲突", "Clash of civilizations (foil)", "foil", "文明冲突"),
 "文明优越": (r"文明优越", "Civilizational superiority (foil)", "foil", "文明优越"),
 "文明多样性": (r"文明多样性", "Diversity of civilizations", "civilization", "文明多样性"),
 "中国式现代化": (r"中国式现代化", "Chinese-style modernization", "doctrine", "中国式现代化"),
 # Widened 2026-11-12: the dominant phrasing is the REBUTTAL of a quoted myth,
 # 打破了"现代化=西方化/等于西方化"的迷思, with ASCII or full-width "=", quote marks and
 # 等同于/就是/不必. The memo's first regex matched 2 of the 23 bodies that carry this
 # claim within 8 characters.
 "现代化≠西方化": (r"现代化[”\"’']?[，,]?[^。；\n]{0,4}?(?:不等于|等同于|等于|不是|并非|不必|就是|[=＝≠])[“\"‘']?西方化",
               "Modernization is not Westernization", "civilization", "西方化"),
 "中国方案": (r"中国方案", "China's solution", "doctrine", "中国方案"),
 "百年变局": (r"百年(?:未有之)?大?变局", "Changes unseen in a century", "world_order", "变局"),
 "新型国际关系": (r"新型国际关系", "New type of international relations", "world_order", "新型国际关系"),
 "全球治理体系": (r"全球治理体系", "Global governance system", "world_order", "全球治理体系"),
 "真正的多边主义": (r"真正的多边主义", "True multilateralism", "world_order", "真正的多边主义"),
 "霸权主义": (r"霸权主义", "Hegemonism", "foil", "霸权主义"),
 "单边主义": (r"单边主义", "Unilateralism", "foil", "单边主义"),
 # (?<!地方): 地方保护主义 is DOMESTIC market segmentation (营商环境 documents); it was
 # the only 保护主义 use in 51 of 877 documents (5.8%) on 2026-11-12.
 "保护主义": (r"(?<!地方)保护主义", "Protectionism", "foil", "保护主义"),
 "西方中心": (r"西方中心", "Western-centrism (foil)", "foil", "西方中心"),
 "历史终结": (r"历史终结", "End of history (foil)", "foil", "历史终结"),
 "天下为公": (r"天下为公", "The world belongs to all", "civilization", "天下为公"),
 "天下体系": (r"天下(?:体系|主义)", "Tianxia system / Tianxia-ism", "civilization", "天下"),
 "全球南方": (r"全球南方", "Global South", "world_order", "全球南方"),
 "多极化": (r"多极化", "Multipolarity", "world_order", "多极化"),
 "经济全球化": (r"经济全球化", "Economic globalization", "world_order", "经济全球化"),
 "脱钩断链": (r"脱钩断链|小院高墙", "Decoupling / small yard, high fence", "foil", None),
 "修昔底德": (r"修昔底德", "Thucydides trap", "foil", "修昔底德"),
 "一带一路": (r"一带一路", "Belt and Road", "world_order", "一带一路"),
 "规则国际秩序": (r"基于规则的国际秩序", "Rules-based international order (rival term)", "foil", "基于规则的国际秩序"),
 "自主知识体系": (r"自主(?:的)?知识体系", "Autonomous knowledge system", "knowledge", "知识体系"),
 "国际话语权": (r"国际话语权|话语体系", "International discourse power / discourse system", "knowledge", "话语"),
 "讲好中国故事": (r"讲好中国故事", "Tell China's story well", "knowledge", "讲好中国故事"),
}

# Official counter-terms (counter_terms.py, second pass of the memo). 人类文明新形态
# is already a concept above, so it is not repeated here.
COUNTER_TERMS = {
 "以联合国为核心的国际体系": (r"以联合国为核心的国际体系", "UN-centred international system", "counter_term", "以联合国为核心的国际体系"),
 "以国际法为基础的国际秩序": (r"以国际法为基础的国际秩序", "International-law-based order", "counter_term", "以国际法为基础的国际秩序"),
 "平等有序的(世界)多极化": (r"平等有序的(?:世界)?多极化", "Equal and orderly multipolarity", "counter_term", "平等有序的"),
 "普惠包容的经济全球化": (r"普惠包容的经济全球化", "Inclusive economic globalization", "counter_term", "普惠包容的经济全球化"),
 "中心—外围": (r"中心[—-]外围", "Core-periphery", "counter_term", "外围"),
 "西方伪史": (r"西方伪史|伪史论", "'Fake Western history' theory", "counter_term", "伪史"),
 "中等强国": (r"中等强国", "Middle powers", "counter_term", "中等强国"),
 "天下文明": (r"天下文明", "Tianxia civilization", "counter_term", "天下文明"),
 "文明型国家": (r"文明型国家", "Civilizational state", "counter_term", "文明型国家"),
 "习近平外交思想": (r"习近平外交思想", "Xi Jinping Thought on Diplomacy", "counter_term", "习近平外交思想"),
 "新时代中国特色大国外交": (r"中国特色大国外交", "Major-country diplomacy with Chinese characteristics", "counter_term", "中国特色大国外交"),
}

FAMILIES = ["doctrine", "initiatives", "world_order", "civilization", "knowledge", "foil", "counter_term"]

# Back-compat views used by the memo scripts: label -> regex string.
C = {k: v[0] for k, v in CONCEPTS.items()}
PH = {k: v[0] for k, v in COUNTER_TERMS.items()}
PH["人类文明新形态"] = C["人类文明新形态"]


# --- page chrome --------------------------------------------------------------
# 观察者网 (guancha): 934 of 15,267 stored bodies are the PAGE CHROME, not the article
# (measured 2026-11-12): title, a timestamp line, then a "相关推荐" (or "观察者头条")
# list of other headlines with timestamps and "评论 N" counts. 933 of the 934 have
# under 200 characters before that header, i.e. the article body was never
# extracted, and ~20 of 28 伪史论 hits were only these sidebar links. Cut the body at
# the first line that IS one of these headers. The headers are matched as whole
# lines, so prose that mentions 相关推荐 is untouched; "相关新闻" is deliberately NOT a
# header (on the one guancha page and one ifeng page where it appears, real article
# prose follows it). ifeng carries none of these blocks (0 of 10,471).
CHROME_SITES = {"guancha"}
_CHROME_HDR = re.compile(r"\n[ \t\u00a0\u3000]*(?:相关推荐|观察者头条|风闻 · 24小时最热|最新视频)[ \t\u00a0\u3000]*(?:\n|$)")
_DATE_LINE = re.compile(r"^[ \t\u00a0]*(?:\d{4}-\d{2}-\d{2}[ \d:]*|\d{2}/\d{2}/\d{4}[ \d:]*|-->)[ \t\u00a0]*$")
CHROME_MIN_TEXT = 30   # chars left after title/date/chrome removal; below = no article text


def strip_chrome(site, body):
    """Body with the sidebar/related-headline chrome removed (guancha only); every
    other site's body is returned unchanged."""
    if site not in CHROME_SITES or not body:
        return body
    m = _CHROME_HDR.search(body)
    return body[:m.start()] if m else body


def article_chars(title, body):
    """Characters of article text: body lines minus the title line and bare
    date/timestamp lines. Used to drop chrome-only stubs from the denominator."""
    t = (title or "").strip()
    n = 0
    for line in body.split("\n"):
        x = line.strip()
        if not x or x == t or _DATE_LINE.match(line):
            continue
        n += len(x)
    return n


def all_terms():
    """Every tracked term, concepts then counter-terms: key -> (regex, label_en, family, anchor)."""
    out = dict(CONCEPTS)
    out.update(COUNTER_TERMS)
    return out


def compiled():
    """[(key, compiled regex, anchors tuple)] in a stable order. An anchor of None
    means 'derive from the alternation' (each branch's literal)."""
    out = []
    for k, (pat, _en, _fam, anchor) in all_terms().items():
        if anchor is None:
            anchors = tuple(pat.split("|"))       # pure-literal alternation
        else:
            anchors = (anchor,)
        out.append((k, re.compile(pat), anchors))
    return out


def find_terms(text, terms=None):
    """Keys of every term whose regex matches ``text`` (anchor-prefiltered)."""
    terms = terms if terms is not None else compiled()
    return [k for k, rx, anchors in terms
            if any(a in text for a in anchors) and rx.search(text)]
