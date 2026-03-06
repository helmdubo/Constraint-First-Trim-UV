"""Patch-to-patch relation classification — DOCK / STITCH / IGNORE.

TODO: Implements Layer 2 semantic analysis:
- DOCK: same-type neighbors (WALL+WALL), rigid transform alignment
- STITCH: different-type neighbors (WALL+FLOOR), one-axis alignment only
- IGNORE: too small contact or incompatible types
- BEVEL type detection
- Junction/branching detection (T-junctions)
"""
