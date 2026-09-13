"""
Change coupling mined from git history.

Each test builds a small repository with a deliberate commit pattern, so the
expected coupling is known rather than inferred.
"""

import subprocess

import pytest

from epicenter.cochange import analyze_history, ingest_history
from epicenter import CodeGraph
from epicenter.pipeline import ingest_codebase


def git(root, *args):
    subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, capture_output=True, text=True,
    )


@pytest.fixture
def repo(tmp_path):
    """A git repository whose commits are written one at a time."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "Test")

    def commit(files, message="change"):
        for name, source in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", message)
        return root

    commit.root = root
    return commit


def test_symbols_changed_together_are_coupled(repo):
    """alpha and gamma are edited in the same three commits; beta is not."""
    base = {
        "mod.py": "def alpha():\n    return 1\n\n\ndef beta():\n    return 2\n",
        "other.py": "def gamma():\n    return 3\n",
    }
    repo(base, "initial")
    for n in range(3):
        repo({
            "mod.py": f"def alpha():\n    return {n + 10}\n\n\ndef beta():\n    return 2\n",
            "other.py": f"def gamma():\n    return {n + 20}\n",
        }, f"edit {n}")

    pairs, counts, examined = analyze_history(str(repo.root))
    assert examined >= 3
    assert pairs[("mod.alpha", "other.gamma")] >= 3
    assert counts["mod.beta"] == 1        # only the initial commit


def test_enclosing_class_is_not_coupled_to_its_own_method(repo):
    """A class's span covers its methods, so attributing a change to every
    enclosing symbol would couple each class to its own members every time."""
    repo({"mod.py": "class Thing:\n    def run(self):\n        return 1\n"}, "initial")
    repo({"mod.py": "class Thing:\n    def run(self):\n        return 2\n"}, "edit")

    pairs, _, _ = analyze_history(str(repo.root))
    assert ("mod.Thing", "mod.Thing.run") not in pairs


def test_confidence_is_share_of_the_symbol_s_own_commits(repo, tmp_path):
    repo({
        "mod.py": "def alpha():\n    return 1\n",
        "other.py": "def gamma():\n    return 1\n",
    }, "initial")
    repo({
        "mod.py": "def alpha():\n    return 2\n",
        "other.py": "def gamma():\n    return 2\n",
    }, "together")
    repo({"mod.py": "def alpha():\n    return 3\n"}, "alpha alone")

    db = tmp_path / "hist.db"
    ingest_codebase(str(repo.root), db_path=str(db))
    ingest_history(str(repo.root), db_path=str(db))

    graph = CodeGraph(db_path=str(db), realm=str(repo.root))
    coupled = graph.coupled_with("mod.alpha", min_together=1, min_confidence=0.0)
    gamma = next(c for c in coupled if c["symbol"] == "other.gamma")

    # alpha changed in 3 commits, 2 of which also touched gamma.
    assert gamma["of_commits"] == 3
    assert gamma["together"] == 2
    assert gamma["confidence"] == pytest.approx(2 / 3)


def test_coupling_without_a_code_path_is_flagged(repo, tmp_path):
    """The whole point: coupled in practice, invisible to the call graph."""
    for n in range(3):
        repo({
            "encoder.py": f"def encode(x):\n    return x + {n}\n",
            "decoder.py": f"def decode(x):\n    return x - {n}\n",
        }, f"format {n}")

    db = tmp_path / "hist.db"
    ingest_codebase(str(repo.root), db_path=str(db))
    ingest_history(str(repo.root), db_path=str(db))

    graph = CodeGraph(db_path=str(db), realm=str(repo.root))
    coupled = graph.coupled_with("encoder.encode", min_together=2, min_confidence=0.5)
    decode = next(c for c in coupled if c["symbol"] == "decoder.decode")

    assert decode["structural"] is False    # neither calls the other
    assert decode["together"] == 3


def test_module_level_change_is_attributed_to_the_module(repo):
    """Editing a constant touches no function's span, but it is a real change
    and belongs to the module — a config key and its reader is precisely the
    coupling worth catching."""
    repo({"settings.py": "TIMEOUT = 1\n\n\ndef load():\n    return TIMEOUT\n"}, "initial")
    repo({"settings.py": "TIMEOUT = 2\n\n\ndef load():\n    return TIMEOUT\n"}, "bump")

    _, counts, _ = analyze_history(str(repo.root))
    assert counts["settings"] >= 1


def test_directory_outside_any_repository_has_no_history(project):
    root = project({"mod.py": "def alpha(): ...\n"}, name="loose")
    assert analyze_history(str(root)) is None


def test_untracked_directory_inside_a_repository_has_no_history(repo):
    """A realm can sit inside an unrelated repository — a library vendored
    under .venv — where git happily reports the enclosing project's history."""
    repo({"mod.py": "def alpha(): ...\n"}, "initial")

    vendored = repo.root / "vendor_dir"
    vendored.mkdir()
    (vendored / "lib.py").write_text("def library_thing(): ...\n")
    (repo.root / ".gitignore").write_text("vendor_dir/\n")
    git(repo.root, "add", "-A")
    git(repo.root, "commit", "-q", "-m", "ignore vendor")

    assert analyze_history(str(vendored)) is None
