#!/usr/bin/env python3
"""
Mashrek MUN '26 — static site builder.

Reads config.json (+ optional study-guide pages in content/<slug>.html) and
writes every page of the site as plain, static HTML into this folder.

    python3 build.py

No dependencies beyond Python 3.8+. Re-run after every edit to config.json
or content/, then upload the folder to your host.
"""
import hashlib
import json
import os
import re
from datetime import date
from html import escape as _esc

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_config():
    """Load config.json with a plain-English error instead of a Python traceback."""
    path = os.path.join(ROOT, "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        raise SystemExit(f"\nconfig.json has a formatting mistake on line {e.lineno}, column {e.colno}: {e.msg}.\n"
                         "Check for a missing comma, quote or bracket around that spot.\n")
    problems = []
    for key in ("name", "full_name", "year", "short", "theme", "description", "contact", "committees"):
        if key not in cfg:
            problems.append(f'missing "{key}"')
    for i, a in enumerate(cfg.get("applications") or []):
        if not isinstance(a, dict) or not a.get("title"):
            problems.append(f"applications item {i + 1} needs a \"title\"")
        elif a.get("url") and not str(a["url"]).startswith(("https://", "http://")):
            problems.append(f'applications item {i + 1}: "url" must start with https://')
    for i, d in enumerate(cfg.get("schedule") or []):
        if not isinstance(d, dict) or not d.get("day") or not isinstance(d.get("events", []), list):
            problems.append(f'schedule item {i + 1} needs a "day" and an "events" list')
        else:
            for j, e in enumerate(d.get("events", [])):
                if not isinstance(e, dict) or not e.get("title"):
                    problems.append(f'schedule item {i + 1}, event {j + 1} needs a "title"')
    for i, c in enumerate(cfg.get("committees") or []):
        for key in ("slug", "abbr", "name", "level", "tier", "blurb"):
            if not isinstance(c, dict) or not c.get(key):
                problems.append(f'committee {i + 1} is missing "{key}"')
    if problems:
        raise SystemExit("\nconfig.json needs fixing:\n  - " + "\n  - ".join(problems) + "\n")
    return cfg


CFG = load_config()

SITE_URL = CFG.get("site_url", "").strip().rstrip("/")
C = CFG["committees"]
TIERS = ["Beginner", "Intermediate", "Expert", "Special"]
FONTS = ("https://fonts.googleapis.com/css2?family=Cormorant+SC:wght@600;700"
         "&family=EB+Garamond:ital,wght@0,400;0,500;0,600;0,700;1,400"
         "&family=Playfair+Display:ital,wght@0,400;0,700;0,800;0,900;1,400&display=swap")
STAR = '<span class="star" aria-hidden="true">✦</span>'


def esc(s):
    return _esc(str(s), quote=True)


def asset_version(path):
    with open(os.path.join(ROOT, path), "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]


CSS_V = asset_version("css/style.css")
JS_V = asset_version("js/site.js")


def content_for(slug):
    p = os.path.join(ROOT, "content", f"{slug}.html")
    return open(p, encoding="utf-8").read() if os.path.exists(p) else None


def has_guide(c):
    return bool(c.get("guide_url")) or content_for(c["slug"]) is not None


def abs_url(path):
    return f"{SITE_URL}/{path}" if SITE_URL else path


# ------------------------------------------------------------------ layout

INTRO = ("<script>try{if(!sessionStorage.getItem('mmun-intro')&&!matchMedia('(prefers-reduced-motion: reduce)').matches){"
         "var h=document.documentElement;h.classList.add('intro');sessionStorage.setItem('mmun-intro','1');"
         "var f=function(){h.classList.remove('intro')};setTimeout(f,1100);"
         "['pointerdown','keydown','wheel','touchstart'].forEach(function(e){addEventListener(e,f,{once:true,passive:true})})"
         "}}catch(e){}</script>")


def head(title, description, path, base=""):
    full_title = f"{title} | {CFG['name']} ’{CFG['year'][2:]}" if title else \
        f"{CFG['name']} ’{CFG['year'][2:]} | {CFG['theme']}"
    intro = INTRO if path == "index.html" else ""
    canonical = f'<link rel="canonical" href="{esc(abs_url(path))}">' if SITE_URL else ""
    og_url = f'<meta property="og:url" content="{esc(abs_url(path))}">' if SITE_URL else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="color-scheme" content="light">
  <title>{esc(full_title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta name="theme-color" content="#0c1830">
  {canonical}
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{esc(CFG['full_name'])} {esc(CFG['year'])}">
  <meta property="og:title" content="{esc(full_title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:image" content="{esc(abs_url('assets/og-image.jpg') if SITE_URL else base + 'assets/og-image.jpg')}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  {og_url}
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" type="image/png" sizes="32x32" href="{base}assets/favicon-32.png">
  <link rel="icon" type="image/png" sizes="64x64" href="{base}assets/favicon-64.png">
  <link rel="apple-touch-icon" href="{base}assets/apple-touch-icon.png">
  <link rel="manifest" href="{base}site.webmanifest">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="{FONTS}" rel="stylesheet">
  <link rel="stylesheet" href="{base}css/style.css?v={CSS_V}">
  <script>document.documentElement.classList.add('js')</script>{intro}
</head>
"""


def header(active, base=""):
    rows, prev = [], None
    for c in C:
        if prev and prev["tier"] != c["tier"]:
            rows.append('<div class="divider" role="presentation"></div>')
        cur = ' class="active" aria-current="page"' if active == c["slug"] else ""
        rows.append(f'<a href="{base}{c["slug"]}.html"{cur}><span>{esc(c["name"])}</span>'
                    f'<span class="lvl">{esc(c["level"])}</span></a>')
        prev = c
    in_committee = any(c["slug"] == active for c in C)

    def link(href, label, key):
        cur = ' active" aria-current="page' if active == key else ""
        return f'<li><a class="nav-link{cur}" href="{base}{href}">{label}</a></li>'

    return f"""<body data-page="{esc(active)}">
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="{base}index.html" aria-label="{esc(CFG['name'])} home">
      <img src="{base}assets/logo-192.png" alt="" width="52" height="52">
      <span class="brand-text" translate="no"><strong>{esc(CFG['name'])}</strong><small>{esc(CFG['short'])}</small></span>
    </a>
    <button class="menu-btn" type="button" aria-label="Menu" aria-expanded="false" aria-controls="nav">
      <span></span><span></span><span></span>
    </button>
    <nav class="nav" id="nav" aria-label="Main">
      <ul class="nav-list">
        {link("index.html", "Home", "home")}
        <li class="has-dropdown">
          <button class="nav-toggle{' active' if in_committee else ''}" type="button" aria-expanded="false" aria-controls="committee-menu">
            Committees <span class="caret" aria-hidden="true">▾</span>
          </button>
          <div class="dropdown" id="committee-menu">{''.join(rows)}</div>
        </li>
        {link("applications.html", "Applications", "applications")}
        {link("guides.html", "Guides", "guides")}
        {link("schedule.html", "Schedule", "schedule")}
      </ul>
    </nav>
  </div>
</header>
"""


def contact_line(label, value, href=None):
    if not value:
        return ""
    if href:
        ext = ' target="_blank" rel="noopener"' if href.startswith("http") else ""
        v = f'<a href="{esc(href)}"{ext}>{esc(value)}</a>'
    else:
        v = f"<strong>{esc(value)}</strong>"
    return f'<div class="contact-line"><span>{label}</span>{v}</div>'


def footer(base=""):
    ct = CFG["contact"]
    ig = ct.get("instagram", "").lstrip("@").strip()
    lines = "".join([
        contact_line("Email", ct.get("email"), f"mailto:{ct.get('email')}"),
        contact_line("Instagram", f"@{ig}" if ig else "", f"https://www.instagram.com/{ig}/"),
        contact_line("Phone", ct.get("phone"), "tel:" + ct.get("phone", "").replace(" ", "")),
    ])
    venues = ct.get("location") or []
    if isinstance(venues, str):
        venues = [venues]
    if venues:
        lines += ('<div class="contact-line"><span>Venue</span>'
                  + "".join(f"<strong>{esc(v)}</strong>" for v in venues) + "</div>")
    cr = CFG.get("credit") or {}
    credit = ""
    if cr.get("name"):
        who = (f'<a href="{esc(cr["url"])}" target="_blank" rel="noopener" translate="no">{esc(cr["name"])}</a>'
               if cr.get("url") else f'<span translate="no">{esc(cr["name"])}</span>')
        credit = f'<p class="site-credit">Website by {who}</p>'
    ig_btn = (f'<a class="ig-btn" href="https://www.instagram.com/{esc(ig)}/" target="_blank" rel="noopener">'
              f'<img src="https://cdn.simpleicons.org/instagram/ffffff" alt="" width="18" height="18" loading="lazy">'
              f'Follow @{esc(ig)}</a>') if ig else ""
    if not (ct.get("email") or ig or ct.get("phone")):
        lines += '<p class="footer-note">Email and social channels will be announced shortly.</p>'
    return f"""
<footer class="site-footer" id="contact">
  <div class="wrap">
    <div class="footer-grid">
      <div class="footer-brand">
        <img src="{base}assets/logo-192.png" alt="" width="56" height="56" loading="lazy">
        <div>
          <strong translate="no">{esc(CFG['name'])} ’{esc(CFG['year'][2:])}</strong>
          <span>{esc(CFG['theme'])}</span>
        </div>
        {ig_btn}
      </div>
      <div>
        <h3>Contact us</h3>
        {lines}
      </div>
      <div>
        <h3>Explore</h3>
        <ul>
          <li><a href="{base}index.html#committees">Committees</a></li>
          <li><a href="{base}applications.html">Applications</a></li>
          <li><a href="{base}guides.html">Study guides</a></li>
          <li><a href="{base}schedule.html">Schedule</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <span>© {esc(CFG['year'])} {esc(CFG['full_name'])}</span>
    </div>
    {credit}
  </div>
</footer>
<a class="to-top" href="#main" aria-label="Back to top"><span aria-hidden="true">↑</span></a>
<script src="{base}js/site.js?v={JS_V}" defer></script>
</body>
</html>
"""


def page(filename, title, description, active, main_html, extra_head=""):
    html = head(title, description, filename).replace("</head>", extra_head + "</head>") \
        + header(active) + f'<main id="main">\n{main_html}\n</main>\n' + footer()
    with open(os.path.join(ROOT, filename), "w", encoding="utf-8") as f:
        f.write(html)
    return filename


def page_head(eyebrow, h1, lede, badges="", seal=True):
    seal_html = '<img class="seal" src="assets/logo-192.png" alt="" width="88" height="88">' if seal else ""
    badges_html = f'<div class="badges">{badges}</div>' if badges else ""
    return f"""<header class="page-head band">
  <canvas class="hero-canvas" aria-hidden="true"></canvas>
  <button class="motion-toggle" type="button" aria-pressed="false" title="Pause motion"><span class="icon" aria-hidden="true">❚❚</span><span class="label sr-only">Pause motion</span></button>
  <div class="wrap">
    {seal_html}
    <p class="eyebrow">{eyebrow}</p>
    <h1 class="split">{h1}</h1>
    <p class="lede">{lede}</p>
    {badges_html}
  </div>
</header>
<hr class="rule">"""


def pending(eyebrow, title, body, buttons=""):
    return f"""<div class="pending reveal">
  <p class="eyebrow">{eyebrow}</p>
  <h2>{title}</h2>
  {body}
  {f'<div class="btn-row">{buttons}</div>' if buttons else ''}
</div>"""


# ------------------------------------------------------------------ pages

def build_home():
    open_apps = [a for a in CFG["applications"] if a.get("url")]
    released = sum(1 for c in C if has_guide(c))
    venues = CFG["contact"].get("location") or []
    if isinstance(venues, str):
        venues = [venues]

    rows = "".join(f"""<li><a class="c-row" href="{c['slug']}.html">
      <span class="c-abbr">{esc(c['abbr'])}</span>
      <span class="c-name">{esc(c['name'])}</span>
      <span class="c-level">{esc(c['level'])}</span>
      <span class="c-go" aria-hidden="true">→</span>
    </a></li>""" for c in C)

    facts = "".join(
        f"<li><b>{esc(v.split(':', 1)[0].strip())}</b>{esc(v.split(':', 1)[1].strip()) if ':' in v else ''}</li>"
        for v in venues)
    facts += (f"<li><b>Delegates</b>{'Applications open' if open_apps else 'Applications opening soon'}</li>")

    phrases = [("The Narratives of Power", ""), ("Behind every headline is a choice", "m"),
               ("Question who holds the pen", ""), ("Power decides what the world sees", "m")]
    one = "".join(f'<span class="{c}">{esc(t)}</span><i>✦</i>' for t, c in phrases)
    marquee = f'<div class="marquee" aria-hidden="true"><div class="marquee-track">{one}{one}</div></div>'

    film = ""
    if CFG.get("theme_video"):
        film = f"""
<section class="film" id="film" aria-labelledby="film-title">
  <div class="wrap">
    <div class="film-head reveal">
      <p class="eyebrow"><span class="live-dot" aria-hidden="true"></span> Now Showing</p>
      <h2 class="split" id="film-title">The Theme Reveal</h2>
    </div>
    <figure class="film-frame unveil">
      <div class="film-screen">
        <video muted loop playsinline controls preload="metadata" poster="{esc(CFG.get('theme_video_poster', ''))}"
               aria-label="{esc(CFG['short'])} theme film: The Narratives of Power" aria-describedby="film-desc">
          <source src="{esc(CFG['theme_video'])}" type="video/mp4">
          Your browser can’t play this video. <a href="{esc(CFG['theme_video'])}">Download it instead</a>.
        </video>
        <div class="film-bar">
          <button class="film-btn film-sound" type="button" aria-pressed="false"><span class="lbl">Turn On Sound</span></button>
          <button class="film-btn film-pause" type="button" aria-pressed="false"><span class="ic" aria-hidden="true">❚❚</span> <span class="lbl">Pause</span></button>
        </div>
      </div>
      <figcaption id="film-desc">A montage of real news footage about journalists, protest and free speech, ending on the {esc(CFG['short'])} theme. Contains scenes of conflict and grief.</figcaption>
    </figure>
  </div>
</section>
"""

    jsonld = ""
    if SITE_URL:
        jsonld = ('<script type="application/ld+json">' + json.dumps({
            "@context": "https://schema.org", "@type": "Organization",
            "name": f"{CFG['full_name']} {CFG['year']}", "alternateName": CFG["short"],
            "url": SITE_URL + "/", "logo": abs_url("assets/logo.png"),
        }, ensure_ascii=False) + "</script>\n")

    topics = 2 * len(C)
    main = f"""
<section class="hero" aria-labelledby="hero-title">
  <div class="hero-photos" aria-hidden="true">
    <img src="assets/photos/hero-session.jpg" alt="" width="1280" height="853" decoding="async">
    <img src="assets/photos/hero-celebration.jpg" alt="" width="1280" height="853" decoding="async" fetchpriority="low">
    <img src="assets/photos/hero-drafting.jpg" alt="" width="1280" height="960" decoding="async" fetchpriority="low">
  </div>
  <canvas class="hero-canvas" aria-hidden="true"></canvas>
  <div class="hero-grain" aria-hidden="true"></div>
  <div class="wrap hero-inner" data-parallax>
    <img class="hero-logo" src="assets/logo.png" alt="{esc(CFG['short'])} logo" width="240" height="240" fetchpriority="high">
    <p class="presents">{esc(CFG['full_name'])} · {esc(CFG['year'])}</p>
    <h1 id="hero-title" class="split"><span class="the">The</span> Narratives<br>of Power</h1>
    <p class="deck">Behind every headline is a choice.</p>
    <div class="btn-row">
      <a class="btn light" href="applications.html">Delegate Applications <span class="arr" aria-hidden="true">→</span></a>
      <a class="btn ghost light" href="#committees">Committees</a>
    </div>
  </div>
  <div class="hero-facts"><ul>{facts}</ul></div>
  <button class="motion-toggle" type="button" aria-pressed="false" title="Pause motion"><span class="icon" aria-hidden="true">❚❚</span><span class="label sr-only">Pause motion</span></button>
</section>

<section class="glance" aria-label="At a glance">
  <div class="wrap">
    <div class="glance-grid" data-stagger>
      <div class="glance-item"><span class="num" data-count="3">3</span><span class="lbl">Conference days</span><p>The full programme will be announced on the Schedule page.</p></div>
      <div class="glance-item"><span class="num" data-count="{len(C)}">{len(C)}</span><span class="lbl">Committees</span><p>From Beginner to Expert, plus the Global Press Council.</p></div>
      <div class="glance-item"><span class="num" data-count="{topics}">{topics}</span><span class="lbl">Topics &amp; events</span><p>Two per committee, each with a study guide online.</p></div>
      <div class="glance-item"><span class="num" data-count="{len(venues)}">{len(venues)}</span><span class="lbl">Venues</span><p>{' and '.join(esc(v.split(':', 1)[-1].strip()) for v in venues)}.</p></div>
    </div>
  </div>
</section>
{film}
<section class="theme" id="theme">
  <div class="wrap">
    <div class="theme-head reveal"><p class="eyebrow">The Official Theme</p></div>
    <div class="theme-grid">
      <article class="reveal">
        <h2 class="headline"><em>The</em>Narratives of Power</h2>
        <p class="standfirst">Behind every headline is a choice. Behind every choice is power.</p>
        <div class="columns">
          <p>From the stories amplified to the voices silenced, power shapes the narrative — and the narrative shapes the world.</p>
          <p>At Mashrek MUN 2026, we challenge you to look deeper, think critically, and question who holds the pen.</p>
        </div>
      </article>
      <aside class="reveal">
        <div class="sidebar-box">Power decides what the world sees.</div>
        <p class="caption">In a world filled with noise, not every voice is heard. At Mashrek MUN 2026, we amplify ideas that matter and empower leaders who will rewrite tomorrow.</p>
        <figure class="pull-quote">
          <span class="mark" aria-hidden="true">“</span>
          <blockquote>The pen may be mightier than the sword, but only if it’s in the hands of those brave enough to use it.</blockquote>
          <cite>Mashrek MUN 2026</cite>
        </figure>
      </aside>
    </div>
  </div>
</section>

<section class="gallery" aria-labelledby="gallery-title">
  <div class="wrap">
    <h2 class="split gallery-title" id="gallery-title">Life at Mashrek MUN</h2>
    <div class="gallery-grid" data-stagger>
      <figure class="g-item g-main">
        <button class="g-open" type="button" aria-label="View larger: A delegate stands to speak during a committee session, national flags lined up along the table"><img src="assets/photos/session-1600.jpg" srcset="assets/photos/session-900.jpg 900w, assets/photos/session-1600.jpg 1600w"
             sizes="(max-width: 800px) 100vw, 60vw" width="1600" height="1067" loading="lazy"
             alt="A delegate stands to speak during a committee session, national flags lined up along the table"></button>
        <figcaption>In session</figcaption>
      </figure>
      <figure class="g-item">
        <button class="g-open" type="button" aria-label="View larger: Delegates working together on laptops, drafting a resolution"><img src="assets/photos/drafting-1600.jpg" srcset="assets/photos/drafting-900.jpg 900w, assets/photos/drafting-1600.jpg 1600w"
             sizes="(max-width: 800px) 100vw, 40vw" width="1600" height="1200" loading="lazy"
             alt="Delegates working together on laptops, drafting a resolution"></button>
        <figcaption>Drafting resolutions</figcaption>
      </figure>
      <figure class="g-item">
        <button class="g-open" type="button" aria-label="View larger: Delegates cheering and applauding together in a ballroom"><img src="assets/photos/celebration-1600.jpg" srcset="assets/photos/celebration-900.jpg 900w, assets/photos/celebration-1600.jpg 1600w"
             sizes="(max-width: 800px) 100vw, 40vw" width="1600" height="1067" loading="lazy"
             alt="Delegates cheering and applauding together in a ballroom"></button>
        <figcaption>Celebrating together</figcaption>
      </figure>
    </div>
  </div>
</section>

{marquee}

<section class="committees-home" id="committees">
  <div class="wrap narrow">
    <div class="section-head center reveal">
      <h2 class="split">Choose your room.</h2>
    </div>
    <ul class="c-list" data-stagger>{rows}</ul>
    <p class="c-foot reveal"><a href="guides.html">{released} of {len(C)} study guides released →</a></p>
  </div>
</section>

<section class="cta">
  <div class="wrap narrow reveal">
    <h2 class="split">{'Delegate applications are open.' if open_apps else 'Delegate applications open soon.'}</h2>
    <div class="btn-row">
      <a class="btn light" href="applications.html">Delegate Applications <span class="arr" aria-hidden="true">→</span></a>
      <a class="btn ghost light" href="schedule.html">Schedule</a>
    </div>
  </div>
</section>"""
    page("index.html", "", CFG["description"], "home", main, jsonld)


def build_committee(c):
    content = content_for(c["slug"])
    badges = []
    if content:
        words = len(re.sub(r"<[^>]+>", " ", content).split())
        minutes = max(1, round(words / 200))
        badges.append(f'<span class="status solid">Study guide · {minutes} min read</span>')
        if 'lang="ar"' in content:
            badges.append('<span class="status" lang="ar">الدليل باللغة العربية</span>')
        badges.append('<button class="status print-btn" type="button" data-print hidden>Save as PDF</button>')
    if c.get("guide_url"):
        badges.append(f'<a class="status solid" href="{esc(c["guide_url"])}" target="_blank" rel="noopener">Download guide ↓</a>')
    if not badges:
        badges.append('<span class="status">Study guide · Coming soon</span>')

    top = page_head(f"{esc(c['abbr'])} · {esc(c['level'])}", esc(c["name"]), esc(c["blurb"]), "".join(badges))
    i = C.index(c)
    prev_c, next_c = C[i - 1] if i > 0 else None, C[i + 1] if i + 1 < len(C) else None
    pager = '<nav class="pager" aria-label="Other committees"><div class="wrap">'
    pager += (f'<a class="pager-link prev" href="{prev_c["slug"]}.html"><span class="dir">← Previous committee</span>'
              f'<span class="nm">{esc(prev_c["name"])}</span></a>') if prev_c else '<span></span>'
    pager += (f'<a class="pager-link next" href="{next_c["slug"]}.html"><span class="dir">Next committee →</span>'
              f'<span class="nm">{esc(next_c["name"])}</span></a>') if next_c else '<span></span>'
    pager += '</div></nav>'
    if content:
        body = f'<div class="wrap">\n{content}\n</div>'
    else:
        dl = (f'<a class="btn" href="{esc(c["guide_url"])}" target="_blank" rel="noopener">Download study guide</a>'
              if c.get("guide_url") else '<a class="btn" href="applications.html">Applications</a>')
        body = f"""<section>
  <div class="wrap narrow">
    {pending("Topics &amp; Study Guide",
             "Available to download" if c.get("guide_url") else "To be released",
             f'<p>The topics and background guide for the {esc(c["name"])} will be published here as soon as they are finalised by the chairs.</p>'
             '<p>In the meantime, start researching the committee’s mandate and your country’s foreign policy.</p>'
             if not c.get("guide_url") else
             f'<p>The study guide for the {esc(c["name"])} is ready. Read it carefully before conference.</p>',
             dl + '<a class="btn ghost" href="guides.html">All guides</a>')}
  </div>
</section>"""
    extra = ""
    if content and 'lang="ar"' in content:
        extra = ('  <link href="https://fonts.googleapis.com/css2?family=Amiri:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">\n')
    desc = f"{c['name']} ({c['level']}) at {CFG['full_name']} {CFG['year']}. {c['blurb']}"
    page(f"{c['slug']}.html", c["name"], desc, c["slug"], top + "\n" + body + "\n" + pager, extra)


def build_applications():
    apps = CFG["applications"]
    top = page_head("Take Part", "Applications",
                    "Every narrative needs its authors. Apply as a delegate and take up the pen.", seal=False)
    if apps:
        rows = []
        for a in apps:
            note = f'<span class="sub">{esc(a["note"])}</span>' if a.get("note") else ""
            deadline = f'<span class="status">Deadline · {esc(a["deadline"])}</span>' if a.get("deadline") else ""
            action = (f'<a class="btn" href="{esc(a["url"])}" target="_blank" rel="noopener">Apply <span aria-hidden="true">→</span></a>'
                      if a.get("url") else '<span class="status">Opening soon</span>')
            rows.append(f'<li><span class="title">{esc(a["title"])}{note}</span>'
                        f'<span class="actions">{deadline}{action}</span></li>')
        body = f'<ul class="link-list reveal">{"".join(rows)}</ul>'
    else:
        body = pending("Applications", "Opening soon",
                       "<p>The delegate application form will be posted here as soon as it is released.</p>"
                       "<p>Check back soon, or reach the team using the contact details below.</p>")
    page("applications.html", "Applications",
         f"Apply as a delegate to {CFG['full_name']} {CFG['year']}.",
         "applications", top + f'\n<section><div class="wrap narrow">{body}</div></section>')


def build_guides():
    rows = []
    for c in C:
        actions = []
        if content_for(c["slug"]):
            actions.append(f'<a class="btn ghost" href="{c["slug"]}.html">Read online <span aria-hidden="true">→</span></a>')
        if c.get("guide_url"):
            actions.append(f'<a class="btn" href="{esc(c["guide_url"])}" target="_blank" rel="noopener">Download <span aria-hidden="true">↓</span></a>')
        if not actions:
            actions.append('<span class="status">Coming soon</span>')
        rows.append(f'<li><span class="title"><a href="{c["slug"]}.html">{esc(c["name"])}</a>'
                    f'<span class="sub">{esc(c["abbr"])} · {esc(c["level"])}</span></span>'
                    f'<span class="actions">{"".join(actions)}</span></li>')
    top = page_head("Preparation", "Study Guides",
                    "Background guides for each committee, released as the chairs finalise them.", seal=False)
    page("guides.html", "Study Guides", f"Study guides for every committee at {CFG['full_name']} {CFG['year']}.",
         "guides", top + f'\n<section><div class="wrap narrow"><ul class="link-list reveal">{"".join(rows)}</ul></div></section>')


def build_schedule():
    sched = CFG.get("schedule") or []
    top = page_head("Programme", "MMUN Schedule",
                    "The official conference programme." if sched else
                    "The official conference programme is being prepared by the organising team.", seal=False)
    if sched:
        days = []
        for d in sched:
            evs = "".join(f'<li><span class="when">{esc(e.get("time", ""))}</span>'
                          f'<span><strong>{esc(e["title"])}</strong>'
                          f'{"<span class=sub>" + esc(e["place"]) + "</span>" if e.get("place") else ""}</span></li>'
                          for e in d.get("events", []))
            days.append(f'<div class="day reveal"><h2 class="day-title">{esc(d["day"])}</h2><ul class="timeline">{evs}</ul></div>')
        body = "".join(days)
    else:
        body = pending("Schedule", "To be announced",
                       "<p>Opening ceremony, committee sessions and closing ceremony times will be posted here once the schedule is finalised.</p>")
    page("schedule.html", "Schedule", f"Conference schedule for {CFG['full_name']} {CFG['year']}.",
         "schedule", top + f'\n<section><div class="wrap narrow">{body}</div></section>')


def build_404():
    main = f"""<section class="page-head" style="padding-bottom:var(--space)">
  <div class="wrap">
    <img class="seal" src="assets/logo-192.png" alt="" width="88" height="88">
    <p class="eyebrow">Error 404</p>
    <h1>This story was never printed.</h1>
    <p class="lede">The page you’re looking for doesn’t exist or has moved.</p>
    <div class="btn-row" style="margin-top:36px">
      <a class="btn light" href="index.html">Back to home</a>
      <a class="btn ghost light" href="index.html#committees">Committees</a>
    </div>
  </div>
</section>"""
    html = head("Page not found", CFG["description"], "404.html") \
        .replace('<meta name="viewport"', '<meta name="robots" content="noindex">\n  <meta name="viewport"')
    # Hosts serve 404.html at any URL depth, so resolve relative links from the site root.
    html = html.replace("<head>", f'<head>\n  <base href="{SITE_URL + "/" if SITE_URL else "/"}">', 1)
    html += header("") + f'<main id="main">\n{main}\n</main>\n' + footer()
    open(os.path.join(ROOT, "404.html"), "w", encoding="utf-8").write(html)


def build_meta_files():
    pages = ["index.html"] + [f'{c["slug"]}.html' for c in C] + ["applications.html", "guides.html", "schedule.html"]
    robots = "User-agent: *\nAllow: /\n"
    if SITE_URL:
        today = date.today().isoformat()
        urls = "".join(f"  <url><loc>{esc(abs_url('' if p == 'index.html' else p))}</loc><lastmod>{today}</lastmod></url>\n"
                       for p in pages)
        open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
        robots += f"\nSitemap: {SITE_URL}/sitemap.xml\n"
    elif os.path.exists(os.path.join(ROOT, "sitemap.xml")):
        os.remove(os.path.join(ROOT, "sitemap.xml"))
    open(os.path.join(ROOT, "robots.txt"), "w").write(robots)

    manifest = {
        "name": f"{CFG['full_name']} {CFG['year']}", "short_name": CFG["short"],
        "icons": [{"src": "assets/logo-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "assets/logo.png", "sizes": "512x512", "type": "image/png"}],
        "theme_color": "#0c1830", "background_color": "#ffffff", "display": "browser", "start_url": "index.html",
    }
    json.dump(manifest, open(os.path.join(ROOT, "site.webmanifest"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    build_home()
    for c in C:
        build_committee(c)
    build_applications()
    build_guides()
    build_schedule()
    build_404()
    build_meta_files()
    print(f"Built {len(C) + 5} pages" + ("" if SITE_URL else "  (tip: set site_url in config.json once you have a domain)"))
