from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from product_support_agent.config import get_settings
from product_support_agent.core.bootstrap import bootstrap_application
from product_support_agent.ui.layout import render_app


def main() -> None:
    settings = get_settings()
    bootstrap_application(settings)
    render_app(settings)


if __name__ == "__main__":
    main()
