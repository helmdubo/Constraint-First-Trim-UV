# Constraint-First Trim UV (CFTUV)

Blender addon (3.0+) for architectural trim sheet UV mapping.
Constraint-first approach: constraints are established BEFORE the final conformal solve, not applied as corrections after.

Evolved from Hotspot UV addon (v2.4.0 -> v2.5.7).

## Features

- **Two-Pass Unwrap** — pins selected core faces, seamlessly relaxes chamfers
- **Manual Dock** — dock UV islands based on selected boundary edges
- **Select Similar** — select all islands with matching 3D area
- **Stack Similar** — group and perfectly align similar islands with 4-way rotation lock
- **Debug Visualization** — Grease Pencil overlay for patch/frame analysis

## Development Setup (Windows)

### Symlink Install (recommended)

1. Right-click `scripts\install_dev.bat` -> **Run as administrator**
2. Restart Blender
3. **Edit > Preferences > Add-ons** -> search "Hotspot UV" -> enable
4. Panel: **View3D > Sidebar (N) > Hotspot UV**

> **Important:** Do NOT click the "Install" button in Blender Preferences — that is for ZIP files only.
> With the symlink approach the addon appears automatically in the addon list after Blender restart.
> Just search for "Hotspot UV" and enable it.
> After that you can iterate from the local project folder and only use **Refresh Addon** inside the panel to reload scripts.

Default Blender version is 4.1. For a different version, pass it as argument:
```
scripts\install_dev.bat 4.3
```

Changes in code are picked up after **F3 > Reload Scripts**, by pressing **Hotspot UV > Development > Refresh Addon**, or by restarting Blender.

### Build ZIP for Distribution

```
scripts\build_zip.bat
```

Creates `cftuv.zip` ready for **Edit > Preferences > Add-ons > Install**.

### Lint / Syntax Check

```
scripts\lint.bat
```

## Project Structure

```
cftuv/
├── __init__.py              # bl_info, register/unregister
├── config.py                # Globals, settings, validate_edit_mesh
├── analysis/
│   ├── geometry.py          # IslandInfo, find_island_up, calc_surface_basis
│   ├── patches.py           # Seam patches, boundary loops, OUTER/HOLE
│   ├── frame.py             # Corner detection, H_FRAME/V_FRAME classification
│   └── relations.py         # [TODO] DOCK/STITCH/IGNORE
├── solver/
│   ├── orient.py            # orient_scale_and_position_island
│   ├── docking.py           # Manual dock, chain BFS
│   ├── align.py             # Root-anchored island alignment
│   ├── seam_align.py        # Split seam alignment
│   ├── two_pass.py          # [TODO] Extract two-pass pipeline
│   └── frame_solve.py       # [TODO] Frame straighten + pin + conformal
├── operators/               # Blender operators
├── ui/                      # Sidebar panel
└── tests/                   # [TODO] Test meshes
```

See [SPEC.md](SPEC.md) for the full design document.
