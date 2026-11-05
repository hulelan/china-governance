"""Extraction and decoding tests for crawlers/finmedia.py and base._decode_text.

Every case here is a defect that shipped and was caught by measuring live pages
on 2026-11-05, not an invented scenario. The CJK-only thresholds are the theme:
three of the four bugs were a rule that worked on Chinese text and silently
returned nothing on everything else.
"""
import pytest

from crawlers import base
from crawlers.finmedia import (
    MIN_BODY_CJK, SITES, _cjk, extract_body, extract_date, extract_title,
)

EN_PARA = ("The People's Bank of China set the midpoint rate at 6.7147 per dollar "
           "today, its strongest level in four years against the greenback. ")
CN_PARA = ("会上，来自教育教学、医疗卫生、科学研究、工业制造、生物制造、农业农村、智慧能源、"
           "交通运输、气象服务等9个领域的21家链主单位代表，围绕高质量数据集建设交流经验做法。")


def _page(title, body_html):
    return f"<html><head><title>{title}</title></head><body>{body_html}</body></html>"


# ---------------------------------------------------------------- titles

def test_english_title_is_extracted():
    """A CJK-only floor made every English page titleless.

    Business Recorder fetched at 277 KB with a usable <title> and returned "".
    """
    html = _page("China's yuan hits 4-year high versus dollar after Fed decision", "")
    assert extract_title(html).startswith("China's yuan hits 4-year high")


def test_chinese_title_still_wins_over_section_suffix():
    html = _page("携手构建全球开放人工智能行动倡议_世界互联网大会", "")
    assert extract_title(html) == "携手构建全球开放人工智能行动倡议"


def test_a_short_junk_title_is_still_rejected():
    assert extract_title(_page("首页", "")) == ""


# ---------------------------------------------------------------- bodies

def test_english_paragraphs_are_kept():
    """15 English <p> of ~250 chars extracted to zero under the CJK-only gate."""
    html = _page("t", "".join(f"<p>{EN_PARA * 3}</p>" for _ in range(4)))
    assert len(extract_body(html)) > 400
    assert "midpoint rate" in extract_body(html)


def test_chinese_paragraphs_are_kept():
    html = _page("t", f"<p>{CN_PARA}</p><p>{CN_PARA}</p>")
    assert _cjk(extract_body(html)) >= MIN_BODY_CJK


def test_short_nav_paragraphs_are_dropped():
    html = _page("t", "<p>首页</p><p>更多</p><p>分享到：</p>" + f"<p>{CN_PARA}</p>")
    body = extract_body(html)
    assert "首页" not in body and "分享到" not in body
    assert CN_PARA[:12] in body


def test_long_line_fallback_for_a_page_with_no_prose_paragraphs():
    """npc.gov.cn had 2 <p> and nda.gov.cn 1, with the body in bare divs."""
    html = _page("t", f"<div><div>{CN_PARA}</div></div>")
    assert _cjk(extract_body(html)) >= 50


def test_script_and_style_never_reach_the_body():
    html = _page("t", f"<script>var x='{CN_PARA}';</script><style>.a{{}}</style>"
                      f"<p>{CN_PARA}</p>")
    assert extract_body(html).count(CN_PARA[:12]) == 1


# ---------------------------------------------------------------- dates

def test_no_generic_fallback_reads_a_cdn_path_as_a_date():
    """The measured failure: 2024-05 off tmtpost's image URL, 2016-07 off huxiu's."""
    html = _page("t", '<img src="https://img.cdn.com/uploads/images/2024/05/2024051332.jpg">')
    assert extract_date("https://www.tmtpost.com/8190090.html", html,
                        SITES["tmtpost"]) == ""


def test_tmtpost_date_is_found_past_the_old_head_window():
    """tmtpost's time span sits near byte 82k; html[:20000] found nothing."""
    html = _page("t", "x" * 90_000 + '<span class="time" data-v-x>2026.11.03 08:45</span>')
    assert extract_date("https://www.tmtpost.com/1.html", html, SITES["tmtpost"]) == "2026-11-03"


def test_huxiu_published_time_meta_is_found_past_the_old_head_window():
    html = ('<html><head>' + '<!-- pad -->' * 3000 +
            '<meta property="article:published_time" content="2026-11-04T20:47:58+08:00">'
            '</head><body></body></html>')
    assert extract_date("https://www.huxiu.com/article/1.html", html,
                        SITES["huxiu"]) == "2026-11-04"


def test_url_date_wins_and_needs_no_html():
    assert extract_date("http://www.ce.cn/a/202611/t20261103_3281360.shtml", "",
                        SITES["ce"]) == "2026-11-03"


def test_jiemian_epoch_timestamp_is_converted():
    html = _page("t", '<span class="date">1762300000</span>')
    assert extract_date("https://www.jiemian.com/article/1.html", html,
                        SITES["jiemian"]).startswith("2025-11-")


def test_an_out_of_range_epoch_is_rejected():
    html = _page("t", '<span class="date">123456789</span>')          # 1973
    assert extract_date("https://www.jiemian.com/article/1.html", html,
                        SITES["jiemian"]) == ""


# ---------------------------------------------------------------- decoding

def test_gbk_page_is_decoded_by_its_declared_charset():
    """hn.chinanews.com.cn gave 2,538 chars of which 10 were CJK, title included.

    A mojibake title is invisible to both FTS indexes, can never be a citation
    target and can never match a title_reissue edge.
    """
    text = ('<html><head><meta charset="gb2312"></head><body>'
            + "湖南省网信办集中约谈某文化传媒公司及4家大模型运营单位。" * 30
            + '</body></html>')
    out = base._decode_text(text.encode("gb18030"))
    assert out.count("�") == 0
    assert _cjk(out) > 500
    assert "湖南省网信办" in out


def test_utf8_pages_decode_identically_after_the_charset_fix():
    """The safety property: a page that decoded cleanly before must not change."""
    text = "<html><body>" + "正常的中文页面。" * 50 + "</body></html>"
    raw = text.encode("utf-8")
    assert base._decode_text(raw) == text


def test_a_few_stray_bad_bytes_do_not_trigger_a_re_decode():
    """Only a systematically wrong decode re-decodes; a stray byte is left alone."""
    raw = ("<html><body>" + "正常的中文页面。" * 400 + "</body></html>").encode("utf-8")
    raw = raw[:60] + b"\xff\xfe" + raw[60:]
    out = base._decode_text(raw)
    assert "正常的中文页面" in out


def test_gb18030_without_a_declared_charset_still_recovers():
    text = "<html><body>" + "国家数据局召开行业高质量数据集链主工作座谈会。" * 40 + "</body></html>"
    out = base._decode_text(text.encode("gb18030"))
    assert _cjk(out) > 500


@pytest.mark.parametrize("key", sorted(SITES))
def test_every_site_declares_what_extract_date_needs(key):
    cfg = SITES[key]
    assert cfg.get("date_url") or cfg.get("date_pats") or cfg.get("date_epoch") \
        or key == "caixin", f"{key} can never produce a date"
    assert cfg["tier"] in (1, 2, 3)
    assert "admin_level" not in cfg, "level is set at store time, not per site"
