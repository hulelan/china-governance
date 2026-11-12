"""Read-only. Global-discourse concept map over a dense cross-section window.

Per document: speaker type, which concepts it uses. Out: rates per speaker,
pairwise lift, and contention sentences (concept + rebuttal marker)."""
import sqlite3, re, json, collections, hashlib, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WIN = ("2025-07-01", "2026-11-13")
# Concept regexes: web/services/discourse_vocab.py (one source of truth, via speakers.py).
# NOTE 2026-11-12: 保护主义 now excludes 地方保护主义 and 现代化≠西方化 was widened;
# neither appears in the memo's tables.
from speakers import C
CR = {k: re.compile(v) for k, v in C.items()}
MARK = re.compile(r"所谓|鼓吹|谬论|驳斥|驳|炒作|抹黑|污名|并非|绝不是|不是.{0,30}而是|有人认为|一些人|西方学者|有观点|争论|争议|质疑|误读|曲解|错误思潮|陷阱|零和")
SENT = re.compile(r"[^。！？\n]{6,240}[。！？]?")

from speakers import speaker, strip_chrome

c = sqlite3.connect("file:documents.db?mode=ro", uri=True)
q = ("SELECT d.id, d.site_key, substr(d.date_published,1,10), d.title, d.body_text_cn, "
     "COALESCE(i.admin_level_doc,''), COALESCE(i.genre,''), COALESCE(i.province,'') "
     "FROM documents d LEFT JOIN doc_identity i ON i.doc_id=d.id "
     "WHERE d.body_text_cn!='' AND d.date_published>=? AND d.date_published<?")
N = collections.Counter()                  # docs per speaker
H = collections.defaultdict(collections.Counter)   # speaker -> concept -> docs
PAIR = collections.Counter(); ONE = collections.Counter(); NDOC = 0
SAMP = collections.defaultdict(list)       # concept|speaker -> sentences
TOP = collections.defaultdict(list)        # concept -> (n concepts, id, site, date, title)
AUTH = collections.defaultdict(collections.Counter)  # guancha author -> concept
PROV = collections.defaultdict(collections.Counter)  # province -> concept (subnational)
PROVN = collections.Counter()
GEN = collections.defaultdict(collections.Counter)   # subnational genre -> concept
seen_title = set()
for did, site, dt, title, body, lvl, genre, prov in c.execute(q, WIN):
    sp = speaker(site, lvl)
    if not sp: continue
    body = strip_chrome(site, body)       # guancha 相关推荐/观察者头条 sidebar (2026-11-12)
    key = (sp, re.sub(r"\W", "", title or "")[:40])
    if key in seen_title: continue          # one copy per title per speaker: mirrors are not voices
    seen_title.add(key)
    txt = (title or "") + "\n" + body
    hit = [k for k, r in CR.items() if r.search(txt)]
    N[sp] += 1
    if sp == "subnational" and prov: PROVN[prov] += 1
    if not hit: continue
    NDOC += 1
    for k in hit:
        H[sp][k] += 1; ONE[k] += 1
        if sp == "subnational":
            if prov: PROV[prov][k] += 1
            GEN[genre][k] += 1
    for a in range(len(hit)):
        for b in range(a + 1, len(hit)):
            PAIR[(hit[a], hit[b])] += 1
    if sp == "commentary" and site == "guancha":
        m = re.search(r"-([^-\s]{2,8})$", (title or "").strip())
        if m:
            for k in hit: AUTH[m.group(1)][k] += 1
    for k in hit:
        TOP[k].append((len(hit), did, site, dt, (title or "")[:70], sp))
    for s in SENT.findall(body):
        if not MARK.search(s): continue
        for k in hit:
            if CR[k].search(s):
                bucket = SAMP[k + "|" + sp]
                h = int(hashlib.md5(f"{did}{s[:20]}".encode()).hexdigest()[:8], 16)
                bucket.append((h, did, site, dt, s.strip()))
out = {
 "window": WIN, "n_speaker": dict(N), "n_docs_with_concept": NDOC,
 "hits": {sp: dict(v) for sp, v in H.items()},
 "one": dict(ONE),
 "pair": [[a, b, n] for (a, b), n in PAIR.items() if n >= 5],
 "samples": {k: [x[1:] for x in sorted(v)[:8]] for k, v in SAMP.items()},
 "samples_n": {k: len(v) for k, v in SAMP.items()},
 "top": {k: [x[1:] for x in sorted(v, reverse=True)[:12]] for k, v in TOP.items()},
 "authors": {a: dict(v) for a, v in AUTH.items() if sum(v.values()) >= 3},
 "prov": {p: dict(v) for p, v in PROV.items()}, "provn": dict(PROVN),
 "subgenre": {g: dict(v) for g, v in GEN.items()},
}
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/gd.json", "w"), ensure_ascii=False)
print("speakers", dict(N), "docs_with_concept", NDOC, file=sys.stderr)
