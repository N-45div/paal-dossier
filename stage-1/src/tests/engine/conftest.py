"""Make the ``dossier`` package under ``src/`` importable from the engine unit tests."""

import pathlib
import sys

SRC = pathlib.Path(__file__).resolve().parents[2]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
