"""Link-preview images for shared calls: one 1200x630 PNG per decision.

iMessage, WhatsApp and Android show a large preview when a page names a large
og:image. GitHub Pages is static, so a shared link points at app/<call>/ (a tiny
page with that call's image) and the page forwards to the app.

Run:  py build/og_images.py      Out: app/og/<call>.png, app/<call>/index.html
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
.k{{color:#aab4bf;font-size:44px;letter-spacing:.18em}}.k b{{color:#3ccf7e}}
.c{{color:{color};font-size:{size}px;line-height:1;letter-spacing:.02em;margin-top:18px;text-align:center}}
.bar{{width:160px;height:8px;background:{color};border-radius:4px;margin-top:40px}}</style></head>
<body><div class="k">FOURTH <b>DOWN</b> ENGINE SAYS</div><div class="c">{text}</div><div class="bar"></div></body></html>"""
PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{text}</title>
<meta property="og:title" content="{text}">
<meta property="og:description" content="Fourth Down Engine">
<meta property="og:type" content="website">
<meta property="og:image" content="{site}og/{slug}.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>location.replace("../" + location.search);</script>
</head><body style="background:#06080a"><a href="../">Open the Fourth Down Engine</a></body></html>
"""


def main():
    tmp = tempfile.mkdtemp()
    for slug, (text, color) in CALLS.items():
        html = os.path.join(tmp, slug + ".html")
        size = 230 if len(text) <= 9 else 150
        open(html, "w", encoding="utf-8").write(CARD.format(text=text, color=color, size=size))
        out = os.path.join(ROOT, "app", "og", slug + ".png")
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={tmp}\prof",
                        "--window-size=1200,630", "--virtual-time-budget=4000", f"--screenshot={out}", html],
                       check=True, capture_output=True)
        os.makedirs(os.path.join(ROOT, "app", slug), exist_ok=True)
        open(os.path.join(ROOT, "app", slug, "index.html"), "w", encoding="utf-8", newline="\n").write(
            PAGE.format(text=text, site=SITE, slug=slug))
        print("wrote", slug)


if __name__ == "__main__":
    main()
