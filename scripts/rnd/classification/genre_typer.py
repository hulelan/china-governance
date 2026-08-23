#!/usr/bin/env python3
"""
genre_typer.py — refined rule-based Chinese-government document GENRE classifier.

WHY THIS EXISTS
---------------
`scripts/compute_scores.py:classify_doc_type()` produces the stored `algo_doc_type`.
On the live corpus (~263k docs) its top bucket is `other` at ~131.7k docs (~50%).
That coarseness cripples any analysis that slices by document type.

This module is a *standalone* drop-in replacement for that title->genre step. It
recovers a large slice of `other` by handling the real cases the old ruleset misses:

  1. HTML noise in titles  (<strong>, <br/>, &nbsp; ...).
  2. Trailing ANNOTATIONS after the genre word, which defeat the old `$`-anchored
     rules, e.g.
         "...的通知（发改价格〔2026〕413号）"     <- 通知 not at end
         "...公告 第270号"                          <- 公告 not at end
         "...的决定"  vs  "...条例》的决定"          <- 决定 unseen by old rules
         "...部门决算"  "...年度报告"  "...结果公示"   <- whole genres unseen
     We strip a trailing (文号 / date / 【已废止】 / 第N号 / issuing-date) run before
     applying suffix rules, while still matching genre words that appear mid-title
     via the `关于……的X` frame.
  3. Whole genres the old set never had: 意见/指导意见, 决定/决议, 通报, 公示,
     令(decree), 法(law), 部门预算/决算(budget), 年度报告(report),
     招标/中标/采购(procurement).

It is deliberately CONSERVATIVE about news headlines (leader-activity readouts,
international news, sports, features): those legitimately have no 公文种类 and are
left as `other`. The goal is precision on recovered docs, not zero `other`.

HOW TO WIRE IT IN LATER (do NOT auto-apply — left for a human)
--------------------------------------------------------------
`compute_scores.py` is the hot path (runs nightly in daily_sync.sh Phase 2).
To adopt this classifier there, WITHOUT changing its call sites:

  1. In compute_scores.py, replace the body of `classify_doc_type(title)` with a
     call into this module, passing the document_number too:

         from scripts.rnd.classification.genre_typer import classify
         def classify_doc_type(title, document_number=""):
             return classify(title, document_number)

     (or copy DOC_GENRE_PATTERNS + classify() inline to avoid the import path).

  2. compute_scores.py currently selects only `id, title` for the type pass
     (see build_doc_types / the SELECT around line 268). Add `document_number`
     to that SELECT and pass it through, so the 文号-based rules (decree/law/
     announcement) can fire. The function tolerates an empty document_number.

  3. The genre KEYS here are a SUPERSET of the old ones (same names reused where
     they mean the same thing) plus new keys: opinion, decision, circular,
     publicity, decree, law, budget, report, procurement, plan, request.
     The web Browse filter reads distinct `algo_doc_type` values dynamically, so
     new keys appear automatically — but check any hard-coded type lists/labels
     in web/ before shipping. English labels for the UI are in GENRE_LABELS_EN.

  4. Re-run is cheap & score-preserving: compute_scores.py already diffs and
     UPDATEs only rows whose computed type changed (see its 2026-08-10 note), so
     adopting this re-types the changed docs and writes a few tens of thousands of
     rows once, not all 263k.

CLI
---
    python3 scripts/rnd/classification/genre_typer.py --self-test
    python3 scripts/rnd/classification/genre_typer.py --sample 8000
        # ssh's a random `other` sample off the droplet (read-only) and reports
        # the before/after `other` rate + a per-genre breakdown of what moved.
    python3 scripts/rnd/classification/genre_typer.py --tsv path.tsv
        # score a local id\tdocnum\tsite\ttitle TSV (offline; no ssh).
"""
from __future__ import annotations

import re
import sys
import html as _html

# --------------------------------------------------------------------------
# Title normalization
# --------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# A trailing annotation run we strip before applying suffix ($) rules.
# Matches one-or-more trailing groups of:
#   （…） or (…)   — 文号, dates, 第N号, 批次, （已废止）…
#   【…】          — 【已废止】/【已失效】
#   〔…〕 号        — bare 文号 without wrapping parens
#   trailing ISO date "2025-11-20"  or  "（2022年10月）"
_TRAILING_ANNOT_RE = re.compile(
    r"(?:"
    r"\s*[（(][^（）()]{0,60}[）)]"          # (...) or （...）
    r"|\s*【[^【】]{0,30}】"                 # 【...】
    r"|\s*〔[^〔〕]{1,12}〕\s*第?\s*[\dA-Za-z]{0,8}号?"  # 〔2024〕123号
    r"|\s*第[\d〇零一二三四五六七八九十百]{1,8}号"        # 第270号 / 第十六号
    r"|\s*[\-—]\s*\d{4}[-.年]\d{1,2}([-.月]\d{1,2})?[日]?"  # -2025-11-20
    r"|\s*\d{4}-\d{1,2}-\d{1,2}\s*$"        # trailing 2025-11-20
    r"|\s*（?已(废止|失效|作废|修订|修改)）?"  # 已废止 tails
    r")+\s*$"
)


def clean_title(title: str) -> str:
    """Strip HTML, unescape entities, collapse whitespace."""
    if not title:
        return ""
    t = _html.unescape(title)
    t = _TAG_RE.sub(" ", t)
    t = t.replace("　", " ")  # ideographic space
    t = _WS_RE.sub(" ", t).strip()
    return t


def core_title(title: str) -> str:
    """`clean_title` minus trailing 文号/date/废止 annotations, for $-anchored rules.

    Applied repeatedly because titles can carry stacked tails, e.g.
    "……的通知（珠府办函〔2023〕75号）（已废止）".
    """
    t = clean_title(title)
    for _ in range(4):
        nt = _TRAILING_ANNOT_RE.sub("", t).strip()
        # also drop trailing quote/space debris left behind
        nt = re.sub(r"[》）)\s、，,。.·\-—]+$", "", nt).strip()
        if nt == t or not nt:
            break
        t = nt
    return t


# --------------------------------------------------------------------------
# Ordered rule set. First match wins. Each rule: (compiled_regex, target, where)
#   where = "core"  -> test against core_title (annotations stripped)
#   where = "full"  -> test against clean_title (annotations kept)
# Rules are ordered most-specific -> most-general so that, e.g., 征求意见 lands in
# `consultation` before the generic 意见 rule, and 实施方案 in action_plan before
# the generic 方案 rule.
# --------------------------------------------------------------------------

_RULES_RAW = [
    # --- interpretations & explainers (FIRST: an 一图读懂/解读 OF a 办法 is an
    #     explainer, not the regulation itself) --------------------------------
    (r"一图读懂|图解|图读|政策问答|答记者问|解读|问答$", "explainer", "full"),

    # --- laws & regulations -------------------------------------------------
    (r"条例$|办法$|规定$|规则$|准则$|细则$|章程$|规程$", "regulation", "core"),
    # law: title (core) ends in 法 / 法典 but NOT the common non-law bigrams
    # (办法 already caught above; exclude 方法/做法/说法/看法/想法/用法/疗法/语法/历法/手法/活法/玩法/走法/打法).
    (r"(?<!方)(?<!做)(?<!说)(?<!看)(?<!想)(?<!用)(?<!疗)(?<!语)(?<!历)(?<!手)"
     r"(?<!活)(?<!玩)(?<!走)(?<!打)(?<!无)(?<!合)(?<!非)(?<!违)(?<!司)(?<!军)"
     r"(?<!笔)(?<!book)法$|法典$", "law", "core"),

    # --- decrees / orders ---------------------------------------------------
    (r"^.{0,40}令$|第[\d〇零一二三四五六七八九十百]{1,6}号令|府令\s*\d", "decree", "core"),

    # --- action plans / strategies / plans ---------------------------------
    (r"行动计划|行动方案", "action_plan", "full"),
    (r"实施方案|实施意见|实施细则|工作方案$|专项方案", "action_plan", "full"),
    (r"发展规划|发展纲要|.规划纲要|五年规划|规划》|印发.{0,24}规划|.{2,}规划$", "strategy", "full"),
    (r"工作计划$|工作要点$|工作方案", "work_plan", "core"),
    (r"方案$", "plan", "core"),

    # --- policy issuance (关于印发X的通知) ---------------------------------
    (r"关于印发|印发《", "policy_issuance", "full"),

    # --- subsidies & funding ------------------------------------------------
    (r"补贴|资助|奖励|扶持|专项资金|引导基金|以奖代补", "subsidy", "full"),

    # --- consultation (must precede generic 意见) --------------------------
    (r"征求.*?意见|意见征集|公开征求|征集意见|意见的公告|意见稿", "consultation", "full"),

    # --- opinions / guiding opinions ---------------------------------------
    (r"指导意见|.的意见$|意见$", "opinion", "core"),

    # --- decisions & resolutions -------------------------------------------
    (r"的决定$|决定$|的决议$|决议$", "decision", "core"),

    # (explainer handled first, above)

    # --- application guides -------------------------------------------------
    (r"申报.{0,10}指南|申报.{0,10}通知|申报.{0,10}公告|申报指引|申报须知", "application_guide", "full"),

    # --- procurement --------------------------------------------------------
    (r"招标|中标|采购结果|采购公告|采购项目|询价|竞争性磋商|竞争性谈判|成交结果|"
     r"评标结果|中选结果|比选|招投标|采购意向", "procurement", "full"),

    # --- publicity (公示) ---------------------------------------------------
    (r"公示$|公示名单|结果公示|名单公示|拟.{0,8}公示|情况公示|公示（|公示\(|予以公示", "publicity", "core"),
    (r"公示", "publicity", "full"),

    # --- standards ----------------------------------------------------------
    (r"标准$|国家标准|行业标准|团体标准|地方标准|技术规范$", "standard", "core"),

    # --- announcements (公告/通告/公报) ------------------------------------
    (r"公告$|通告$|公报$", "announcement", "core"),
    (r"公告\s*第?\d|第.{1,6}号公告|公告\d{4}年|公告（|通告（|通告\s*第", "announcement", "full"),

    # --- circulars (通报) ---------------------------------------------------
    (r"通报$|情况的?通报|.的通报$|予以通报|通报表扬|通报批评", "circular", "core"),
    (r"通报", "circular", "full"),

    # --- budgets & final accounts ------------------------------------------
    (r"部门预算|部门决算|财政预算|财政决算|预算公开|决算公开|预算报告|决算报告|"
     r"预算$|决算$|预算安排|三公经费", "budget", "full"),

    # --- reports (年度报告 / analysis / self-assessment) -------------------
    # report words anchored near end (core, so a trailing date is stripped first);
    # keeps "…年度报告" but NOT "《…研究报告》评审工作" (a meeting readout).
    (r"年度报告$|工作报告$|统计报告$|分析报告$|自评报告$|履职报告$|评估报告$|"
     r"监测报告$|研究报告$|专项报告$|信息公开.{0,10}报告$", "report", "core"),

    # --- consultation / meeting minutes / admin ----------------------------
    (r"会议纪要|纪要$|工作总结|述职|议程$", "administrative", "full"),

    # --- personnel ----------------------------------------------------------
    (r"任免|任命|聘任|录用|拟任|任职的通知|免职|职务任免|人事任免", "personnel", "full"),
    (r"招聘|公开选调|遴选公告|选聘", "personnel", "full"),

    # --- replies / official letters ----------------------------------------
    (r"批复$|复函$|的复$|函$", "reply", "core"),

    # --- requests (请示) ----------------------------------------------------
    (r"请示$|的请示", "request", "core"),

    # --- notices (通知) — general catch late so specific 通知 frames win first
    (r"通知$|的通知$", "notice", "core"),
    (r"关于.{0,40}的通知", "notice", "full"),
    (r"通知", "notice", "full"),

    # --- media / commentary -------------------------------------------------
    (r"评论|社论|时评|锐评|快评|论坛|观察$", "commentary", "full"),
    (r"专访|访谈|对话$", "interview", "full"),
    (r"综述|述评|盘点|回顾$", "review", "full"),
]

DOC_GENRE_PATTERNS = [(re.compile(p), t, w) for p, t, w in _RULES_RAW]

# --------------------------------------------------------------------------
# document_number-based fallback: if the title is silent but the 文号 names a
# genre, use it. 文号 kind chars appear right before 〔YYYY〕:  X府令 / X发 / X函 / …
# --------------------------------------------------------------------------
_DOCNUM_RULES = [
    (re.compile(r"令\s*第?\s*\d"), "decree"),
    (re.compile(r"令\s*\d"), "decree"),
    (re.compile(r"函〔"), "reply"),
    (re.compile(r"通知"), "notice"),
]


def classify(title: str, document_number: str = "") -> str:
    """Return a genre key for a gov document. Falls back to 'other'.

    Pure function of (title, document_number). Never raises on bad input.
    """
    core = core_title(title)
    full = clean_title(title)
    if not core and not full:
        return "unknown"
    for rx, target, where in DOC_GENRE_PATTERNS:
        hay = core if where == "core" else full
        if hay and rx.search(hay):
            return target
    # 文号 fallback
    if document_number:
        dn = document_number.strip()
        for rx, target in _DOCNUM_RULES:
            if rx.search(dn):
                return target
    return "other"


GENRE_LABELS_EN = {
    "regulation": "Regulation", "law": "Law", "decree": "Decree/Order",
    "action_plan": "Action Plan", "strategy": "Strategy/Plan", "work_plan": "Work Plan",
    "plan": "Plan/Scheme", "policy_issuance": "Policy Issuance", "subsidy": "Subsidy/Funding",
    "consultation": "Public Consultation", "opinion": "Opinion/Guidance",
    "decision": "Decision/Resolution", "explainer": "Explainer",
    "application_guide": "Application Guide", "procurement": "Procurement",
    "publicity": "Publicity Notice", "standard": "Standard", "announcement": "Announcement",
    "circular": "Circular (通报)", "budget": "Budget/Final Accounts", "report": "Report",
    "administrative": "Administrative", "personnel": "Personnel", "reply": "Reply/Letter",
    "request": "Request (请示)", "notice": "Notice", "commentary": "Commentary",
    "interview": "Interview", "review": "Review", "other": "Other", "unknown": "Unknown",
}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

_SELF_TESTS = [
    ("关于优化完善无线电频率占用费标准的通知(发改价格〔2026〕413号)", "", "notice"),
    ("中华人民共和国农业农村部公告 第270号", "", "announcement"),
    ("江苏省人民代表大会常务委员会关于停止执行《江苏省环境保护条例》第四十四条处罚权限规定的决定", "", "decision"),
    ("中共中央 国务院关于全面加强新时代大中小学劳动教育的意见", "", "opinion"),
    ("反分裂国家法", "", "law"),
    ("《上海市长兴岛开发建设管理办法》（沪府令12号）", "", "regulation"),
    ("2023年深圳市社会保险基金管理局龙岗分局部门决算", "", "budget"),
    ("深圳市民政局2019年政府信息公开工作年度报告", "", "report"),
    ("司法鉴定管理服务项目中标结果公示", "", "procurement"),
    ("采购结果公示", "", "procurement"),
    ("深圳市社会组织管理局承接政府职能转移和购买服务社会组织推荐目录编制项目招标公告（第二次）", "", "procurement"),
    ("重庆市水利局办公室关于2026年水利工程建设项目勘察设计成果质量抽查（第二批次）情况的通报 2026-07-10", "", "circular"),
    ("国防科工局关于废止部分规范性文件的决定", "", "decision"),
    ("中共中央办公厅 国务院办公厅印发《关于进一步深化税收征管改革的意见》", "", "policy_issuance"),
    ("《可再生能源发展“十五五”规划》发布", "", "strategy"),
    ("市委常委会召开会议", "", "other"),
    ("习近平会见柬埔寨人民党主席、参议院主席洪森", "", "other"),
    ("中共深圳市民政局党组关于邢享明同志任职的通知", "深民党组任〔2022〕20号", "personnel"),
    ("关于《中华人民共和国刑法修正案（九）（草案）》的说明", "", "other"),
    ("2025年广东省商务厅部门预算", "", "budget"),
    ("市场监管总局反垄断二司相关负责人就《横向经营者集中审查指引》答记者问", "", "explainer"),
    ("深圳市住房保障署面向人才配售住房通告（住保售〔2025〕018号）", "", "announcement"),
]


def _self_test():
    ok = 0
    for title, dn, expected in _SELF_TESTS:
        got = classify(title, dn)
        mark = "OK " if got == expected else "XX "
        if got == expected:
            ok += 1
        else:
            print(f"{mark}exp={expected:14s} got={got:14s} | {title[:50]}")
    print(f"\nself-test: {ok}/{len(_SELF_TESTS)} passed")
    return ok == len(_SELF_TESTS)


def _score_rows(rows):
    """rows: iterable of (id, docnum, site, title). Print before/after report."""
    from collections import Counter
    n = 0
    recovered = Counter()
    still_other = []
    recovered_rows = []
    for _id, dn, site, title in rows:
        n += 1
        g = classify(title, dn)
        if g == "other" or g == "unknown":
            still_other.append((_id, site, title))
        else:
            recovered[g] += 1
            recovered_rows.append((_id, site, g, title))
    if n == 0:
        print("no rows")
        return
    rec = n - len(still_other)
    print(f"\nSample size (all currently `other`): {n:,}")
    print(f"Still `other` after refined rules : {len(still_other):,}  ({len(still_other)/n*100:.1f}%)")
    print(f"Recovered into a genre            : {rec:,}  ({rec/n*100:.1f}%)")
    print("\nRecovered breakdown:")
    for g, c in recovered.most_common():
        print(f"  {g:18s} {c:6,}  ({c/n*100:.1f}%)")
    return recovered_rows, still_other


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--sample", type=int, metavar="N",
                    help="ssh a random N-row `other` sample off the droplet and report")
    ap.add_argument("--tsv", metavar="PATH",
                    help="score a local id\\tdocnum\\tsite\\ttitle TSV (offline)")
    ap.add_argument("--show-recovered", type=int, default=0,
                    help="print this many recovered examples per genre")
    ap.add_argument("--host", default="root@104.236.88.45")
    args = ap.parse_args(argv)

    if args.self_test:
        return 0 if _self_test() else 1

    rows = []
    if args.tsv:
        with open(args.tsv, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 4:
                    continue
                rows.append((parts[0], parts[1], parts[2], parts[3]))
    elif args.sample:
        import subprocess
        sql = (
            "SELECT id, COALESCE(document_number,''), COALESCE(site_key,''), title "
            "FROM documents WHERE algo_doc_type='other' AND title != '' "
            f"ORDER BY RANDOM() LIMIT {int(args.sample)};"
        )
        cmd = ["ssh", args.host,
               f"cd /root/china-governance && sqlite3 documents.db \".mode tabs\" \"{sql}\""]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        for line in out.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 4:
                rows.append((parts[0], parts[1], parts[2], parts[3]))
    else:
        ap.print_help()
        return 0

    result = _score_rows(rows)
    if args.show_recovered and result:
        recovered_rows, _ = result
        from collections import defaultdict
        byg = defaultdict(list)
        for _id, site, g, title in recovered_rows:
            byg[g].append((_id, title))
        print("\n--- recovered examples ---")
        for g, items in byg.items():
            print(f"\n[{g}]")
            for _id, title in items[:args.show_recovered]:
                print(f"  {_id}  {title[:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
