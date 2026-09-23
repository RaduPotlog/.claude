---
description: Scaffold a new SysML v2 model (or a new subsystem package set) under mbse/ following the project's layered layout, seeded from the ROS 2 workspace, and validate it.
argument-hint: "<SystemName> [from-workspace|empty]"
allowed-tools: ["Bash", "Read", "Write", "Edit", "Grep", "Glob"]
---

Scaffold a SysML v2 model for a system or subsystem.

Argument handling (`$ARGUMENTS`):
1. `<SystemName>`: PascalCase (e.g. `DockingStation`, `RoverA2`). Required.
   The directory is `mbse/<snake_case_name>/`.
2. `[mode]`: `from-workspace` (default) seeds structure and values from the
   ROS 2 sources. `empty` creates the skeleton only.

If the name is missing, or the directory already exists, ask before acting.

Process:
1. Read the `sysml_v2_modeling` skill and `rules/sysml_v2.md`. Use
   `mbse/rover_a1/` as the reference for layout and idioms.
2. Create five files, one package each, named `<System>_<Layer>`:
   - `01_interfaces.sysml`: `QosProfile`, the `RosTopic` metadata def (or
     `private import RoverA1_Interfaces::*;` to reuse it), `item def`s, and
     `port def`s.
   - `02_structure.sysml`: hardware and software `part def`s, a system
     `part def <System>` holding the composition and flows, a usage
     `part <system> : <System>;`, and allocations.
   - `03_calculations.sysml`: `calc def`s (may start empty with a `doc`).
   - `04_requirements.sysml`: a requirement spec group plus `satisfy`, status
     BASELINE.
   - `05_analysis.sysml`: at least one `analysis def` and one
     `verification def` tied to the requirements.
3. For `from-workspace`: pull values from their source files (see the skill,
   "Deriving model content"). Cite each source in a `doc`. Mark unknowns
   `TBD`. Never invent numbers.
4. Validate with `/sysml-validate mbse/<name>` and fix until it passes.
5. Render the structure interconnection view into `mbse/diagrams/`.
6. Run the `sysml-reviewer` agent on the new directory and address its
   Must-fix items.
7. Print a summary: files created, element counts (parts, ports, flows,
   requirements), open `TBD`s, and next steps (e.g. `system_composer_sysml`
   pipeline A once MATLAB is connected).
