"""Read-only. Key texts, then official counter-terms counted by speaker type."""
import sqlite3, re, json, collections, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
c = sqlite3.connect("file:documents.db?mode=ro", uri=True)
for did in [900175926, 900200671, 900160234, 900138544, 900154072, 900036301, 900136354, 900033246, 900124795, 12709232]:
    r = c.execute("SELECT site_key, substr(date_published,1,10), title, length(body_text_cn), body_text_cn FROM documents WHERE id=?", (did,)).fetchone()
    print(f"\n=== {did} {r[0]} {r[1]} {r[3]}ch | {r[2]}\n{r[4][:900]}")
PH = {"以联合国为核心的国际体系": r"以联合国为核心的国际体系", "以国际法为基础的国际秩序": r"以国际法为基础的国际秩序",
      "平等有序的(世界)多极化": r"平等有序的(?:世界)?多极化", "普惠包容的经济全球化": r"普惠包容的经济全球化",
      "中心—外围": r"中心[—-]外围", "西方伪史": r"西方伪史|伪史论", "中等强国": r"中等强国",
      "人类文明新形态": r"人类文明新形态", "天下文明": r"天下文明", "文明型国家": r"文明型国家",
      "习近平外交思想": r"习近平外交思想", "新时代中国特色大国外交": r"中国特色大国外交"}
PC = {k: re.compile(v) for k, v in PH.items()}
from speakers import speaker
WIN = ("2025-07-01", "2026-11-13")
H = collections.defaultdict(collections.Counter); N = collections.Counter(); seen = set(); EX = collections.defaultdict(list)
for did, site, dt, title, body, lvl in c.execute("SELECT d.id,d.site_key,substr(d.date_published,1,10),d.title,d.body_text_cn,COALESCE(i.admin_level_doc,'') FROM documents d LEFT JOIN doc_identity i ON i.doc_id=d.id WHERE d.body_text_cn!='' AND d.date_published>=? AND d.date_published<?", WIN):
    sp = speaker(site, lvl)
    if not sp: continue
    k2 = (sp, re.sub(r"\W", "", title or "")[:40])
    if k2 in seen: continue
    seen.add(k2); N[sp] += 1
    t = (title or "") + "\n" + body
    for k, r in PC.items():
        if r.search(t):
            H[k][sp] += 1
            if len(EX[k]) < 4: EX[k].append((did, site, dt, (title or "")[:50]))
print("\n\nCOUNTER-TERMS (docs) by speaker", dict(N))
for k in PH: print(k, dict(H[k]), EX[k][:3])
