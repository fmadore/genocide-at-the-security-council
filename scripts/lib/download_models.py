"""Prefetch embedding weights into the Hugging Face cache.

Called by scripts/cluster/download_models.sh on the login node, which is the
only machine in the loop with internet access. Compute nodes run with
HF_HUB_OFFLINE=1, so anything not fetched here fails the job at model-load time
— which is the intended behaviour. A job that silently downloaded weights would
be a job whose model version depends on when it happened to run.

Usage:
    python scripts/lib/download_models.py                # the default model
    python scripts/lib/download_models.py qwen3-0.6b granite-small-en
    python scripts/lib/download_models.py --all
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib import console, embeddings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("keys", nargs="*", help="registry keys (default: the registry default)")
    parser.add_argument("--all", action="store_true", help="fetch every model in the registry")
    args = parser.parse_args()

    registry = embeddings.load_registry()
    if args.all:
        keys = list(registry.models)
    elif args.keys:
        keys = args.keys
    else:
        keys = [registry.default]

    unknown = [k for k in keys if k not in registry.models]
    if unknown:
        console.fail(
            f"unknown model key(s): {', '.join(unknown)}",
            [f"available: {', '.join(registry.models)}"],
        )

    if os.environ.get("HF_HUB_OFFLINE") == "1":
        console.fail("HF_HUB_OFFLINE=1 — this step needs the network; run it on the login node")

    from huggingface_hub import snapshot_download

    for key in keys:
        spec = registry.models[key]
        console.step(f"{key} -> {spec.repo} @ {spec.revision}")
        path = snapshot_download(repo_id=spec.repo, revision=spec.revision)
        console.info(f"cached at {path}")

    console.step("Done")
    console.info(f"HF_HOME={os.environ.get('HF_HOME', '(default)')}")


if __name__ == "__main__":
    main()
