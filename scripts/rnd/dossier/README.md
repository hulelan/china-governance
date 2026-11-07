# Parallel-text dossier builder

Builds a three-column Chinese / English / references reader for one document and
the instruments it cites. Built 2026-11-06 for 工信厅信管〔2026〕42号.

## Pipeline

```bash
# 1. ON THE DROPLET — pull the bodies, split them into articles
python3 scripts/rnd/dossier/dump_texts.py          # -> /tmp/dossier_cn.json
python3 scripts/rnd/dossier/measure_auth.py        # -> /tmp/dossier_facts.json
scp root@104.236.88.45:/tmp/dossier_{cn,facts}.json <workdir>/

# 2. LOCALLY — merge with the authored English and annotations
python3 scripts/rnd/dossier/build_dossier.py       # -> artifact/data.js
```

`dump_texts.py` holds the id map; add a document there to add it to the reader.
English lives in `data/dossier/en/<key>.json`, keyed by **article number**
(`第十二条`) and never by list index, so a later translation pass cannot shift the
alignment of the articles already done. A block with no English renders Chinese
alone and counts against the coverage badge the page prints, which is why a
partial translation is safe to ship.

## Three things building it found

**1. Splitting on 第N条 over-counts, and the fix is the document's own numbering.**
A naive split gave 网络安全法 109 blocks against its real 81 articles and 电信条例 98
against 80, because statutes cross-reference their own articles mid-sentence
(`违反第二十一条规定`). Whitespace is not the discriminator — these bodies are
flattened extractions. The article **sequence** is: a real header is the first
第一条 and every later one is exactly prev+1, which a backward cross-reference can
never satisfy. After the fix every count matches the published total
(数据安全法 55, 个人信息保护法 74, 反电信网络诈骗法 50). This is CLAUDE.md's
"when a heuristic and an identifier disagree, the identifier wins", applied to
text structure.

**2. A relevance rule that selects 95% of a statute is not selecting.** The first
plan was to translate "the articles the notice relies on", chosen by matching the
notice's own operative terms. It selected 64 of 81 articles of 网络安全法 and 71 of
74 of 个人信息保护法 — a measure describing the measure, not the corpus. It was also
answering a question the source does not pose: the notice cites its authorities
wholesale (`依据…等相关法律法规规章`) and names no article, so a "relied-on set" would
have invented precision. Chapter 1 (总则) is used instead, because it is a unit the
**document** defines.

**3. Four extraction defects were sitting in these bodies, invisible until the text
was read as text.** The 反电信网络诈骗法 body literally begins with a leaked HTML
attribute fragment (`class="article_content …" ms-class="font{{detailFont}}">`,
90 chars) because extraction started mid-tag. The 数据安全法 copy opens with a Xinhua
wire dateline, since that is the carrier it arrived on. Every gov.cn document
carries the site footer (主办单位/版权所有/京ICP备) inside its **last article** — a gap
in `trim_body_tails.py`'s markers. And chapter headings sit inline, so 第三章 was
glued onto the end of 第十四条. All four are stripped in `dump_texts.py`; the first
three are corpus-wide and are worth fixing at the extractor.

Also noted and **not** repaired: 电信设备进网管理办法 Article 35 is missing its item
（一） in the held text. A fabricated item is worse than a visible gap, so the page
reproduces what the corpus holds.

## What the reader demonstrates

Two of the six cited authorities are hit by the citation defects written up in
`docs/working/citation-target-has-no-text.md`. 697 edges for 网络安全法 resolve to a
2,256-character wire summary rather than the 11,047-character statute, and all 63
for 反电信网络诈骗法 resolve to a record with **zero** characters while an
8,780-character copy is held. The page states both in its own reference panel.
