import os
import sys
from pathlib import Path

import django

PROJECT_ROOT_DIR = Path(os.path.abspath(__file__)).parents[1]

DJANGO_ROOT_DIR = PROJECT_ROOT_DIR / "sap"


def django_setup() -> None:
   
    sys.path.append(DJANGO_ROOT_DIR.as_posix())
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "sap.settings"
    )

    django.setup()
    