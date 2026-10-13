"""Link-preview images for shared calls: one 1200x630 PNG per decision.

iMessage, WhatsApp and Android show a large preview when a page names a large
og:image. GitHub Pages is static, so a shared link points at app/s/<call>-<yards to go>/
(a tiny page with that image) and the page forwards to the app.

Run:  py build/og_images.py      Out: app/og/<slug>.png, app/s/<slug>/index.html
Needs Microsoft Edge (headless) for the PNGs.
"""
import os
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://willhoop.github.io/fourth-down/"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CALLS = {  # slug: (headline, color)
    "go": ("GO FOR IT", "#3ccf7e"),
    "fg": ("KICK THE FIELD GOAL", "#f2b441"),
    "punt": ("PUNT IT", "#5aa2f0"),
    "tossup": ("TOSS-UP", "#aab4bf"),
}
CARD = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700&display=swap" rel="stylesheet">
<style>html,body{{margin:0;width:1200px;height:630px;background:#06080a;overflow:hidden}}
body{{display:flex;flex-direction:column;justify-content:center;align-items:center;font-family:"Barlow Condensed",sans-serif}}
.k{{color:#aab4bf;font-size:38px;letter-spacing:.18em;margin-top:34px}}.k b{{color:#3ccf7e}}
.d{{color:#f4f6f8;font-size:120px;line-height:1;letter-spacing:.03em}}
.c{{color:{color};font-size:{size}px;line-height:1;letter-spacing:.02em;margin-top:18px;text-align:center}}
</style></head>
<body>{dd}<div class="c">{text}</div><div class="k">FOURTH <b>DOWN</b> ENGINE</div></body></html>"""
PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{text}</title>
<meta property="og:title" content="{text}">
<meta property="og:description" content="Fourth Down Engine">
<meta property="og:type" content="website">
<meta property="og:image" content="{site}og/{slug}.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>location.replace("{up}" + location.search);</script>
</head><body style="background:#06080a"><a href="{up}">Open the Fourth Down Engine</a></body></html>
"""


TOGO = [str(n) for n in range(1, 16)] + ["long"]       # 4th & 1 ... 4th & 15, then "long" (16+)


def cards():
    """(slug, down-and-distance line or "", call text, color). A slug with a
    distance is "<call>-<togo>"; the plain slug is for early downs."""
    for slug, (text, color) in CALLS.items():
        yield slug, "", text, color
        for d in TOGO:
            yield f"{slug}-{d}", f"4TH &amp; {d.upper()}", text, color


def main():
    tmp = tempfile.mkdtemp()
    pairs = []
    os.makedirs(os.path.join(ROOT, "app", "og"), exist_ok=True)
    for slug, dd, text, color in cards():
        html = os.path.join(tmp, slug + ".html")
        size = (230 if len(text) <= 9 else 150) if not dd else (190 if len(text) <= 9 else 120)
        open(html, "w", encoding="utf-8").write(CARD.format(text=text, color=color, size=size,
                                                            dd=f'<div class="d">{dd}</div>' if dd else ""))
        pairs += [html, os.path.join(ROOT, "app", "og", slug + ".png")]
        page_dir = os.path.join(ROOT, "app", "s", slug)
        os.makedirs(page_dir, exist_ok=True)
        title = (dd.replace("&amp;", "&").title().replace("Th &", "th &") + ": " if dd else "") + text
        open(os.path.join(page_dir, "index.html"), "w", encoding="utf-8", newline=chr(10)).write(
            PAGE.format(text=title, site=SITE, slug=slug, up="../../"))
    edge = subprocess.Popen([EDGE, "--headless=new", "--remote-debugging-port=9351",
                             "--user-data-dir=" + os.path.join(tmp, "prof"), "about:blank"])
    try:
        subprocess.run(["node", os.path.join(ROOT, "build", "og_shot.mjs"), "9351", *pairs], check=True, timeout=600)
    finally:
        edge.kill()
    print("wrote", len(pairs) // 2, "cards")


if __name__ == "__main__":
    main()
