from fastapi.testclient import TestClient

from backend.analysis import analyze
from backend.app import create_app
from backend.languages import count_languages

JS = """const { exec } = require("child_process");
const crypto = require("crypto");

function run(name) {
  exec(`ls ${name}`);
}
function find(db, name) {
  return db.query("SELECT * FROM users WHERE name = '" + name + "'");
}
function calc(expr) {
  return eval(expr);
}
function show(el, html) {
  el.innerHTML = html;
}
const digest = crypto.createHash("md5").update("x").digest("hex");
const API_KEY = "Zq8vR2mW9xLp4TnB7cYd";
"""

JAVA = """import java.security.MessageDigest;
import java.sql.Statement;

class Users {
    void find(Statement st, String name) throws Exception {
        st.executeQuery("SELECT * FROM users WHERE name = '" + name + "'");
        Runtime.getRuntime().exec("ls " + name);
        MessageDigest.getInstance("MD5");
    }
}
"""

GO = """package users

import (
	"crypto/md5"
	"database/sql"
	"fmt"
	"os/exec"
)

func Find(db *sql.DB, name string) {
	db.Query(fmt.Sprintf("SELECT * FROM users WHERE name = '%s'", name))
	exec.Command("sh", "-c", "ls "+name).Run()
	md5.Sum([]byte(name))
}
"""


def rules(findings, path):
    return {(f.line, f.rule) for f in findings if f.path == path and f.tool == "semgrep"}


def test_javascript_java_and_go_vulnerabilities_are_found(tmp_path):
    (tmp_path / "app.js").write_text(JS)
    (tmp_path / "Users.java").write_text(JAVA)
    (tmp_path / "users.go").write_text(GO)
    found = analyze(tmp_path)
    assert {(5, "js-shell-command"), (8, "js-sql-concat"), (11, "js-eval"), (14, "js-inner-html"),
            (16, "js-weak-hash")} <= rules(found, "app.js")
    assert {(6, "java-sql-concat"), (7, "java-runtime-exec"), (8, "java-weak-hash")} <= rules(found, "Users.java")
    assert {(11, "go-sql-format"), (12, "go-shell-command"), (13, "go-weak-hash")} <= rules(found, "users.go")
    assert any(f.tool == "secrets" and f.path == "app.js" for f in found)


def test_safe_code_in_other_languages_is_quiet(tmp_path):
    (tmp_path / "ok.js").write_text('function find(db, name) { return db.query("SELECT * FROM users WHERE name = ?", [name]); }\n'
                                    'function show(el) { el.innerHTML = "<b>hi</b>"; }\n')
    (tmp_path / "ok.go").write_text('package x\n\nimport "database/sql"\n\nfunc Find(db *sql.DB, n string) { db.Query("SELECT 1 WHERE n = ?", n) }\n')
    assert [f for f in analyze(tmp_path) if f.tool == "semgrep"] == []


def test_languages_are_counted_and_non_python_repos_are_listed(tmp_path):
    (tmp_path / "web" / "src").mkdir(parents=True)
    (tmp_path / "web" / "src" / "a.ts").write_text("export const a = 1\n")
    (tmp_path / "web" / "src" / "b.tsx").write_text("export const b = 1\n")
    (tmp_path / "web" / "node_modules" / "x").mkdir(parents=True)
    (tmp_path / "web" / "node_modules" / "x" / "i.js").write_text("1\n")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "a.md").write_text("hi\n")
    assert count_languages(tmp_path / "web") == {"typescript": 2}
    repos = TestClient(create_app(repos_root=tmp_path, data_dir=tmp_path / "data")).get("/repos").json()
    assert [(r["name"], r["languages"], r["python_files"]) for r in repos] == [("web", {"typescript": 2}, 0)]


def test_the_full_assistant_is_refused_on_a_repository_without_python(tmp_path):
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "a.js").write_text("eval(x)\n")
    client = TestClient(create_app(repos_root=tmp_path, data_dir=tmp_path / "data", model=lambda m: "x"))
    r = client.post("/runs", json={"repo": "web", "mode": "agents"})
    assert r.status_code == 422 and "Python" in r.json()["detail"]
    assert client.post("/runs", json={"repo": "web", "mode": "analyze"}).status_code == 201
