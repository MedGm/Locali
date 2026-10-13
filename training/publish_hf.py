"""Publish the Locali models and the training mixture to the Hugging Face Hub (public).

    uv run python -m training.publish_hf [--only adapter merged gguf adapters dataset]

Model cards live in docs/hf/. Files come from ~/models and data/mix_v2. The "Llama" name prefix
follows the Llama 3.1 licence (the training data contains Llama-3.1-70B-generated unit tests).
"""

import argparse
from pathlib import Path

from huggingface_hub import HfApi

USER = "MedGm"
MODELS = Path.home() / "models"
CARDS = Path(__file__).resolve().parents[1] / "docs" / "hf"
DATA = Path(__file__).resolve().parents[1] / "data" / "mix_v2"
ADAPTER_FILES = ["adapter_config.json", "adapter_model.safetensors", "tokenizer.json", "tokenizer_config.json",
                 "chat_template.jinja"]
VARIANTS = ["qwen2.5-coder-1.5b-qlora-v1", "qwen2.5-coder-1.5b-lora16-v2", "qwen2.5-coder-1.5b-rslora-v2",
            "phi-4-mini-qlora-v2"]


def upload(api: HfApi, repo: str, card: str, files: dict[str, Path], repo_type: str = "model") -> None:
    api.create_repo(repo, repo_type=repo_type, private=False, exist_ok=True)
    api.upload_file(path_or_fileobj=CARDS / card, path_in_repo="README.md", repo_id=repo, repo_type=repo_type)
    for name, path in files.items():
        print(f"{repo}: {name} ({path.stat().st_size / 2**20:.0f} MiB)", flush=True)
        api.upload_file(path_or_fileobj=path, path_in_repo=name, repo_id=repo, repo_type=repo_type)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="+", default=["adapter", "adapters", "dataset", "gguf", "merged"])
    args = parser.parse_args()
    api = HfApi()

    if "adapter" in args.only:
        src = MODELS / "adapters" / "qwen2.5-coder-1.5b-qlora-v2"
        upload(api, f"{USER}/Llama-Locali-Qwen2.5-Coder-1.5B-QLoRA", "qlora-adapter.md",
               {f: src / f for f in ADAPTER_FILES})
    if "adapters" in args.only:
        files = {f"{v}/{f}": MODELS / "adapters" / v / f for v in VARIANTS for f in ADAPTER_FILES
                 if (MODELS / "adapters" / v / f).exists()}
        upload(api, f"{USER}/Llama-Locali-adapters", "adapters.md", files)
    if "dataset" in args.only:
        upload(api, f"{USER}/locali-mix-v2", "dataset.md",
               {f: DATA / f for f in ["train.jsonl", "val.jsonl", "test.jsonl", "stats.json"]}, repo_type="dataset")
    if "gguf" in args.only:
        src = MODELS / "gguf"
        upload(api, f"{USER}/Llama-Locali-Qwen2.5-Coder-1.5B-GGUF", "gguf.md", {
            f"llama-locali-qwen2.5-coder-1.5b-{q}.gguf": src / f"qwen2.5-coder-1.5b-qlora-v2-{q}.gguf"
            for q in ["q8_0", "q4_k_m"]})
    if "merged" in args.only:
        src = MODELS / "merged" / "qwen2.5-coder-1.5b-qlora-v2"
        upload(api, f"{USER}/Llama-Locali-Qwen2.5-Coder-1.5B", "merged.md",
               {p.name: p for p in sorted(src.iterdir()) if p.is_file()})


if __name__ == "__main__":
    main()
