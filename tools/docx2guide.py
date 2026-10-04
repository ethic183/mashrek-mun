#!/usr/bin/env python3
"""
Convert a committee topic brief (.docx) into a study-guide page fragment.

    python3 tools/docx2guide.py "path/to/Brief.docx" <committee-slug>
    python3 tools/docx2guide.py "path/to/Brief.txt"  <committee-slug>   (plain text also works)
    python3 build.py

Writes content/<committee-slug>.html. Needs only Python 3 (no extra packages).

The brief should follow the "MUN Topic Description Structure":
  Council Overview → TOPIC A (1. Introduction & Background, 2. Key Issues &
  Challenges, 3. International Perspectives, 4. Previous International Action)
  → TOPIC B (same). Bold paragraphs are treated as headings, bulleted list
  items become bullet lists, and bold words inside paragraphs stay bold.
  English and Arabic briefs are both supported (Arabic is laid out right-to-left).
"""
import html
import os
import re
import sys
import zipfile

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

AR_LETTERS = ["أ", "ب", "ج", "د", "هـ", "و", "ز", "ح"]
EN_LETTERS = list("ABCDEFGH")

SECTION_KEYS = [
    # (english keywords, arabic keywords)
    (("introduction", "background"), ("المقدمة", "الخلفية")),
    (("key issues", "key legal issues", "challenges"), ("القضايا", "التحديات")),
    (("perspectives", "positions", "stakeholders"), ("المواقف", "أصحاب المصلحة")),
    (("previous", "action"), ("الإجراءات", "السابقة")),
]


def esc(s):
    return html.escape(s, quote=True)


# ------------------------------------------------------------------ read docx

def read_paragraphs(path):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    out = []
    for p in root.iter(W + "p"):
        style_el = p.find(f"{W}pPr/{W}pStyle")
        style = style_el.get(W + "val") if style_el is not None else ""
        is_list = p.find(f"{W}pPr/{W}numPr") is not None
        runs = []
        for r in p.iter(W + "r"):
            text = ""
            for node in r:
                if node.tag == W + "t":
                    text += node.text or ""
                elif node.tag in (W + "tab",):
                    text += " "
                elif node.tag in (W + "br", W + "cr"):
                    text += " "
            if not text:
                continue
            b = r.find(f"{W}rPr/{W}b")
            bold = b is not None and b.get(W + "val", "true") not in ("0", "false")
            runs.append((text, bold))
        text = "".join(t for t, _ in runs)
        if not text.strip() or text.strip() in (".", "•"):
            continue
        visible = [(t, bd) for t, bd in runs if t.strip()]
        all_bold = bool(visible) and all(bd for _, bd in visible)
        out.append({"style": style, "list": is_list, "runs": runs,
                    "text": re.sub(r"\s+", " ", text).strip(), "bold": all_bold})
    return out


def read_text(path):
    """Plain-text brief: short lines ending in ':' (and topic / section names) count as headings."""
    out = []
    for line in open(path, encoding="utf-8").read().splitlines():
        text = re.sub(r"\s+", " ", line).strip()
        if not text or text in (".", "•"):
            continue
        is_list = bool(re.match(r"^[•\-*]\s+", text))
        text = re.sub(r"^[•\-*]\s+", "", text)
        heading = (len(text) < 90 and text.endswith((":", ";"))) or bool(TOPIC_RE.match(text)) \
            or (len(text) < 60 and section_index(text) is not None and not text.endswith(".")) \
            or bool(OVERVIEW_RE.match(text)) or (not out and len(text) < 90)
        out.append({"style": "", "list": is_list, "runs": [(text, heading)], "text": text, "bold": heading})
    return out


def inline_html(runs):
    """Runs → HTML, keeping bold words bold and merging neighbouring runs."""
    merged = []
    for t, b in runs:
        if merged and merged[-1][1] == b:
            merged[-1][0] += t
        else:
            merged.append([t, b])
    parts = []
    for t, b in merged:
        t = esc(t)
        if b and t.strip():
            lead = t[: len(t) - len(t.lstrip())]
            trail = t[len(t.rstrip()):]
            parts.append(f"{lead}<strong>{t.strip()}</strong>{trail}")
        else:
            parts.append(t)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


# ------------------------------------------------------------------ classify

def is_arabic(paras):
    txt = "".join(p["text"] for p in paras)
    ar = len(re.findall(r"[؀-ۿ]", txt))
    return ar > len(re.findall(r"[A-Za-z]", txt))


def section_index(text):
    t = re.sub(r"^\s*\d+\s*[.)]\s*", "", text).lower()
    for i, (en, ar) in enumerate(SECTION_KEYS):
        if any(k in t for k in en) or any(k in text for k in ar):
            return i
    return None


TOPIC_RE = re.compile(r"^\s*((topic|event)\s*([A-Za-z0-9]+)|الموضوع\s+(\S+))\s*[:：\-–—]?\s*(.*)$", re.I)
OVERVIEW_RE = re.compile(r"^(council overview|overview|نبذة عن المجلس|نظرة عامة)", re.I)
CONCLUSION_RE = re.compile(r"^(conclusion|summary|الخلاصة|الخاتمة)\s*:?$", re.I)
SUB_PREFIX_RE = re.compile(r"^\s*([A-Za-z]|[أبجده]ـ?|هـ)\s*[.)\-–]\s+")


def parse(paras):
    doc = {"overview": [], "topics": [], "conclusion": []}
    cur_topic = None
    cur_section = None
    target = None  # list we append blocks to
    awaiting_title = False
    first_heading_skipped = False

    for p in paras:
        text = p["text"]
        heading_like = p["bold"] or p["style"].lower().startswith("heading")

        if heading_like and not first_heading_skipped and not doc["overview"] and not doc["topics"]:
            first_heading_skipped = True
            if not OVERVIEW_RE.match(text) and not TOPIC_RE.match(text):
                continue  # document title, e.g. "SECURITY COUNCIL"

        if heading_like and OVERVIEW_RE.match(text):
            target = doc["overview"]; cur_topic = None; cur_section = None
            continue
        m = TOPIC_RE.match(text) if heading_like else None
        if m:
            unit = (m.group(2) or "").lower()
            cur_topic = {"title": m.group(5).strip(), "sections": [], "unit": "Event" if unit == "event" else ""}
            doc["topics"].append(cur_topic)
            cur_section = None; target = None
            awaiting_title = not cur_topic["title"]
            continue
        if awaiting_title and heading_like:
            cur_topic["title"] = text; awaiting_title = False
            continue
        if heading_like and CONCLUSION_RE.match(text):
            target = doc["conclusion"]; cur_topic = None; cur_section = None
            continue
        if cur_topic is not None and heading_like and section_index(text) is not None and \
                (p["list"] or re.match(r"^\s*\d", text) or p["style"].lower().startswith("heading")
                 or len(text) < 60):
            title = re.sub(r"^\s*\d+\s*[.)]\s*", "", text).strip().rstrip(":;").strip()
            if not re.search(r"[\u0600-\u06FF]", title):   # English: consistent title case
                small = {"and", "of", "the", "in", "on", "for", "to", "a", "an", "&"}
                title = " ".join(w if (i and w.lower() in small) else w[:1].upper() + w[1:]
                                 for i, w in enumerate(title.split()))
            cur_section = {"title": title, "blocks": []}
            cur_topic["sections"].append(cur_section)
            target = cur_section["blocks"]
            continue
        if cur_section is not None and heading_like and not p["list"] and len(text) < 120:
            target.append({"type": "sub", "text": SUB_PREFIX_RE.sub("", text).strip().rstrip(":;").strip()})
            continue
        if cur_topic is not None and cur_section is None:
            # Topic text that starts without an "Introduction & Background" heading
            cur_section = {"title": "المقدمة والخلفية" if re.search(r"[\u0600-\u06FF]", text) else "Introduction & Background",
                           "blocks": []}
            cur_topic["sections"].append(cur_section)
            target = cur_section["blocks"]
        if target is None:
            target = doc["overview"]
        if target is doc["overview"] and heading_like and len(text) < 120:
            target.append({"type": "h", "text": text.rstrip(":;").strip()})
            continue
        block = {"type": "li" if p["list"] else "p", "html": inline_html(p["runs"])}
        target.append(block)
    return doc


# ------------------------------------------------------------------ render

def render_blocks(blocks, letters):
    out, in_list, n = [], False, 0
    for b in blocks:
        if b["type"] == "li":
            if not in_list:
                out.append('<ul class="plain">'); in_list = True
            out.append(f"  <li>{b['html']}</li>")
            continue
        if in_list:
            out.append("</ul>"); in_list = False
        if b["type"] == "h":
            out.append(f'<h4 class="ov-h">{esc(b["text"])}</h4>')
            continue
        if b["type"] == "sub":
            letter = letters[n] if n < len(letters) else str(n + 1)
            n += 1
            out.append(f'<h4><span class="letter">{letter}</span> {esc(b["text"])}</h4>')
        else:
            out.append(f"<p>{b['html']}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def short(title, words=5):
    w = title.split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


def render(doc, arabic):
    L = {
        "toc": "في هذه الصفحة" if arabic else "On this page",
        "overview": "نبذة عن المجلس" if arabic else "Council Overview",
        "topic": (lambda i: ["الموضوع الأول", "الموضوع الثاني", "الموضوع الثالث"][i]) if arabic
                 else (lambda i: f"Topic {EN_LETTERS[i]}"),
        "conclusion": "الخلاصة" if arabic else "Conclusion",
    }
    letters = AR_LETTERS if arabic else EN_LETTERS
    toc = [f'<li><a href="#overview">{L["overview"]}</a></li>']
    body = []

    if doc["overview"]:
        body.append(f'''<div class="overview" id="overview">
  <p class="topic-label"><span class="star">✦</span> {L["overview"]}</p>
  {render_blocks(doc["overview"], letters)}
</div>''')

    for i, t in enumerate(doc["topics"]):
        tid = f"topic-{'ab'[i] if i < 2 else i + 1}"
        label = f"Event {i + 1}" if t.get("unit") == "Event" else L["topic"](i)
        toc.append(f'<li><a href="#{tid}">{label} · {esc(short(t["title"]))}</a></li>')
        secs = []
        for j, s in enumerate(t["sections"]):
            sid = f"{tid[-1]}-{j + 1}"
            toc.append(f'<li class="sub"><a href="#{sid}">{esc(s["title"])}</a></li>')
            secs.append(f'<h3 id="{sid}"><span class="n">{j + 1}.</span> {esc(s["title"])}</h3>\n'
                        + render_blocks(s["blocks"], letters))
        body.append(f'''<div class="topic-block" id="{tid}">
  <p class="topic-label"><span class="star">✦</span> {label}</p>
  <h2>{esc(t["title"])}</h2>
{chr(10).join(secs)}
</div>''')

    if doc["conclusion"]:
        toc.append(f'<li><a href="#conclusion">{L["conclusion"]}</a></li>')
        body.append(f'''<div class="callout" id="conclusion">
  <strong>{L["conclusion"]}</strong>
  {render_blocks(doc["conclusion"], letters)}
</div>''')

    lang = ' lang="ar" dir="rtl"' if arabic else ""
    return f'''<div class="guide-layout"{lang}>

  <nav class="toc" aria-label="{L["toc"]}">
    <p class="eyebrow">{L["toc"]}</p>
    <ol>
      {chr(10).join("      " + x for x in toc).strip()}
    </ol>
  </nav>

  <article class="guide">
{chr(10).join(body)}
  </article>
</div>
'''


def main():
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(1)
    src, slug = sys.argv[1], sys.argv[2]
    paras = read_text(src) if src.lower().endswith((".txt", ".md")) else read_paragraphs(src)
    arabic = is_arabic(paras)
    doc = parse(paras)
    out = os.path.join(ROOT, "content", f"{slug}.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(render(doc, arabic))
    n_sec = [len(t["sections"]) for t in doc["topics"]]
    print(f"{slug}: {'Arabic' if arabic else 'English'} · overview {len(doc['overview'])} blocks · "
          f"{len(doc['topics'])} topics, sections {n_sec}"
          + (" · conclusion" if doc["conclusion"] else ""))


if __name__ == "__main__":
    main()
