"""Build the README diagrams as Excalidraw files (docs/diagrams/*.excalidraw).

    uv run python docs/diagrams/make_diagrams.py

Each diagram is a list of boxes and arrows below; the script writes plain Excalidraw JSON, which
opens on excalidraw.com (File > Open) for editing. export.py turns the files into the SVGs the
README shows.
"""

import json
import random
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path

OUT = Path(__file__).parent

# Excalidraw's own palette
COLORS = {
    "ui": "#a5d8ff",  # blue: what people use
    "core": "#d0bfff",  # violet: backend and agents
    "model": "#ffec99",  # yellow: the language model
    "guard": "#ffc9c9",  # red: security controls
    "tool": "#b2f2bb",  # green: deterministic tools
    "store": "#e9ecef",  # grey: storage and monitoring
    "none": "transparent",
}
STROKE = "#1e1e1e"
FONT = 5  # Excalifont, the hand-drawn font
SIZE = 18
rng = random.Random(7)


def base(kind: str, x: float, y: float, w: float, h: float, **extra) -> dict:
    return {
        "id": f"{kind}-{rng.randrange(10**9)}", "type": kind, "x": x, "y": y, "width": w, "height": h,
        "angle": 0, "strokeColor": STROKE, "backgroundColor": "transparent", "fillStyle": "solid",
        "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [],
        "frameId": None, "roundness": None, "seed": rng.randrange(2**31), "version": 1,
        "versionNonce": rng.randrange(2**31), "isDeleted": False, "boundElements": [], "updated": 1,
        "link": None, "locked": False, **extra,
    }


def text_size(text: str, size: int) -> tuple[float, float]:
    lines = text.split("\n")
    return max(len(line) for line in lines) * size * 0.55, len(lines) * size * 1.25


def text(content: str, x: float, y: float, size: int = SIZE, container: str | None = None,
         align: str = "center", color: str = STROKE) -> dict:
    w, h = text_size(content, size)
    return base("text", x, y, w, h, text=content, originalText=content, fontSize=size, fontFamily=FONT,
                textAlign=align, verticalAlign="middle", containerId=container, lineHeight=1.25,
                autoResize=True, strokeColor=color)


@dataclass
class Diagram:
    elements: list[dict] = field(default_factory=list)
    boxes: dict[str, dict] = field(default_factory=dict)

    def box(self, key: str, label: str, x: float, y: float, w: float, h: float, color: str = "core",
            shape: str = "rectangle", dashed: bool = False, size: int = SIZE) -> None:
        b = base(shape, x, y, w, h, backgroundColor=COLORS[color],
                 roundness={"type": 3} if shape == "rectangle" else {"type": 2},
                 strokeStyle="dashed" if dashed else "solid")
        t = text(label, 0, 0, size, container=b["id"])
        t["x"], t["y"] = x + (w - t["width"]) / 2, y + (h - t["height"]) / 2
        b["boundElements"].append({"type": "text", "id": t["id"]})
        self.elements += [b, t]
        self.boxes[key] = b

    def label(self, content: str, x: float, y: float, size: int = SIZE, align: str = "left",
              color: str = STROKE) -> None:
        self.elements.append(text(content, x, y, size, align=align, color=color))

    def frame(self, label: str, x: float, y: float, w: float, h: float) -> None:
        """A dashed area with a title above its top-left corner, behind everything else."""
        self.elements.insert(0, base("rectangle", x, y, w, h, strokeStyle="dashed", strokeWidth=1,
                                     roundness={"type": 3}, strokeColor="#868e96"))
        self.elements.append(text(label, x + 12, y - 28, 16, align="left", color="#868e96"))

    def arrow(self, a: str, b: str, label: str = "", dashed: bool = False, sides: str = "",
              both: bool = False) -> None:
        """Arrow from box a to box b. sides is two letters (l, r, t, b) for the exit and entry
        sides; by default the one facing the other box."""
        A, B = self.boxes[a], self.boxes[b]
        if not sides:
            dx = B["x"] + B["width"] / 2 - A["x"] - A["width"] / 2
            dy = B["y"] + B["height"] / 2 - A["y"] - A["height"] / 2
            sides = ("rl" if dx > 0 else "lr") if abs(dx) > abs(dy) else ("bt" if dy > 0 else "tb")
        p, q = point(A, sides[0]), point(B, sides[1])
        points = [[0, 0], [q[0] - p[0], q[1] - p[1]]]
        arr = base("arrow", p[0], p[1], abs(points[1][0]), abs(points[1][1]), points=points,
                   roundness={"type": 2}, strokeStyle="dashed" if dashed else "solid",
                   startBinding={"elementId": A["id"], "focus": 0, "gap": 6},
                   endBinding={"elementId": B["id"], "focus": 0, "gap": 6},
                   startArrowhead="arrow" if both else None, endArrowhead="arrow",
                   lastCommittedPoint=None)
        A["boundElements"].append({"type": "arrow", "id": arr["id"]})
        B["boundElements"].append({"type": "arrow", "id": arr["id"]})
        self.elements.append(arr)
        if label:
            t = text(label, 0, 0, 15, container=arr["id"])
            t["x"] = p[0] + points[1][0] / 2 - t["width"] / 2
            t["y"] = p[1] + points[1][1] / 2 - t["height"] / 2
            arr["boundElements"].append({"type": "text", "id": t["id"]})
            self.elements.append(t)

    def save(self, name: str) -> None:
        doc = {"type": "excalidraw", "version": 2, "source": "https://excalidraw.com",
               "elements": self.elements,
               "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"}, "files": {}}
        (OUT / f"{name}.excalidraw").write_text(json.dumps(doc, indent=1))
        print(f"wrote {name}.excalidraw ({len(self.elements)} elements)")


def point(box: dict, side: str) -> tuple[float, float]:
    x, y, w, h = box["x"], box["y"], box["width"], box["height"]
    return {"l": (x, y + h / 2), "r": (x + w, y + h / 2), "t": (x + w / 2, y), "b": (x + w / 2, y + h)}[side]


def architecture() -> None:
    d = Diagram()
    d.label("Locali: system architecture", 40, 10, 28)

    d.box("dev", "Developer", 40, 150, 170, 80, "none", shape="ellipse")
    d.box("web", "Web app\nNext.js · React · TypeScript", 290, 140, 290, 100, "ui")
    d.box("api", "FastAPI backend\ntoken stays on the server", 660, 140, 260, 100, "core")
    d.box("wf", "LangGraph workflow\n9 fixed steps\n(the model has no tools)", 660, 330, 260, 120, "core")
    d.box("audit", "Audit log\nruns · approvals · refusals", 290, 340, 290, 100, "store")
    d.box("mlflow", "MLflow\nruns · traces · evaluations", 660, 560, 260, 80, "store")

    d.frame("used by the workflow", 1030, 70, 330, 600)
    d.box("model", "Model server\nllama.cpp on the laptop\nvLLM on Kaggle", 1060, 100, 270, 100, "model")
    d.box("tools", "Static tools\nRuff · Bandit · Radon\nSemgrep · secret scan", 1060, 240, 270, 100, "tool")
    d.box("sandbox", "Docker sandbox\npytest · no network\nread-only · limits", 1060, 380, 270, 100, "guard")
    d.box("patches", "Patch store\nvalidated, one patch\nper change", 1060, 530, 270, 100, "guard")

    d.box("gh", "GitHub Action\non pull requests", 1510, 240, 280, 100, "ui")
    d.box("mcp", "3 MCP servers\nrepository · tests · analysis\nfor other clients", 1510, 380, 280, 100, "tool", dashed=True)
    d.box("repo", "Repository\nnever written\nby a run", 1550, 520, 210, 120, "store", shape="ellipse")

    d.arrow("dev", "web")
    d.arrow("web", "api")
    d.arrow("api", "wf", "start a run")
    d.arrow("wf", "audit")
    d.arrow("wf", "model", "prompts", sides="rl")
    d.arrow("wf", "tools", sides="rl")
    d.arrow("wf", "sandbox", "tests", sides="rl")
    d.arrow("wf", "patches", "patches", sides="rl")
    d.arrow("wf", "mlflow")
    d.arrow("patches", "repo", "approve exact hash\napply · revert")
    d.arrow("gh", "tools", "changed files")
    d.arrow("mcp", "sandbox", dashed=True)
    d.save("architecture")


def legend(d: Diagram, x: float, y: float, items: list[tuple[str, str]]) -> None:
    for i, (color, label) in enumerate(items):
        d.elements.append(base("rectangle", x, y + i * 34, 26, 22, backgroundColor=COLORS[color],
                               roundness={"type": 3}, strokeWidth=1))
        d.label(label, x + 38, y + i * 34, 16)


def workflow() -> None:
    d = Diagram()
    d.label("One assistant run: 9 fixed steps (backend/agents/workflow.py)", 40, 10, 28)
    w, h, top, bottom = 240, 120, 100, 330
    xs = [40, 340, 640, 940, 1240]
    d.box("prepare", "1 - prepare\nisolated copy\nof the repository", xs[0], top, w, h, "core")
    d.box("analyze", "2 - analyze\nRuff · Bandit · Radon\nSemgrep · secrets", xs[1], top, w, h, "tool")
    d.box("review", "3 - review\nthe model reviews each\nfunction; a finding must\nquote a real line", xs[2], top, w, h, "model")
    d.box("testgen", "4 - testgen\ntests for untested\nfunctions, kept only\nif they pass", xs[3], top, w, h, "model")
    d.box("debug", "5 - debug\nfailing test + error\n→ the model fixes it\n(repair loop)", xs[4], top, w, h, "model")
    d.box("docs", "6 - docs\ndocstrings only,\nchecked on the\nsyntax tree", xs[4], bottom, w, h, "model")
    d.box("propose", "7 - propose\none patch per change,\nreplayed and validated\non a fresh copy", xs[3], bottom, w, h, "guard")
    d.box("devops", "8 - devops\nmerge readiness ·\ntyposquat check ·\nCI suggestion", xs[2], bottom, w, h, "tool")
    d.box("report", "9 - report\nsummary, findings,\ntests and patches", xs[1], bottom, w, h, "core")
    d.box("wait", "patches wait\nfor a human", xs[0] + 20, bottom + 10, 200, 100, "store", shape="ellipse")
    order = ["prepare", "analyze", "review", "testgen", "debug", "docs", "propose", "devops", "report", "wait"]
    for a, b in pairwise(order):
        d.arrow(a, b)
    d.label("Insecure or suspect functions get no regression test and no docstring:\n"
            "a passing test or a docstring would describe the bug as correct.", 40, 500, 16, color="#495057")
    legend(d, 1000, 490, [("model", "uses the language model"), ("tool", "static tools only"),
                          ("guard", "sandbox and validation"), ("core", "workspace and report")])
    d.save("workflow")


def patches() -> None:
    d = Diagram()
    d.label("From an agent's change to the repository (backend/patches.py, backend/validation.py)", 40, 10, 28)
    d.box("change", "Agent change\nin the run's\nisolated copy", 40, 130, 220, 110, "core")
    d.box("fresh", "Replayed alone on\na fresh copy of\nthe repository", 330, 130, 220, 110, "core")
    d.frame("validation: all three must hold", 620, 80, 300, 360)
    d.box("v1", "no test that passed\nbefore now fails\n(sandbox)", 640, 100, 260, 90, "guard")
    d.box("v2", "no new Bandit or\nSemgrep finding", 640, 210, 260, 90, "guard")
    d.box("v3", "no secret in\nthe added lines", 640, 320, 260, 90, "guard")
    d.box("proposed", "Proposed patch\ndiff SHA-256\n+ hash of each file\n+ validation-record hash", 1000, 120, 270, 130, "store")
    d.box("human", "A human reviews\nthe diff and its\nvalidation record\nin the web app", 1000, 360, 270, 130, "ui")
    d.box("applied", "Applied\nfiles re-hashed and\n`git apply --check`\nfirst; backups kept", 1000, 600, 270, 130, "tool")
    d.box("rejected", "Rejected", 660, 610, 200, 90, "store")
    d.box("reverted", "Reverted\nonly if the files are\nstill as the patch\nleft them", 1380, 600, 250, 130, "store")
    d.box("stale", "Stale\nthe files changed\nsince the proposal\n→ revalidate", 1380, 360, 250, 130, "store")
    d.arrow("change", "fresh")
    d.arrow("fresh", "v2")
    d.arrow("v2", "proposed", "passed", sides="rl")
    d.arrow("proposed", "human")
    d.arrow("human", "applied", "approve: send back\nthe three hashes")
    d.arrow("human", "rejected", "reject", sides="bt")
    d.arrow("applied", "reverted", "revert")
    d.arrow("human", "stale", "on apply: files\nchanged since")
    d.arrow("stale", "proposed", "revalidate", sides="tr")
    d.label("Only a patch whose validation passed can be approved. A different hash,\n"
            "or a record edited after the proposal, is refused. Every step is in the audit log.",
            40, 760, 16, color="#495057")
    d.save("patches")


def training() -> None:
    d = Diagram()
    d.label("Fine-tuning pipeline: from verified problems to the laptop", 40, 10, 28)
    w, h, top, bottom = 260, 130, 100, 360
    xs = [40, 360, 680, 1000, 1320]
    d.box("src", "Verified problems\nCodeRM-UnitTest\nsolutions + tests\n+ self-oss-instruct", xs[0], top, w, h, "store")
    d.box("tasks", "Build examples\nT1 repair · T2 tests\nT3 review · T4 traces\n+ 3,271 realistic bugs", xs[1], top, w, h, "core")
    d.box("teacher", "Teacher Qwen3.5-9B\n(2×T4, vLLM)\ndiagnoses, explanations,\nrealistic bugs", xs[2], top, w, h, "model")
    d.box("check", "Execution checks\nkept only if a real\ntest fails / the sandbox\nconfirms the label", xs[3], top, w, h, "guard")
    d.box("decon", "13-gram decontamination\nagainst every eval set\n+ grouped split\n(no problem in 2 splits)", xs[4], top, w, h, "guard")
    d.box("train", "QLoRA on one T4\nUnsloth · rank 16\n2 epochs · 2–5 h", xs[4], bottom, w, h, "model")
    d.box("eval", "Evaluation harness\n16 tasks, code run\nin the sandbox,\npaired McNemar tests", xs[3], bottom, w, h, "tool")
    d.box("merge", "Merge the adapter\ninto the base,\nchecked against\nbase + adapter", xs[2], bottom, w, h, "core")
    d.box("gguf", "GGUF export\nQ8_0 / Q4_K_M\nllama.cpp", xs[1], bottom, w, h, "core")
    d.box("laptop", "Laptop CPU\n3B Q4_K_M + n-gram:\na fix in ~15 s,\n2.2 GB, 456 J", xs[0], bottom, w, h, "ui")
    order = ["src", "tasks", "teacher", "check", "decon", "train", "eval", "merge", "gguf", "laptop"]
    for a, b in pairwise(order):
        d.arrow(a, b)
    d.label("Kaggle T4 GPUs: teacher, training, evaluation, merge. Laptop: data checks, scoring, deployment.",
            40, 540, 16, color="#495057")
    d.save("training")


def evaluation_chain() -> None:
    d = Diagram()
    d.label("The brief's chain, and what each stage gave", 40, 10, 28)
    stages = [
        ("slm", "Small model\n\n5 models, 10 tasks;\nthe 1.5B costs 8× less\nenergy per correct\nanswer than the 9B", "store"),
        ("ft", "Fine-tuning\n\nQLoRA, one T4;\n3B repair 46 → 62 %,\nbugs caught by its\ntests 62 → 83 %", "model"),
        ("quant", "Quantization\n\nQ8: no loss;\nQ4: −2 to −4 points,\n2.8× faster,\n2.8× less RAM", "core"),
        ("tokens", "Token optimization\n\nshorter prompts −14 %\ninput, no significant\nloss; full test suite\n2.2× input, no gain", "tool"),
        ("agents", "Agentic workflow\n\nmulti-agent + tools:\n4 of 5 bugs, 5 of 5\nvulnerabilities\n(single agent: 0 and 3)", "ui"),
        ("tasks", "On the laptop\n\nreview, tests, a fix\nin ~15 s, 2.2 GB RAM,\nevery patch approved\nby a human", "guard"),
    ]
    for i, (key, label, color) in enumerate(stages):
        d.box(key, label, 40 + i * 300, 100, 250, 200, color)
    for (a, _, _), (b, _, _) in pairwise(stages):
        d.arrow(a, b)
    d.save("evaluation_chain")


if __name__ == "__main__":
    architecture()
    workflow()
    patches()
    training()
    evaluation_chain()
