"""Make the phone-ready copy of the app for publishing as a private Claude artifact.

Run:  py build/publish_artifact.py
Out:  build/artifact/  (gitignored): index.html plus the scripts it loads.

The artifact host adds the page wrapper (doctype, head, body) itself, so this copy
drops them. Links that only work inside the project folder are removed.
"""
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build", "artifact")


def main():
    os.makedirs(OUT, exist_ok=True)
    t = open(os.path.join(ROOT, "app", "index.html"), encoding="utf-8").read()
    t = re.sub(r"<!doctype html>\s*", "", t, flags=re.I)
    t = re.sub(r"</?html[^>]*>\s*|</?head>\s*|</?body>\s*", "", t)
    t = re.sub(r'<meta charset="utf-8">\s*', "", t)
    t = re.sub(r'<meta name="viewport"[^>]*>\s*', "", t)
    t = re.sub(r'<link rel="icon"[^>]*>\s*', "", t)
    # project-folder links do not exist on the web
    t = re.sub(r"<p>Full method, results and sources:.*?</p>",
               "<p>Full method, results and sources are in the white paper in the project folder.</p>", t, flags=re.S)
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8", newline="\n").write(t)
    for f in ("model.js", "engine.js", "grades.js", "bootstrap.js"):
        shutil.copy(os.path.join(ROOT, "app", f), os.path.join(OUT, f))
    print("wrote", os.path.relpath(OUT, ROOT))


if __name__ == "__main__":
    main()
