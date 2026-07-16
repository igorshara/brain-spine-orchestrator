"""Add ``src`` to sys.path so scenarios run without installation."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
