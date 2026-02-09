"""Entry point for running satellite as a module.

Usage:
    python -m satellite
"""

import multiprocessing
import os

# Force 'spawn' method for multiprocessing BEFORE any other imports.
# This is critical for Python 3.14+ where fork() causes 'bad value(s) in fds_to_keep'
# errors when combined with threading (like Textual's worker threads).
try:
    multiprocessing.set_start_method("spawn", force=True)
except RuntimeError:
    pass  # Already set or not supported

# Disable HuggingFace parallelism to avoid multiprocessing issues
# when running in Textual's threading context on Python 3.14+.
# These MUST be set BEFORE importing any HuggingFace libraries.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_DATASETS_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

from satellite.app import main

if __name__ == "__main__":
    main()
