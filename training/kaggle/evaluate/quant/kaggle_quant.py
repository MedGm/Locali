"""How much does 4-bit rounding cost run E, and does a better 4-bit file win it back? (T4)

Run E fixes 63.4 % of HumanEvalFix on Kaggle (vLLM, 16-bit) and 57.9 % on the laptop (llama.cpp,
Q4_K_M); run D lost 0.6 points over the same step. The two runtimes also differ in their sampling
defaults, so that gap is not a measurement of rounding. Here every file is served by the same
llama.cpp build (the commit of every laptop run), greedy, on the same problems:

    f16, Q8_0, Q5_K_M, Q4_K_M, and Q4_K_M with an importance matrix (llama-imatrix on training rows)

1. training/merge_adapter.py merges the adapter (Kaggle dataset locali-adapters-3b), then
   convert_hf_to_gguf.py --outtype f16 and llama-quantize, as in training/kaggle/deploy/gguf
2. llama-server with all layers on the GPU answers each task; scored in evaluation/isolated.py

Only the answers and scores are kept. Environment: ADAPTER=mixv3s, TASKS (space-separated),
QUANTS (space-separated), PILOT=1 runs 8 problems.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = "https://github.com/MedGm/Locali.git"
COMMIT = "__LOCALI_COMMIT__"  # replaced when the notebook is built
LLAMA_CPP = ("https://github.com/ggml-org/llama.cpp.git", "987498f")
WORK = Path("/kaggle/working")
CODE = Path("/tmp/locali")
TMP = Path("/tmp/gguf")
RESULTS = WORK / "results"
LOGS = WORK / "logs"
BASE_REVISION = "488639f1ff808d1d3d0ba301aef8c11461451ec5"
ADAPTER = os.environ.get("ADAPTER", "mixv3s")
NAME = f"qwen2.5-coder-3b-locali-{ADAPTER}"
TASKS = tuple(os.environ.get("TASKS", "humanevalfix humaneval_plus").split())
QUANTS = tuple(os.environ.get("QUANTS", "f16 q8_0 q5_k_m q4_k_m q4_k_m-imatrix").split())
CALIBRATION_ROWS = 200
PORT = 8000
LIMIT = 8 if os.environ.get("PILOT") == "1" else None


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(cmd: list[str], logfile: Path | None = None, **kwargs) -> None:
    log(" ".join(map(str, cmd))[:200])
    if logfile is None:
        subprocess.run(cmd, check=True, **kwargs)
        return
    with open(logfile, "a") as fh:
        subprocess.run(cmd, check=True, stdout=fh, stderr=subprocess.STDOUT, **kwargs)


def calibration_text() -> Path:
    """Training rows as plain text for llama-imatrix: what the model reads and writes in use."""
    train = next(Path("/kaggle/input").rglob("train.jsonl"))
    rows = [json.loads(line) for line in train.read_text().splitlines() if line.strip()]
    step = max(1, len(rows) // CALIBRATION_ROWS)
    out = TMP / "calibration.txt"
    out.write_text("\n\n".join(m["content"] for row in rows[::step][:CALIBRATION_ROWS] for m in row["messages"]))
    return out


def build_files() -> dict[str, Path]:
    TMP.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    if not CODE.exists():
        run(["git", "clone", "-q", REPO, str(CODE)])
    run(["git", "-C", str(CODE), "checkout", "-q", COMMIT])
    adapter = next(p.parent for p in Path("/kaggle/input").rglob("adapter_config.json") if p.parent.name == ADAPTER)
    merged = TMP / "merged"
    run([sys.executable, "-m", "pip", "install", "-q", "peft", "datasets", "radon", "bandit"])
    # Kaggle's preinstalled torchao is too old for peft's import check; the merge does not use it
    run([sys.executable, "-m", "pip", "uninstall", "-y", "-q", "torchao"])
    run([sys.executable, "-m", "training.merge_adapter", str(adapter), str(merged)], cwd=CODE)
    shutil.copy(merged / "merge_report.json", WORK / f"{NAME}.merge_report.json")

    llama = TMP / "llama.cpp"
    run(["git", "clone", "-q", LLAMA_CPP[0], str(llama)])
    run(["git", "-C", str(llama), "checkout", "-q", LLAMA_CPP[1]])
    run([sys.executable, "-m", "pip", "install", "-q", "gguf", "sentencepiece"])
    files = {"f16": TMP / f"{NAME}-f16.gguf"}
    run([sys.executable, str(llama / "convert_hf_to_gguf.py"), str(merged), "--outtype", "f16",
         "--outfile", str(files["f16"])])
    shutil.rmtree(merged)
    build_log = LOGS / "llama_build.log"
    # Kaggle's image has the driver library only as libcuda.so.1, which CMake does not find by itself
    driver = next((str(f) for d in ("/usr/lib64-nvidia", "/usr/lib/x86_64-linux-gnu", "/usr/local/nvidia/lib64",
                                    "/usr/local/cuda/lib64", "/usr/local/cuda/lib64/stubs")
                   for f in sorted(Path(d).glob("libcuda.so*"))), None)
    log(f"cuda driver library: {driver}")
    run(["cmake", "-S", str(llama), "-B", str(llama / "build"), "-DGGML_CUDA=ON", "-DLLAMA_CURL=OFF",
         *([f"-DCUDA_cuda_driver_LIBRARY={driver}"] if driver else [])], build_log)
    run(["cmake", "--build", str(llama / "build"), "--target", "llama-quantize", "llama-imatrix", "llama-server",
         "-j", "4"], build_log)
    tools = llama / "build" / "bin"
    imatrix = TMP / "imatrix.dat"
    for quant in QUANTS:
        if quant == "f16":
            continue
        kind, _, weighted = quant.partition("-")
        extra = []
        if weighted:
            if not imatrix.exists():
                run([str(tools / "llama-imatrix"), "-m", str(files["f16"]), "-f", str(calibration_text()),
                     "-o", str(imatrix), "-ngl", "99", "-c", "512"], LOGS / "imatrix.log")
            extra = ["--imatrix", str(imatrix)]
        files[quant] = TMP / f"{NAME}-{quant}.gguf"
        run([str(tools / "llama-quantize"), *extra, str(files["f16"]), str(files[quant]), kind.upper()],
            LOGS / f"quantize_{quant}.log")
        log(f"{quant}: {files[quant].stat().st_size / 1e9:.2f} GB")
    return {q: files[q] for q in QUANTS}


def score_in_isolation() -> str:
    from evaluation import isolated
    from evaluation.tasks import codegen, humanevalpack

    def run_program(program: str, timeout_s: float = 60) -> codegen.Outcome:
        r = isolated.run_isolated(program, timeout_s=min(timeout_s, 60))
        return codegen.Outcome(r.passed, r.status, r.error or "", r.seconds)

    codegen.run_program = run_program
    humanevalpack.run_program = run_program
    return isolated.network_isolation()


def wait_healthy(server: subprocess.Popen, timeout_s: float = 600) -> bool:
    start = time.time()
    while time.time() - start < timeout_s:
        if server.poll() is not None:
            return False
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=5)
            return True
        except OSError:
            time.sleep(3)
    return False


def evaluate(quant: str, gguf: Path) -> None:
    from evaluation.rescore import rescore_run
    from evaluation.run import TASKS as REGISTERED

    server_bin = TMP / "llama.cpp" / "build" / "bin" / "llama-server"
    with open(LOGS / f"server_{quant}.log", "w") as fh:
        server = subprocess.Popen(
            [str(server_bin), "-m", str(gguf), "--jinja", "--parallel", "4", "-c", "16384", "-ngl", "99",
             "--host", "127.0.0.1", "--port", str(PORT)], stdout=fh, stderr=subprocess.STDOUT)
    try:
        if not wait_healthy(server):
            raise RuntimeError(f"server failed to start, see logs/server_{quant}.log")
        for task_name in TASKS:
            model_id = f"qwen2.5-coder-3b-ft-qlora-{ADAPTER}"
            out = RESULTS / task_name / f"{model_id}__{quant}__kaggle-t4-llamacpp"
            cmd = [sys.executable, "-m", "evaluation.run", "--benchmark", task_name, "--generate-only",
                   "--workers", "4", "--model-id", model_id, "--model-revision", BASE_REVISION,
                   "--quantization", quant, "--max-tokens", "1024", "--runtime", f"llama.cpp {LLAMA_CPP[1]} T4",
                   "--base-url", f"http://127.0.0.1:{PORT}/v1", "--served-model", "local", "--out", str(out),
                   "--notes", "quantization check, one llama.cpp build", *(["--limit", str(LIMIT)] if LIMIT else [])]
            try:
                run(cmd, LOGS / f"run_{task_name}_{quant}.log", cwd=CODE)
            except subprocess.CalledProcessError as e:
                log(f"{task_name}/{quant}: FAILED rc={e.returncode}")
                continue
            task = REGISTERED[task_name]
            summary = rescore_run(out, task, task.load(LIMIT), workers=8)
            log(f"{task_name}/{quant}: pass@1 {summary['metrics']['pass@1']}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=60)
        except subprocess.TimeoutExpired:
            server.kill()


def main() -> None:
    files = build_files()
    sys.path.insert(0, str(CODE))
    log(f"network isolation {score_in_isolation()}")
    for quant, gguf in files.items():
        evaluate(quant, gguf)
        if quant != "f16":
            gguf.unlink()
    log("all done")


if __name__ == "__main__":
    main()
