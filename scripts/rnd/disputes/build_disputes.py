"""Render scratchpad/disputes/*.json into one dispute reader page (hash-routed)."""
import json, html, sys, pathlib
S = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2])
ORDER = ["plenum", "civilization", "pseudohistory", "globalsouth"]
SHORT = {"plenum": "The world in the plenum texts", "civilization": "Whose civilization",
         "pseudohistory": "The pseudo-history boomerang", "globalsouth": "Global South, multipolarity, middle powers"}
e = lambda s: html.escape(str(s if s is not None else ""))

def quote(q):
    src = f'<a href="{e(q.get("url"))}" target="_blank" rel="noopener">{e(q.get("site"))}</a>' if q.get("url") else e(q.get("site"))
    did = f' · doc {e(q["id"])}' if q.get("id") else ""
    note = f'<p class="note">{e(q["note"])}</p>' if q.get("note") else ""
    return (f'<figure class="q"><blockquote lang="zh">{e(q.get("zh"))}</blockquote>'
            f'<p class="en">{e(q.get("en"))}</p>'
            f'<figcaption><span class="chip sp">{e(q.get("speaker"))}</span> {e(q.get("date"))} · {src}{did}'
            f'<span class="ttl" lang="zh">{e(q.get("title"))}</span></figcaption>{note}</figure>')

def camps(cs):
    return '<div class="camps">' + "".join(
        f'<section class="camp"><h3>{e(c["name"])}</h3><p class="who">{e(c.get("who"))}</p>'
        f'<p class="sum">{e(c.get("summary_en"))}</p>{"".join(quote(q) for q in c.get("quotes", []))}</section>'
        for c in cs) + "</div>"

def counts(rows):
    if not rows: return ""
    key = "by_speaker" if "by_speaker" in rows[0] else "by_doc"
    cols = []
    for r in rows:
        for k in r.get(key, {}):
            if k not in cols: cols.append(k)
    # tables of different shapes: split rows whose keys differ
    groups = {}
    for r in rows: groups.setdefault(tuple(r.get(key, {}).keys()), []).append(r)
    outh = ""
    for ks, rs in groups.items():
        outh += ('<div class="tw"><table><thead><tr><th>term</th>' + "".join(f"<th>{e(k)}</th>" for k in ks) + "</tr></thead><tbody>"
                 + "".join("<tr><td lang='zh'>" + e(r["term"]) + "</td>" + "".join(f'<td class="n">{e(r[key][k])}</td>' for k in ks) + "</tr>" for r in rs)
                 + "</tbody></table></div>")
    return "<h4>Counts</h4>" + outh

def reading(rs):
    if not rs: return ""
    return "<h4>What it shows</h4><ul class='reading'>" + "".join(
        f'<li><span class="chip lab {e(r.get("label"))}">{e(r.get("label"))}</span> {e(r["claim"])}</li>' for r in rs) + "</ul>"

def lineage(ls):
    if not ls: return ""
    return "<h4>First appearance in the corpus</h4><div class='tw'><table><thead><tr><th>term</th><th>first</th><th>doc</th><th>note</th></tr></thead><tbody>" + "".join(
        f"<tr><td lang='zh'>{e(l.get('term'))}</td><td class='n'>{e(l.get('first_date'))}</td><td class='n'>{e(l.get('first_id'))}</td><td>{e(l.get('note'))}</td></tr>" for l in ls) + "</tbody></table></div>"

def timeline(ts):
    if not ts: return ""
    months = sorted({t["month"] for t in ts}); sps = sorted({t["speaker"] for t in ts})
    m = {(t["month"], t["speaker"]): t["docs"] for t in ts}
    return ("<h4>By month and speaker</h4><div class='tw'><table><thead><tr><th>speaker</th>" + "".join(f"<th class='n'>{e(x)}</th>" for x in months)
            + "</tr></thead><tbody>" + "".join("<tr><td>" + e(s) + "</td>" + "".join(f"<td class='n'>{e(m.get((x,s),''))}</td>" for x in months) + "</tr>" for s in sps) + "</tbody></table></div>")

def body(d):
    h = f'<p class="question">{e(d.get("question"))}</p>'
    if d.get("camps"): h += camps(d["camps"])
    if d.get("engagements"): h += "<h4>Where the sides meet</h4><div class='eng'>" + "".join(quote(q) for q in d["engagements"]) + "</div>"
    for sd in d.get("subdisputes", []):
        h += f'<section class="sub" id="{e(sd.get("key"))}"><h3 class="subh">{e(sd["title"])}</h3><p class="question">{e(sd.get("question"))}</p>{camps(sd.get("camps", []))}{counts(sd.get("counts"))}{reading(sd.get("reading"))}</section>'
    h += timeline(d.get("timeline")) + counts(d.get("counts")) + lineage(d.get("lineage")) + reading(d.get("reading"))
    return h

ds = {k: json.load(open(S / f"{k}.json")) for k in ORDER if (S / f"{k}.json").exists()}
nav = "".join(f'<a href="#{k}" data-k="{k}">{e(SHORT[k])}</a>' for k in ds)
pages = "".join(f'<article class="page" id="{k}" data-k="{k}"><p class="eyebrow">Dispute</p><h2>{e(d["title"])}</h2>{body(d)}</article>' for k, d in ds.items())
tpl = open(pathlib.Path(__file__).with_name("disputes_template.html")).read()
out.write_text(tpl.replace("{{NAV}}", nav).replace("{{PAGES}}", pages))
print("wrote", out, "pages:", list(ds))
