"""Make the integrations in this repo (and any in HAMLET_EXTRA_COMPONENTS) loadable in tests."""
import os
from pathlib import Path

import pytest_homeassistant_custom_component

_TARGET = Path(pytest_homeassistant_custom_component.__file__).parent / "testing_config" / "custom_components"
_SOURCES = [Path(__file__).parent.parent / "custom_components"]
_SOURCES += [Path(p) for p in os.environ.get("HAMLET_EXTRA_COMPONENTS", "").split(os.pathsep) if p]
for src in _SOURCES:
    for comp in src.glob("hamlet_*"):
        link = _TARGET / comp.name
        if not (link.exists() and link.resolve() == comp.resolve()):
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(comp.resolve(), target_is_directory=True)

