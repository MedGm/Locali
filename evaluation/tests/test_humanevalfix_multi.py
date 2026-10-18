from evaluation.tasks.humanevalfix_multi import Item, extract, messages, program


def item(lang, **kw):
    base = {"task_id": "X/0", "language": lang, "declaration": "", "canonical_solution": "", "buggy_solution": "",
            "bug_type": "operator", "entry_point": "f", "imports": "", "test_setup": "", "test": "TEST"}
    return Item(**(base | kw))


def test_prompt_uses_the_language_fence_and_the_python_wording():
    text = messages(item("go", declaration="func F() int {\n", buggy_solution="  return 1\n}\n", entry_point="F"))[0]["content"]
    assert text.startswith("Fix bugs in F.") and "```go\nfunc F() int {" in text and "These tests fail:" in text


def test_extract_takes_the_first_block_or_the_whole_answer():
    assert extract("Here:\n```java\nclass A {}\n```\nmore\n```x\ny```") == "class A {}\n"
    assert extract("int f() { return 1; }") == "int f() { return 1; }"


def test_javascript_asserts_throw():
    files = program(item("js"), "const f = () => 1")
    assert files["main.js"].startswith("console.assert = ") and files["main.js"].endswith("TEST")


def test_cpp_drops_the_answers_own_main_and_keeps_the_includes():
    it = item("cpp", declaration="#include<stdio.h>\nusing namespace std;\nint f(){\n")
    code = "int f(){ return 1; }\nint main(){ return 0; }\n"
    src = program(it, code)["main.cpp"]
    assert "#include<stdio.h>" in src and "using namespace std;" in src
    assert src.count("int main") == 0 and src.endswith("TEST")


def test_java_moves_imports_up_and_wraps_a_bare_method():
    it = item("java", declaration="import java.util.*;\nclass Solution {\n    public int f() {\n")
    src = program(it, "import java.lang.*;\npublic int f() { return 1; }")["Main.java"]
    assert src.startswith("import java.lang.*;\nimport java.util.*;")
    assert "class Solution {\npublic int f()" in src and src.index("TEST") < src.index("class Solution")
    full = program(it, "public class Solution { int f() { return 1; } }")["Main.java"]
    assert "public class Solution" not in full and "class Solution {" in full


def test_go_uses_the_problems_imports_not_the_answers():
    it = item("go", test_setup="package main\n\nimport (\n    \"testing\"\n)\n", imports='import (\n    "math"\n)\n')
    src = program(it, 'package main\n\nimport (\n    "fmt"\n)\n\nfunc F() int { return 1 }\n')["main_test.go"]
    assert '"fmt"' not in src and '"math"' in src and src.count("package main") == 1 and "func F()" in src


def test_rust_is_a_library_with_the_declarations_uses():
    it = item("rust", declaration="\nuse std::cmp::max;\nuse regex::Regex;\n\nfn f() -> i32{\n")
    src = program(it, "fn f() -> i32 { 1 }")["src/lib.rs"]
    assert src.startswith("#![allow(unused, deprecated)]") and "use regex::Regex;" in src and src.endswith("TEST")
