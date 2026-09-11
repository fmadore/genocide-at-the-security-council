"""Restore the checksummed, published semantic map for a clean website build."""

from lib.paths import DERIVED, ROOT
from lib.semantic_release import restore

if __name__ == "__main__":
    restore(ROOT / "config/semantic-release.json", DERIVED / "semantic")
