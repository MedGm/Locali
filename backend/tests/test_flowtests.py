from pathlib import Path

from backend.agents.flowtests import (
    api_routes,
    app_factory,
    called_project_functions,
    generate_api_tests,
    generate_integration_tests,
    integration_targets,
)
from backend.tests.test_debug_agent import ScriptedModel
from backend.workspace import open_workspace
from evaluation.tests.test_codegen import needs_docker

DEMO = Path(__file__).resolve().parents[2] / "demo_repo"
FLAGGED = {("tinyshop/db.py", "find_products"), ("tinyshop/cli.py", "main")}


def test_api_routes_of_demo_repo():
    routes = {(r.method, r.path): r.function for r in api_routes(DEMO)}
    assert routes[("POST", "/orders")] == "place_order"
    assert routes[("GET", "/reports/{day}")] == "day_report"
    assert app_factory(DEMO, "tinyshop/api.py") == "create_app"


def test_routes_on_a_module_level_app_are_found(tmp_path):
    (tmp_path / "svc.py").write_text('from fastapi import FastAPI\napp = FastAPI()\n\n\n@app.get("/ping")\ndef ping():\n    return {}\n')
    assert [(r.method, r.path, r.function) for r in api_routes(tmp_path)] == [("GET", "/ping", "ping")]


def test_called_project_functions_follow_imports():
    assert ("tinyshop/db.py", "sales_for_day") in called_project_functions(DEMO, "tinyshop/reports.py", "daily_report")
    assert ("tinyshop/db.py", "record_sale") in called_project_functions(DEMO, "tinyshop/api.py", "place_order")


def test_integration_targets_skip_flagged_code_and_route_handlers():
    targets = integration_targets(DEMO, skip=FLAGGED, limit=10)
    assert ("tinyshop/reports.py", "daily_report") in targets
    assert ("tinyshop/cli.py", "main") not in targets
    assert not any(rel == "tinyshop/api.py" and func != "create_app" for rel, func in targets)


def test_a_project_without_apps_or_cross_module_calls_has_no_targets(tmp_path):
    (tmp_path / "one.py").write_text("def f(x):\n    return x + 1\n")
    assert api_routes(tmp_path) == []
    assert integration_targets(tmp_path, skip=set()) == []


def test_routes_that_call_flagged_code_get_no_prompt():
    model = ScriptedModel(*["no code here"] * 10)
    generate_api_tests(DEMO, model, skip=FLAGGED)
    assert model.prompts and not any("`GET /products`" in p for p in model.prompts)
    assert any("`POST /orders`" in p for p in model.prompts)


OVERSELL = '''```python
from fastapi.testclient import TestClient
from tinyshop.api import create_app


def test_order_larger_than_stock_is_refused(tmp_path):
    c = TestClient(create_app(tmp_path / "test.db"))
    pid = c.post("/products", json={"name": "Tea", "price": 2.5, "stock": 1}).json()["id"]
    assert c.post("/orders", json={"product_id": pid, "qty": 5, "day": "2026-11-04"}).status_code == 409
```'''

LIVE_SERVER = '''```python
import urllib.request


def test_products_over_http():
    assert urllib.request.urlopen("http://localhost:8000/products").status == 200
```'''

REPORT = '''```python
from tinyshop import db
from tinyshop.reports import daily_report


def test_report_lists_the_sales_of_the_day(tmp_path):
    conn = db.connect(tmp_path / "s.db")
    pid = db.add_product(conn, "Tea", 2.5, stock=5)
    db.record_sale(conn, pid, 2, "2026-11-04")
    assert "Tea: 2 x 2.50" in daily_report(conn, "2026-11-04")
```'''


class ByRoute:
    """Answers each API prompt by the route it names; everything else gets no code."""

    def __init__(self, answers: dict[str, str]):
        self.answers, self.prompts = answers, []

    def __call__(self, messages):
        prompt = messages[-1]["content"]
        self.prompts.append(prompt)
        return next((a for key, a in self.answers.items() if key in prompt), "no code")


@needs_docker
def test_api_test_that_catches_the_oversell_is_a_suspect_and_keeps_nothing():
    ws = open_workspace(DEMO)
    try:
        result = generate_api_tests(ws.path, ByRoute({"`POST /orders`": OVERSELL}), skip=FLAGGED)
        assert ("tinyshop/api.py", "place_order") in {(s.file, s.function) for s in result.suspects}
        assert not (ws.path / "tests/test_locali_api_place_order.py").exists()
    finally:
        ws.cleanup()


@needs_docker
def test_api_test_against_a_live_server_is_a_crash_not_a_suspect():
    ws = open_workspace(DEMO)
    try:
        result = generate_api_tests(ws.path, ByRoute({"`GET /reports/{day}`": LIVE_SERVER}), skip=FLAGGED)
        assert result.crashed.get("tinyshop/api.py::day_report") == 1
        assert not result.suspects
    finally:
        ws.cleanup()


@needs_docker
def test_passing_integration_test_is_kept_under_its_kind_name():
    ws = open_workspace(DEMO)
    try:
        model = ByRoute({"`daily_report`": REPORT})
        result = generate_integration_tests(ws.path, model, skip=FLAGGED)
        assert "tests/test_locali_integration_daily_report.py" in result.files
        assert (ws.path / "tests/test_locali_integration_daily_report.py").exists()
    finally:
        ws.cleanup()


def test_api_prompt_gives_the_client_fixture_on_a_temporary_database():
    from backend.agents.flowtests import Route, api_prompt

    prompt = api_prompt("tinyshop.api", "create_app", Route("tinyshop/api.py", "place_order", "POST", "/orders"), "code\n")
    assert "def client(tmp_path):" in prompt
    assert 'TestClient(create_app(tmp_path / "test.db"))' in prompt
    assert "`POST /orders`" in prompt
