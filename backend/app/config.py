"""Central configuration. Everything overridable via environment variables."""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BACKEND_DIR / "data"))

# Assumed time (UK local) by which the day-ahead purchase decision must be taken
# on day D-1. EPEX GB day-ahead auction gate closure is commonly quoted as ~09:20
# UK time; 09:00 leaves a margin. Confirm with the client. Users can override in UI.
DEFAULT_CUTOFF = os.environ.get("DEFAULT_CUTOFF", "09:00")

TIMEZONE = "Europe/London"
