"""Test classification prompt against an evaluation set.

Runs the v2 prompt against specific documents and compares results.

Usage:
    DEEPSEEK_API_KEY="sk-..." python3 scripts/eval_classification.py
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

from openai import OpenAI

DB_PATH = Path(__file__).parent.parent / "documents.db"

PROMPT_V2 = """You are classifying Chinese government and policy documents for a Western analyst research database.
Given the document below, output a JSON object with these fields:

- title_en: English translation of the title (concise, formal government style)
- summary_en: 1-2 sentence English summary of what this document does or requires
- doc_type: the type of document — see guide below
- policy_significance: how important is the UNDERLYING POLICY OR TOPIC (not this document itself) — one of [high, medium, low]
- topics: array of 1-3 English topic tags (e.g. "artificial intelligence", "housing", "environmental protection")
- policy_area: short Chinese topic label (e.g. "人工智能", "住房保障", "环境保护")
- references: array of Chinese policy names or document numbers referenced in the text (e.g. ["关于深入实施'人工智能+'行动的意见", "国发〔2025〕11号"]). Empty array if none found.

## doc_type — what IS this document?

- original_policy: The authoritative text of a policy, regulation, opinion, plan, or directive (意见, 通知, 办法, 规划, 方案, 条例, 规章, 若干措施). This is the PRIMARY source. IMPORTANT: "印发《X》的通知" (notice issuing X) IS the original — it's the government publishing X for the first time, not relaying it.
- relay_notice: A notice that FORWARDS a policy from a DIFFERENT (usually higher-level) body (转发...的通知). The key test: did the issuer write the policy, or just pass it along? If the title says "转发XX省/XX部关于...", it's a relay.
- interpretation: An official government explanation of a policy's rationale or implementation details (政策解读, 解读). Published by the issuing agency or designated experts.
- explainer: A visual or simplified summary of a policy (图解, 一图读懂, 秒懂, 速览, 政策图解). Derivative — the original policy exists separately.
- media_exclusive: Journalism that reveals non-public information or provides first-of-kind industry data (独家, exclusive reports, first disclosures of deals/products/data).
- media_coverage: General news reporting, conference recaps, event coverage, opinion pieces, or industry overviews.
- research: Academic papers, think tank reports, white papers, data reports.
- personnel: Appointment or removal notices (任免, 职务任免).
- procurement: Bidding announcements, procurement results, public name lists, license transfers.
- other: Anything that doesn't fit above (speeches, meeting minutes, event notices, photo galleries).

## policy_significance — how important is the TOPIC/POLICY being discussed?

This is about the underlying subject matter, NOT about this particular document. An infographic (图解) about an important AI policy still has HIGH policy_significance — the policy matters, even though this document is just a summary.

HIGH:
  - National-level policy frameworks or strategies (e.g., AI+ action plan, data governance, dual carbon)
  - Major regulatory changes affecting broad industries
  - Significant funding programs (billions of yuan)
  - Technology export controls, trade restrictions
  - Topics with international implications

MEDIUM:
  - Provincial or city-level implementation of national policy
  - Sector-specific regulations (single industry, limited geography)
  - Standard budgetary or fiscal matters
  - Routine regulatory updates to existing frameworks

LOW:
  - Internal administrative procedures
  - Individual personnel decisions
  - Procurement and bidding
  - Local event notices, traffic diversions, name lists
  - Topics with no broader policy implications
  - Note: a leader speech ABOUT an important topic (e.g., AI) still has the policy_significance of that topic. The doc_type (media_coverage) already captures that it's a speech, not a policy.

Document title: {title}
Document number: {doc_number}
Publisher: {publisher}
CMS category (if available): {classify_main_name}
Body excerpt (Chinese): {body_excerpt}

Output ONLY valid JSON, no explanation."""

# Eval set: (expected_doc_type, expected_policy_significance, issue_category, title_fragment)
EVAL_SET = [
    # Media articles — should be media type, varied significance
    ("media_exclusive", "high", "media_always_low",
     "晚点独家丨火山引擎豆包大模型日均调用量破百万亿 Tokens"),
    ("media_exclusive", "high", "media_always_low",
     "晚点独家丨Momenta 港股秘密递表，预计年内上市"),
    ("media_coverage", "medium", "media_always_low",
     "京东京造，加速制造 AI+ 爆款"),
    ("media_coverage", "medium", "media_always_low",
     "Openclaw 之外，另一种做 Agent 的方式丨100 个 AI 创业者"),

    # Explainers — should be explainer type, significance matches the policy
    ("explainer", "medium", "explainer_overrated",
     "图解《深圳市龙华区促进人工智能产业发展若干措施》"),
    ("explainer", "low", "explainer_overrated",
     "一图读懂2021年河源市政府工作报告"),

    # District promo — should be low significance
    ("other", "low", "district_promo",
     "大鹏新区坝光开发署2022年工作计划"),

    # Relay notices — should be relay_notice type
    ("relay_notice", "medium", "relay_notice",
     "汕尾市人民政府转发广东省人民政府关于印发"),

    # True original policies — should be original_policy, high significance
    ("original_policy", "high", "correct_original",
     "印发《关于深化电力现货市场建设试点工作的意见》 的通知"),
    ("original_policy", "high", "correct_original",
     "国务院办公厅关于推动个人养老金发展的意见"),
    ("original_policy", "high", "correct_original",
     "关于印发《辽宁沿海经济带高质量发展规划》的通知"),
    ("original_policy", "high", "correct_original",
     "深圳市龙华区人民政府办公室关于印发《深圳市龙华区推动人工智能及机器人产业发展若干措施》的通知"),

    # Personnel — should be personnel type, low significance
    ("personnel", "low", "correct_personnel",
     "中共深圳市民政局党组关于谢清顺等同志职务任免的通知"),

    # Procurement — should be procurement type, low significance
    ("procurement", "low", "correct_procurement",
     "深圳市殡葬服务中心关于民俗告别厅等改造及提升工程设计项目招标公告"),

    # Interpretation — should be interpretation type
    ("interpretation", "medium", "interpretation",
     "《深圳市人力资源和社会保障局关于印发〈深圳市青年人才认定和管理办法〉的通知》的政策解读"),

    # Central ministry AI standard — high significance original
    ("original_policy", "high", "correct_central_ai",
     "关于公开征求《人工智能 安全治理 模型上下文协议应用安全要求》等121项行业标准计划项目意见的公示"),

    # Media about leader activities — media_coverage type, but topic (AI) IS significant
    ("media_coverage", "high", "leader_activity",
     "覃伟中参加市政协七届六次会议联组讨论 抢占人工智能产业科技制高点"),
]


def find_doc(conn, title_fragment):
    """Find a doc by title fragment."""
    row = conn.execute(
        """SELECT id, title, document_number, publisher, body_text_cn,
                  classify_main_name, importance, category
           FROM documents WHERE title LIKE ? LIMIT 1""",
        (f"%{title_fragment[:30]}%",),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0], "title": row[1], "document_number": row[2],
        "publisher": row[3], "body_text_cn": row[4],
        "classify_main_name": row[5], "old_importance": row[6],
        "old_category": row[7],
    }


def classify_one(client, doc):
    """Classify a single document with the v2 prompt."""
    body_excerpt = doc["body_text_cn"][:1500] if doc["body_text_cn"] else "(无正文)"
    prompt = PROMPT_V2.format(
        title=doc["title"],
        doc_number=doc["document_number"] or "(无)",
        publisher=doc["publisher"] or "(未知)",
        classify_main_name=doc.get("classify_main_name") or "(无)",
        body_excerpt=body_excerpt,
    )
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=600,
        )
        raw = (resp.choices[0].message.content or "").strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)
    except Exception as e:
        print(f"  Error: {e}")
        return None


def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("Set DEEPSEEK_API_KEY")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=60.0)
    conn = sqlite3.connect(str(DB_PATH))

    print("=== Classification Prompt v2 Eval ===\n")

    correct_type = 0
    correct_sig = 0
    total = 0

    for exp_type, exp_sig, issue, title_frag in EVAL_SET:
        doc = find_doc(conn, title_frag)
        if not doc:
            print(f"  SKIP (not found): {title_frag[:50]}")
            continue

        result = classify_one(client, doc)
        if not result:
            print(f"  FAIL (API error): {title_frag[:50]}")
            continue

        total += 1
        new_type = result.get("doc_type", "?")
        new_sig = result.get("policy_significance", "?")
        refs = result.get("references", [])

        type_ok = new_type == exp_type
        sig_ok = new_sig == exp_sig
        if type_ok:
            correct_type += 1
        if sig_ok:
            correct_sig += 1

        t_icon = "✅" if type_ok else "❌"
        s_icon = "✅" if sig_ok else "❌"

        print(f"[{issue}] {doc['title'][:55]}")
        print(f"  doc_type:           {t_icon} got={new_type:18s} exp={exp_type}")
        print(f"  policy_significance:{s_icon} got={new_sig:6s} exp={exp_sig}")
        print(f"  old importance/cat: {doc['old_importance'] or '?'} / {doc['old_category'] or '?'}")
        if refs:
            print(f"  references:         {refs[:3]}")
        print()

    print(f"=== RESULTS ({total} tested) ===")
    print(f"doc_type accuracy:           {correct_type}/{total} ({100*correct_type/total:.0f}%)")
    print(f"policy_significance accuracy: {correct_sig}/{total} ({100*correct_sig/total:.0f}%)")
    print(f"Both correct:                {sum(1 for _ in range(total))}/{total}")  # placeholder

    conn.close()


if __name__ == "__main__":
    main()
