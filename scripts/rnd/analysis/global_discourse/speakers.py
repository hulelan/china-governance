"""Speaker type of a document, shared by the global-discourse scans."""
PARTY = {"qstheory", "dangyuan"}
STATE = {"xinhua", "people", "ce", "jjckb", "stdaily", "cnr", "cctv", "chinanews", "people_rmrb",
         "peopleapp", "newscn", "xinhua_lw", "xinhua_en"}
COMM = {"guancha", "ifeng"}
BIZ = {"yicai", "jiemian", "36kr", "latepost", "qbitai", "eeo", "huxiu", "tmtpost", "elsewhere",
       "21jingji", "cnfin", "eastmoney", "guandian", "qqnews", "thepaper"}
RES = {"cass", "amr", "tsinghua_aiig", "cast", "isc"}

def speaker(site, lvl):
    if site in PARTY: return "party_theory"
    if site == "mfa": return "diplomacy"
    if site in STATE: return "state_media"
    if site in COMM: return "commentary"
    if site in BIZ: return "business_press"
    if site in RES: return "research"
    if lvl == "central": return "central"
    if lvl in ("provincial", "municipal", "district", "department"): return "subnational"
    return None

