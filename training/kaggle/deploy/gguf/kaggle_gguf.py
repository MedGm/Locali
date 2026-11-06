"""Merge a 3B adapter into its base and export a Q4_K_M GGUF for the laptop (Kaggle, CPU work only).

1. training/merge_adapter.py: merge in FP32 with its logit checks, save FP16 safetensors
2. llama.cpp 987498f (the commit of every laptop run): convert_hf_to_gguf.py --outtype f16,
   then llama-quantize Q4_K_M
Only the Q4_K_M file and the merge report are kept as outputs, to keep the download small.

Environment: ADAPTER=mixv3 (folder name in the Kaggle dataset locali-adapters-3b).
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = "https://github.com/MedGm/Locali.git"
COMMIT = "__LOCALI_COMMIT__"  # replaced when the notebook is built
LLAMA_CPP = ("https://github.com/ggml-org/llama.cpp.git", "987498f")
WORK = Path("/kaggle/working")
CODE = Path("/tmp/locali")
TMP = Path("/tmp/gguf")
ADAPTER = os.environ.get("ADAPTER", "mixv3")
NAME = f"qwen2.5-coder-3b-locali-{ADAPTER}"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(cmd: list[str], **kwargs) -> None:
    log(" ".join(cmd)[:200])
    subprocess.run(cmd, check=True, **kwargs)


def main() -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    if not CODE.exists():
        run(["git", "clone", "-q", REPO, str(CODE)])
    run(["git", "-C", str(CODE), "checkout", "-q", COMMIT])
    adapter = next(p.parent for p in Path("/kaggle/input").rglob("adapter_config.json") if p.parent.name == ADAPTER)
    merged = TMP / "merged"
    run([sys.executable, "-m", "pip", "install", "-q", "peft"])
    # Kaggle's preinstalled torchao is too old for peft's import check; the merge does not use it
    run([sys.executable, "-m", "pip", "uninstall", "-y", "-q", "torchao"])
    run([sys.executable, "-m", "training.merge_adapter", str(adapter), str(merged)], cwd=CODE)
    shutil.copy(merged / "merge_report.json", WORK / f"{NAME}.merge_report.json")

    llama = TMP / "llama.cpp"
    run(["git", "clone", "-q", LLAMA_CPP[0], str(llama)])
    run(["git", "-C", str(llama), "checkout", "-q", LLAMA_CPP[1]])
    run([sys.executable, "-m", "pip", "install", "-q", "gguf", "sentencepiece"])
    f16 = TMP / f"{NAME}-f16.gguf"
    run([sys.executable, str(llama / "convert_hf_to_gguf.py"), str(merged), "--outtype", "f16", "--outfile", str(f16)])
    shutil.rmtree(merged)
    run(["cmake", "-S", str(llama), "-B", str(llama / "build"), "-DGGML_CUDA=OFF", "-DLLAMA_CURL=OFF"],
        stdout=subprocess.DEVNULL)
    run(["cmake", "--build", str(llama / "build"), "--target", "llama-quantize", "-j", "4"], stdout=subprocess.DEVNULL)
    q4 = WORK / f"{NAME}-q4_k_m.gguf"
    run([str(llama / "build" / "bin" / "llama-quantize"), str(f16), str(q4), "Q4_K_M"])
    log(f"done: {q4} ({q4.stat().st_size / 1e9:.2f} GB)")


if __name__ == "__main__":
    main()
