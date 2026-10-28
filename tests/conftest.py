"""
Pytest configuration and environment fixtures.
Adds project root to sys.path so 'app' is importable in all environments.
"""

import sys
from pathlib import Path

# Add project root directory (fastapi-monitoring) to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

