"""Dump the dossier's documents as JSON, split into articles.

Why split here and not in the browser: the article boundary is a property of the
Chinese text (第N条 at the start of a line or after a full stop), and the English
translation has to be keyed to the SAME boundaries or the two columns drift.
Splitting once, server-side, makes the key the article number rather than an index.
"""
import json, re, sqlite3, sys

IDS = {
    "notice":   900210802,   # 工信厅信管〔2026〕42号
    "rwjg":     900210854,   # 电信设备进网管理办法
    "cybersec": 12694197,    # 网络安全法 (2025 amended, full text)
    "pipl":     12694426,    # 个人信息保护法
    "dsl":      12694435,    # 数据安全法
    "telecom":  12694530,    # 电信条例
    "antifraud": 900084102,  # 反电信网络诈骗法 (npc copy has no body)
    "twin2013": 12760612,    # 工信部电管〔2013〕120号
    "npcdecision": 12694519, # 2012 NPCSC Decision (npc copy 12748155 has no body)
}

# A literal &#xa0; survived HTML-entity escaping on the miit page; strip the
# entity text itself, not just U+00A0.
_ARTIFACT = re.compile(r'&#x[0-9a-fA-F]{2,4};|&nbsp;|​| ')
_ART = re.compile(r'(第[一二三四五六七八九十百零〇]+条)')

_DIG = {c: i for i, c in enumerate('零一二三四五六七八九')}


def cn_num(s):
    """Parse a Chinese ordinal up to 百. Returns None if unparseable."""
    s = s.strip()
    if not s:
        return None
    if s == '十':
        return 10
    total, tens = 0, 0
    if '百' in s:
        h, s = s.split('百', 1)
        total += (_DIG.get(h, 1) if h else 1) * 100
        if not s:
            return total
        if s.startswith('十') or len(s) > 1:
            pass
        elif s[0] in _DIG:
            return total + _DIG[s[0]]
    if '十' in s:
        t, s = s.split('十', 1)
        tens = (_DIG.get(t, 1) if t else 1) * 10
        total += tens
    for ch in s:
        if ch in _DIG:
            total += _DIG[ch]
        elif ch != '零':
            return None
    return total or None


# The gov.cn page footer survives body extraction: it is in neither
# trim_body_tails.py's REPORT_MARKERS nor the finmedia extractor, so it rides
# along inside the LAST article of any gov.cn document (第三十九条 here).
_FOOTER = re.compile(
    r'\s*(主办单位[：:]|运行维护单位[：:]|版权所有[：:]|中文域名[：:]|'
    r'网站标识码|京ICP备|京公网安备|ICP备\d).*$', re.S)

# A statute's appendix is not an article; 电信条例 carries 附 电信业务分类目录
# glued onto 第八十条 because the extraction flattened the page.
# A chapter heading sits INLINE in these flattened bodies, so it rides along
# inside whichever article precedes it. Pull it out as its own block: the
# chapter is how a statute is navigated, and gluing 第三章 onto 第十四条 loses it.
# A leaked HTML attribute fragment: the antifraud body literally BEGINS
# 'class="article_content ..." ms-class="font{{detailFont}}">'. The extractor
# started mid-tag, so the attribute text became the first characters of the
# document. Same family as the gov.cn footer: extraction debris, not content.
_TAGLEAK = re.compile(r'^[^\n<>]{0,40}?(?:class|ms-class|style|id)\s*=\s*"[^"]*"[^\n>]*>\s*')

# A wire-service lede: the 数据安全法 copy we hold came via Xinhua, so the body
# opens 新华社北京6月10日电 before the statute title. The statute is the document;
# the dateline is the carrier.
_WIRE = re.compile(r'^新华社[\u4e00-\u9fff]{0,6}\d{1,2}月\d{1,2}日电\s*')

# 第N节 sections sit one level under chapters and are inline too.
_SECT = re.compile(r'(第[一二三四五六七八九十]+节[\s\u3000]*[^\n]{0,24})')

_CHAP = re.compile(r'(第[一二三四五六七八九十]+章[\s\u3000]*[^\n]{0,24})')

_APPENDIX = re.compile(r'\n?\s*(附\s{0,4}(?:件)?\s*[\u4e00-\u9fff]{3,}目录.*)$', re.S)


def clean(s):
    s = _ARTIFACT.sub('', s or '')
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = _FOOTER.sub('', s)
    s = _TAGLEAK.sub('', s.lstrip())
    s = _WIRE.sub('', s.lstrip())
    return s.strip()


def split_articles(body):
    """Split on 第N条, but only where N continues the article SEQUENCE.

    A naive split on every 第N条 over-counts badly, because statutes
    cross-reference their own articles mid-sentence (违反第二十一条规定...).
    Measured: 网络安全法 split to 109 blocks against its real 79 articles,
    电信条例 to 98 against 81. Whitespace is not the discriminator either —
    these bodies are flattened extractions with no reliable paragraph breaks.

    The document's own numbering IS the discriminator: a real article header is
    the first 第一条, and every later one must be exactly prev+1. A
    cross-reference points backwards or jumps, so it never satisfies that. This
    is the "when a heuristic and an identifier disagree, the identifier wins"
    rule from CLAUDE.md, applied to text structure.
    """
    toks = _ART.split(body)
    blocks, expect, pre = [], 1, []
    for i, tok in enumerate(toks):
        if i % 2 == 0:
            (blocks[-1]["cn"] if blocks else pre).append(tok) if False else None
            if blocks:
                blocks[-1]["parts"].append(tok)
            else:
                pre.append(tok)
            continue
        n = cn_num(tok[1:-1])
        if n == expect:
            blocks.append({"no": tok, "n": n, "parts": [tok]})
            expect += 1
        elif blocks:
            blocks[-1]["parts"].append(tok)
        else:
            pre.append(tok)
    if blocks:
        tail = "".join(blocks[-1]["parts"])
        m = _APPENDIX.search(tail)
        if m:
            blocks[-1]["parts"] = [tail[:m.start()].strip()]
            blocks.append({"no": None, "n": None, "appendix": True,
                           "parts": [m.group(1).strip()]})
    out = []
    head = "".join(pre).strip()
    if head:
        out.append({"no": None, "cn": head})
    for b in blocks:
        text = "".join(b["parts"]).strip()
        if b.get("appendix"):
            out.append({"no": None, "cn": text, "appendix": True})
            continue
        # A trailing chapter heading belongs to the NEXT article, not this one.
        chunks = _CHAP.split(text)
        out.append({"no": b["no"], "n": b["n"], "cn": chunks[0].strip()})
        for i in range(1, len(chunks), 2):
            out.append({"no": None, "chapter": chunks[i].strip()})
            rest = chunks[i + 1].strip() if i + 1 < len(chunks) else ""
            if rest:
                out.append({"no": None, "cn": rest})
    # A stray text block that is NOTHING but a 第N节 heading is a section marker.
    for b in out:
        if b.get("no") or b.get("chapter") or b.get("toc") or b.get("appendix"):
            continue
        m = _SECT.fullmatch((b.get("cn") or "").strip())
        if m:
            b["section"] = re.sub(r'\s+', ' ', m.group(1).strip())
            b.pop("cn", None)
    return [b for b in out
            if b.get("cn") or b.get("chapter") or b.get("section")]


def para_split(body):
    """Paragraphs, for documents with no 第N条 structure (the 通知)."""
    chunks = [p.strip() for p in re.split(r'\n+', body) if p.strip()]
    if len(chunks) <= 2:
        chunks = [p.strip() + '。' for p in body.split('。') if p.strip()]
    return [{"no": None, "cn": c} for c in chunks]


conn = sqlite3.connect("file:documents.db?mode=ro", uri=True)
out = {}
for key, doc_id in IDS.items():
    row = conn.execute(
        "SELECT id, site_key, title, date_published, url, body_text_cn, relation "
        "FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        print(f"MISSING {key} {doc_id}", file=sys.stderr)
        continue
    body = clean(row[5])
    arts = split_articles(body)
    if sum(1 for a in arts if a["no"]) < 2:
        arts = para_split(body)
    head = arts[0] if arts and not arts[0].get("no") else None
    if head and re.search(r'\u76ee\s*\u5f55\s*\n', head["cn"]):
        m = re.search(r'\u76ee\s*\u5f55\s*\n', head["cn"])
        pre_txt, toc_txt = head["cn"][:m.start()].strip(), head["cn"][m.start():].strip()
        arts[0] = {"no": None, "cn": toc_txt, "toc": True}
        if pre_txt:
            arts.insert(0, {"no": None, "cn": pre_txt})
    out[key] = {
        "id": row[0], "site": row[1], "title": clean(row[2]),
        "date": (row[3] or "")[:10], "url": row[4],
        "chars": len(body), "articles": arts,
        "n_articles": sum(1 for a in arts if a["no"]),
    }
    print(f"{key:10s} {row[0]:>10} {len(body):>6}ch  "
          f"{out[key]['n_articles']:>3} articles  {len(arts):>3} blocks", file=sys.stderr)

json.dump(out, open("/tmp/dossier_cn.json", "w"), ensure_ascii=False, indent=1)
print("WROTE /tmp/dossier_cn.json", file=sys.stderr)
