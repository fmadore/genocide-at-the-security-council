"""Restore the checksummed, published semantic map for a clean website build."""

from lib.paths import SEMANTIC, SEMANTIC_PIN
from lib.semantic_release import restore

if __name__ == "__main__":
    restore(SEMANTIC_PIN, SEMANTIC)
