# Kaggle jobs

Everything that needs a GPU runs on Kaggle's free T4s. Each folder is one Kaggle notebook: the
Python script, the notebook built from it by `build_notebook.py`, and `kernel-metadata.json`
(the Kaggle name, the GPU, the data sets it reads). `common.py` holds the shared code: installing
vLLM, starting and stopping its servers, sending the requests, logging the GPU's power.

    uv run python training/kaggle/build_notebook.py training/kaggle/evaluate/explain/kaggle_explain.py
    kaggle kernels push -p training/kaggle/evaluate/explain

The answers come back to the laptop, where they are scored in the sandbox; the results are in
`experiments/results/`.

| Group | Folder | What it does |
|---|---|---|
| `make_data` | `bugs` | the teacher (Qwen3.5-9B) writes realistic bugs, kept only when a test catches them |
| | `teacher` | the teacher explains each training bug |
| | `selfdistill` | the base 3B answers the replay prompts (data v3s, run E) |
| | `evalgen` | answers of a base model and its adapter, side by side |
| `train` | `finetune` | the fine-tuning job (Unsloth, one T4), then every benchmark answer |
| | `finetune-3b-v2` … `finetune-3b-v3s` | the same job for 3B runs A to E |
| | `finetune-3b-v3f` | run F: run E's data with the fix before the diagnosis |
| | `finetune-seed` | the 1.5B run again with another seed |
| `deploy` | `gguf` | merge an adapter into its base and build the 4-bit GGUF for the laptop |
| `evaluate` | `baselines` | every benchmark, base models |
| | `repair_prereg`, `testgen2048` | the two pre-registered checks |
| | `explain` | explaining code (HumanEvalExplain) |
| | `robust`, `feedback` | repair with reworded prompts and with test feedback |
| | `capability`, `divergence`, `scaffold`, `plan` | the study of why code writing drops |
| | `quant` | run E as f16, 8-, 5- and 4-bit files on one llama.cpp build |
| | `scaling` | run E's adapter at half and three-quarter strength, and the average of runs D and E |
| | `diagnosis` | rewrites the bug notes as reviewer diagnoses (run D's data) |
| | `multilang`, `multilang-rescore` | bug fixing in five other languages |
| | `serving`, `speculative` | GPU serving and guessing ahead |
| | `explore` | a notebook to browse the training data |
| `archive` | `w1-spikes` | the first week's checks |
