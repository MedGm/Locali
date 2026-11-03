"""Export docs/diagrams/*.excalidraw to SVG with Excalidraw's own exportToSvg, in headless Chrome.

    uv run python docs/diagrams/export.py [name ...]

Needs Google Chrome and network access (the Excalidraw package is loaded from esm.sh). The SVG
embeds the hand-drawn font, so it looks the same on GitHub as on excalidraw.com.
"""

import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
EXCALIDRAW = "https://esm.sh/@excalidraw/excalidraw@0.18.0"

PAGE = """<!doctype html><meta charset="utf-8"><pre id="out">pending</pre>
<script type="module">
const out = document.getElementById("out");
try {
  const { exportToSvg } = await import("%s");
  const scene = %s;
  const svg = await exportToSvg({
    elements: scene.elements,
    appState: { ...scene.appState, exportBackground: true, exportWithDarkMode: false, exportPadding: 24 },
    files: scene.files || {},
  });
  out.textContent = "SVG:" + svg.outerHTML;
} catch (e) {
  out.textContent = "ERROR:" + e + "\\n" + (e.stack || "");
}
</script>
"""


def export(name: str, attempts: int = 3) -> None:
    for attempt in range(1, attempts + 1):
        result = render(name)
        if result.startswith("SVG:"):
            (HERE / f"{name}.svg").write_text(result[4:])
            print(f"wrote {name}.svg ({len(result) // 1024} KB)")
            return
        print(f"{name}: attempt {attempt} failed: {result[:300]}")
    sys.exit(f"{name}: export failed")


def render(name: str) -> str:
    scene = json.loads((HERE / f"{name}.excalidraw").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "export.html"
        page.write_text(PAGE % (EXCALIDRAW, json.dumps(scene)))
        dom = subprocess.run(
            ["google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={tmp}/profile",
             "--virtual-time-budget=120000", "--dump-dom", page.as_uri()],
            capture_output=True, text=True, timeout=180, check=False).stdout
    match = re.search(r'<pre id="out">(.*?)</pre>', dom, re.DOTALL)
    return html.unescape(match.group(1)) if match else "ERROR: no output"


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(p.stem for p in HERE.glob("*.excalidraw"))
    for n in names:
        export(n)
