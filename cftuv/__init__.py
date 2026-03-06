"""Constraint-First Trim UV (CFTUV) — Blender addon for architectural trim sheet UV mapping.

bl_info, register/unregister, and top-level imports.
"""

bl_info = {
    "name": "Constraint-First Trim UV",
    "author": "",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > CFTUV",
    "description": "Constraint-first UV mapping for architectural trim sheets",
    "category": "UV",
}

from . import config  # noqa: F401, E402
from . import analysis  # noqa: F401, E402
from . import solver  # noqa: F401, E402
from . import operators  # noqa: F401, E402
from . import ui  # noqa: F401, E402


def register():
    """Register all addon classes with Blender."""
    pass


def unregister():
    """Unregister all addon classes from Blender."""
    pass
