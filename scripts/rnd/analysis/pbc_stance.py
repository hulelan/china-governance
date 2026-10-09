"""The PBC Monetary Policy Committee quarterly readouts as a stance series.

Finding: docs/research/pbc-stance-series.md.

70 readouts, 2009-04-12 to 2026-09-24, all with body text — available only after the
2026-10-09 PBC backfill (the 沟通交流 section was capped at 40 pages and the documented
`--max-pages 411` override did not work, so the corpus held 31 PBC documents before and
6,099 after).

NO PANEL CONTROL, deliberately. This is a fixed institution on a fixed cadence producing
a fixed genre, so the denominator is one readout per quarter by construction — unlike
every other series in this corpus, which needs `panel.py`. The measure is PRESENCE, not
count: readout length roughly doubles over the period (546 chars in 2009-04 to
1,300-1,700 from 2023), so a count-based measure would inflate later quarters.

  python3 scripts/rnd/analysis/pbc_stance.py
"""
import re
import sqlite3
from collections import OrderedDict

c = sqlite3.connect("file:documents.db?mode=ro", uri=True)
rows = c.execute("""SELECT id, title, date_published, COALESCE(body_text_cn,'')
                    FROM documents WHERE site_key='pbc'
                      AND title LIKE '%货币政策委员会%' AND title LIKE '%例会%'
                    ORDER BY date_published""").fetchall()
print("MPC quarterly readouts: %d   %s .. %s"
      % (len(rows), rows[0][2][:10], rows[-1][2][:10]))
print("  with body text: %d" % sum(1 for r in rows if len(r[3]) > 200))

STANCE = OrderedDict([
    ("稳健", r"稳健"),                      # prudent — the long default
    ("适度宽松", r"适度宽松"),              # moderately loose
    ("灵活适度", r"灵活适度"),
    ("精准有力", r"精准有力"),
    ("逆周期", r"逆周期"),
    ("跨周期", r"跨周期"),
    ("以我为主", r"以我为主"),              # RMB autonomy
    ("合理均衡", r"合理均衡"),              # the FX-level phrase
    ("双向浮动", r"双向浮动"),
    ("超调", r"超调"),                      # "overshoot" — intervention language
])

print("\n%-10s %-7s %s" % ("quarter", "chars", "stance terms present"))
hits = {k: [] for k in STANCE}
for did, t, dp, body in rows:
    if len(body) < 200:
        continue
    present = [k for k, pat in STANCE.items() if re.search(pat, body)]
    for k in present:
        hits[k].append(dp[:7])
    print("%-10s %-7d %s" % (dp[:7], len(body), " ".join(present) or "—"))

print("\n=== first and last appearance of each stance term ===")
for k in STANCE:
    v = sorted(hits[k])
    print("  %-10s n=%-4d %s" % (k, len(v), (v[0] + " .. " + v[-1]) if v else "never"))
