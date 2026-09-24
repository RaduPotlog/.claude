---
name: system_composer_sysml
description: Connect SysML v2 models to MATLAB / Simulink / System Composer through the MATLAB MCP Server and the Simulink Agentic Toolkit — build a System Composer architecture from the SysML v2 model, export MATLAB projects to SysML v2, run requirement analyses in MATLAB/Simulink, and link requirements with Requirements Toolbox. Trigger when the user asks to use MATLAB, Simulink, Simscape or System Composer with a SysML model, or to evaluate a SysML analysis numerically.
---

# System Composer ↔ SysML v2 (via the MATLAB MCP)

- Capability matrix, setup, API names, mapping table: `rules/matlab_simulink_mbse.md`.
- SysML v2 side: `rules/sysml_v2.md` + skill `sysml_v2_modeling`.
- Model sources: `rover_a1/rover_mbse/rover_a1/*.sysml`. MATLAB artifacts: `rover_a1/rover_mbse/matlab/`.

## Preflight (every session)

1. Check that the `matlab` MCP server is connected (tools `mcp__matlab__*`, e.g.
   `detect_matlab_toolboxes`; project `.mcp.json`, approved at session start). If not, point the user to
   `rules/matlab_simulink_mbse.md` §3 and stop. Nothing below works without it.
2. Call `detect_matlab_toolboxes`. Check the release (**R2026a+** for
   `systemcomposer.sysml.*`) and the toolboxes the task needs (System Composer,
   Requirements Toolbox, Simulink Test, Simscape). Report what is missing
   instead of working around it.
3. Validate the SysML source first (`/sysml-validate rover_mbse/rover_a1`). MATLAB
   work always starts from a clean model.

## First decision: which direction?

| Goal | Pipeline (`matlab_simulink_mbse.md` §4) |
|------|------------------------------------------|
| Architecture model / Simulink behaviour **from** the SysML model | **A**: `sysml_to_syscomp.py` → generated `build_architecture.m` → run via MCP |
| SysML text **from** an existing MATLAB project | **B**: `systemcomposer.sysml.exportFromMLProject` → validate → diff |
| Numbers for an `analysis def` / `calc def` | **C**: MATLAB function / Simulink model mirroring the calc |
| Requirements traceability in MATLAB | `slreq` requirement set generated from `04_requirements` + links |

## A. Build the architecture from SysML

1. `/sysml-validate rover_mbse/<system>` — must pass.
2. Generate (re-run after every SysML change):
   ```bash
   python3 .claude/skills/system_composer_sysml/scripts/sysml_to_syscomp.py \
     rover_mbse/rover_a1 --root RoverA1 --out rover_mbse/matlab/build_architecture.m
   ```
   It maps item defs→interfaces (with units), ports→ports (conjugated = in),
   parts→nested components (`drive[4]` → `drive_1..4`), numeric attributes→
   component parameters, flows→connectors (+ `RosTopic` stereotype, routed via
   `<child>_<port>` boundary ports), interface links→connectors,
   allocate→allocation set. Never hand-edit its output.
3. Build: `evaluate_matlab_code(project_path="\\wsl.localhost\Ubuntu\home\rover-a1\ros2_ws\rover_a1\mbse\matlab", code="build_architecture")`.
4. Verify with the toolkit: `model_overview` (model = `…\mbse\matlab\arch\RoverA1Arch.slx`,
   detail `interfaces`) — component/port counts must match the generator's summary line —
   and `model_check`. Unconnected ports usually mean a missing SysML flow: fix the
   **SysML**, then regenerate.

## B. Export MATLAB → SysML v2

`evaluate_matlab_code(project_path=<mbse\matlab>, code="export_sysml")` →
`rover_mbse/export/rover_a1_export.sysml`, then `/sysml-validate rover_mbse/export`.
Compare structure (parts/ports/connectors) with `rover_mbse/rover_a1`; expect the
losses listed in `rules/matlab_simulink_mbse.md` §4B. Report differences, never
overwrite the hand-written model.

## C. Evaluate an analysis

1. Extend `rover_mbse/matlab/analysis_rover_a1.m`: read inputs with
   `pget(model, "<component path>", "<parameter>")` (values come from SysML via
   the architecture — never re-type numbers), mirror the SysML `calc def` in
   MATLAB, evaluate the objective's constraint.
2. Where dynamics matter, build a Simulink twin with a `build_<name>_sim.m`
   script (pattern: `build_endurance_sim.m`), drive it with
   `Simulink.SimulationInput` variables, compare against the ideal calc.
3. `check_matlab_code` the scripts, then run
   `evaluate_matlab_code(code="analysis_rover_a1")` → `results/analysis_results.json`.
4. Write value, verdict, margin, MATLAB release and date into the analysis
   `doc`; re-validate the `.sysml`.

## D. Requirements Toolbox

Generate `rover_mbse/matlab/build_requirements.m`: `slreq.new("RoverA1Reqs")`, one
requirement per `requirement def` (ID = the `<'R-…'>` short name, description
= its `doc`), then `slreq.createLink` from components (satisfy) and from test
or analysis files (verify).

## Common pitfalls

- Windows MATLAB sees WSL files through `\\wsl.localhost\Ubuntu\…`. Relative
  paths resolve against `--initial-working-folder`.
- Units: SysML values are SI. Keep MATLAB variables in SI and name them with
  their unit (`capacity_Ah` is fine when the conversion is explicit).
- Do not hand-edit `.slx`. Use `model_edit` or the generated scripts.
- SysML v2 → System Composer has **no** native import (R2026a). Pipeline A is
  a generated script, so say so to the user.
