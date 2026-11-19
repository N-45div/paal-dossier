import sys
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parents[2]
if str(STAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(STAGE_ROOT))
