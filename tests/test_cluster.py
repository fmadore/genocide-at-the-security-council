"""The cluster scripts, checked without a cluster.

These are shell files that run unattended on a batch node hours after they were
submitted, where a mistake shows up as a wasted reservation and an empty log.
The checks here are the ones that would otherwise be discovered that way: a job
that writes its log somewhere nobody looks, a submit script that forgot to
activate the venv, a documented command that does not exist.

They also pin the two invariants the pipeline depends on — that 06 runs before
07, and that 07 stays out of the release path.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CLUSTER = ROOT / "scripts" / "cluster"

SCRIPTS = sorted(CLUSTER.glob("*.sh"))
#: Sourced by the others, so it must not exit on their behalf.
SOURCED = {"env.sh"}
#: Run on the user's own machine, not on the cluster.
LOCAL = {"fetch_results.sh", "push_code.sh"}
SUBMIT = [p for p in SCRIPTS if p.name.startswith("submit_") or p.name == "smoke.sh"]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_there_are_cluster_scripts() -> None:
    assert SCRIPTS, "scripts/cluster/ should not be empty"


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
def test_every_script_has_a_shebang(path: Path) -> None:
    assert read(path).startswith("#!/usr/bin/env bash")


def code(path: Path) -> str:
    """The script minus its comments, so prose about `set -e` is not mistaken
    for the thing itself."""
    return "\n".join(
        line for line in read(path).splitlines() if not line.lstrip().startswith("#")
    )


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
def test_scripts_fail_fast(path: Path) -> None:
    """Except env.sh: it is sourced, and `set -e` there would arm the caller."""
    if path.name in SOURCED:
        assert "set -euo pipefail" not in code(path)
    else:
        assert "set -euo pipefail" in code(path)


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
def test_line_endings_are_unix(path: Path) -> None:
    """CRLF makes bash fail with `bad interpreter: /usr/bin/env bash^M`."""
    assert b"\r\n" not in path.read_bytes()


@pytest.mark.parametrize("path", SUBMIT, ids=lambda p: p.name)
def test_batch_jobs_set_up_their_environment(path: Path) -> None:
    text = read(path)
    assert "scripts/cluster/env.sh" in text, "must source the shared settings"
    assert "load_python" in text
    assert "activate_venv" in text or "activate_extras" in text


#: The release pipeline runs in the locked environment; the optional steps get
#: their own, because umap-learn's numba dependency cannot coexist with the numpy
#: the lock pins. Getting this backwards would let an optional step rebuild the
#: corpus under an environment that does not match the reproducibility record.
LOCKED_JOBS = {"submit_corpus.sh", "submit_lexical.sh"}
EXTRAS_JOBS = {"submit_embed.sh", "submit_topics.sh", "submit_lemmas.sh", "smoke.sh"}


@pytest.mark.parametrize("name", sorted(LOCKED_JOBS))
def test_the_release_pipeline_runs_in_the_locked_environment(name: str) -> None:
    text = code(CLUSTER / name)
    assert "activate_venv" in text
    assert "activate_extras" not in text


@pytest.mark.parametrize("name", sorted(EXTRAS_JOBS))
def test_the_optional_steps_run_in_the_extras_environment(name: str) -> None:
    text = code(CLUSTER / name)
    assert "activate_extras" in text


def test_setup_builds_both_environments() -> None:
    text = read(CLUSTER / "setup_env.sh")
    assert "--require-hashes" in text, "the locked environment must install with hashes"
    assert "$EXTRAS_VENV" in text
    assert "requirements-cluster.txt" in text


@pytest.mark.parametrize("path", SUBMIT, ids=lambda p: p.name)
def test_batch_jobs_log_where_the_docs_say_to_look(path: Path) -> None:
    text = read(path)
    assert re.search(r"#SBATCH --output=logs/", text)
    assert re.search(r"#SBATCH --error=logs/", text)
    assert re.search(r"#SBATCH --time=", text)


@pytest.mark.parametrize("path", SUBMIT, ids=lambda p: p.name)
def test_batch_jobs_resolve_the_repo_from_slurm(path: Path) -> None:
    """A spooled copy of the script cannot find the repository from its own path."""
    assert "SLURM_SUBMIT_DIR" in read(path)


@pytest.mark.parametrize("path", [p for p in SCRIPTS if p.name not in LOCAL], ids=lambda p: p.name)
def test_cluster_side_scripts_do_not_hardcode_a_home(path: Path) -> None:
    text = read(path)
    assert "/workdir/$USER" in text or "$HOME" in text or "$REPO" in text or "$USER" not in text


def test_gpu_jobs_run_offline() -> None:
    """Compute nodes have no internet. A job that quietly downloaded its own
    weights would be a job whose model version depends on when it ran."""
    for name in ("submit_embed.sh", "smoke.sh"):
        assert "HF_HUB_OFFLINE" in read(CLUSTER / name)


def test_the_topic_job_does_not_request_a_gpu() -> None:
    """NMF, UMAP and HDBSCAN are CPU work; a reserved idle card is queue time
    taken from someone who needs one."""
    assert "--gres=gpu" not in read(CLUSTER / "submit_topics.sh")


def test_the_topic_job_refuses_to_run_without_embeddings() -> None:
    text = read(CLUSTER / "submit_topics.sh")
    assert "vectors.npy" in text and "exit 1" in text


def test_the_smoke_test_cannot_overwrite_a_real_run() -> None:
    """`atomic_directory` replaces its target wholesale, so a 256-speech test
    would leave something indistinguishable from a corpus artefact."""
    assert "--limit" in read(CLUSTER / "smoke.sh")
    step = (ROOT / "scripts" / "06_embed.py").read_text(encoding="utf-8")
    assert "SMOKE = DERIVED" in step
    assert "target = SMOKE" in step


# --- Documentation and configuration agree ---------------------------------


def test_every_script_named_in_the_docs_exists() -> None:
    docs = (ROOT / "docs" / "CLUSTER.md").read_text(encoding="utf-8")
    named = set(re.findall(r"scripts/cluster/([\w.-]+\.sh)", docs))
    assert named, "CLUSTER.md should show how to run something"
    missing = sorted(name for name in named if not (CLUSTER / name).exists())
    assert not missing, f"CLUSTER.md refers to scripts that do not exist: {missing}"


def test_every_model_key_named_in_the_docs_is_in_the_registry() -> None:
    registry = yaml.safe_load(
        (ROOT / "config" / "embedding_models.yml").read_text(encoding="utf-8")
    )
    docs = (ROOT / "docs" / "CLUSTER.md").read_text(encoding="utf-8")
    for key in re.findall(r"UNSC_MODEL=([\w.-]+)", docs):
        assert key in registry["models"], f"CLUSTER.md offers unknown model `{key}`"


def test_slurm_logs_are_not_committed() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "logs/" in ignored


def test_the_gpu_requirements_are_separate_from_the_pinned_pipeline() -> None:
    """Steps 00-09 must stay installable from the hashed lock alone."""
    gpu = (ROOT / "requirements-cluster.txt").read_text(encoding="utf-8")
    assert "torch" in gpu
    assert "spacy" in gpu
    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    assert "torch" not in lock.lower()


# --- Step order ------------------------------------------------------------


def test_embeddings_are_step_06_and_topics_step_07() -> None:
    """07 reads 06's vectors; the reverse numbering would make an earlier step
    depend on a later one."""
    paths = (ROOT / "scripts" / "lib" / "paths.py").read_text(encoding="utf-8")
    assert re.search(r'EMBEDDINGS = DERIVED / "embeddings"\s*#\s*06', paths)
    assert re.search(r'TOPICS = DERIVED / "topics"\s*#\s*07', paths)
    assert (ROOT / "scripts" / "06_embed.py").exists()
    assert (ROOT / "scripts" / "07_topics.py").exists()


#: Everything 07 writes into data/derived/topics/. The dashboard must be unable
#: to reach any of it, and the projection files are the ones most likely to be
#: reached for: a scatter plot of speeches is the single most shippable-looking
#: thing in this repository, and docs/PLAN.md §4 says it is not evidence.
TOPIC_FILES = [
    "nmf.json",
    "embedding.json",
    "evaluation.json",
    "projection.json",
    "projection_year.png",
    "projection_speaker.png",
    "projection_cluster.png",
    "assignments.parquet",
    "intrusion_task.csv",
]


def test_topics_stay_out_of_the_dashboard() -> None:
    """docs/PLAN.md §4 defers topic modelling; 07 produces evaluation evidence,
    not a release artefact, and nothing in web/ may read it."""
    export = (ROOT / "scripts" / "export_web.py").read_text(encoding="utf-8")
    assert "TOPICS" not in export, "export_web.py must not read data/derived/topics"
    assert "EMBEDDINGS" not in export, "the dashboard ships no vectors"
    assert "derived/topics" not in export
    for name in TOPIC_FILES:
        assert name not in export, f"export_web.py must not read {name}"


def test_the_step_writes_every_file_the_guarantee_covers() -> None:
    """The list above is only a guarantee if it is the list of what 07 writes.
    A new artefact that nothing checks is a new artefact nothing protects."""
    step = (ROOT / "scripts" / "07_topics.py").read_text(encoding="utf-8")
    for name in TOPIC_FILES:
        assert name in step, f"07 no longer writes {name} — update TOPIC_FILES"


def test_the_dashboard_never_learns_the_projection_exists() -> None:
    """Asserted over the source the dashboard is built from, not only over the
    exporter: a hand-copied PNG would bypass export_web.py entirely."""
    sources = [
        path
        for path in (ROOT / "web" / "src").rglob("*")
        if path.suffix in {".ts", ".js", ".svelte", ".json", ".html"} and path.is_file()
    ]
    assert sources, "web/src should contain the dashboard"
    for path in sources:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name in ("projection.json", "projection_year.png", "derived/topics"):
            assert name not in text, f"{path.name} reaches {name}"


def test_the_projection_never_becomes_a_column_of_the_assignments_table() -> None:
    """Coordinates joined to a row_id are a map waiting to be drawn by someone
    who never read the note. The parquet carries labels and nothing else."""
    step = (ROOT / "scripts" / "07_topics.py").read_text(encoding="utf-8")
    table = step.split("assignments = pd.DataFrame(", 1)[1].split("\n    )", 1)[0]
    assert "row_id" in table, "the split found the wrong block"
    for name in ("coordinates", "projection", "umap"):
        assert name not in table.lower(), f"the assignments table carries `{name}`"
