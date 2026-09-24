---
description: "MATLAB / Simulink / System Composer MBSE Reference"
paths:
  - "rover_mbse/**"
  - "**/*.sysml"
  - "**/*.kerml"
  - "**/*.m"
  - "**/*.slx"
  - "**/*.sldd"
---

# MATLAB / Simulink / System Composer MBSE Reference

How Claude works with **MATLAB, Simulink and System Composer** for model-based
systems engineering, and how that connects to SysML v2 text models
(`sysml_v2.md`). Sources: MathWorks docs and the official agentic repos listed
below (checked 2026-09-23). Re-check release-gated items after upgrading MATLAB.

## 1. Components

| Component | Repo / product | Gives Claude | Requires |
|-----------|----------------|--------------|----------|
| **MATLAB MCP Server** | `github.com/matlab/matlab-mcp-server` | MCP tools `detect_matlab_toolboxes`, `check_matlab_code`, `evaluate_matlab_code`, `run_matlab_file`, `run_matlab_test_file` | MATLAB **R2021a+** |
| **Simulink Agentic Toolkit** | `github.com/matlab/simulink-agentic-toolkit` | MCP tools `model_overview`, `model_read`, `model_edit`, `model_check`, `model_read_diagnostics`, `model_test` (Gherkin, needs Simulink Test), `model_query_params`, `model_resolve_params`, `model_scan`, plus 10 skill groups including `model-based-system-engineering` (System Composer) | MATLAB **R2023a+** + Simulink; per-skill toolboxes are listed in each skill's `manifest.yaml` |
| MATLAB Agentic Toolkit | `github.com/matlab/matlab-agentic-toolkit` | MATLAB coding skills | MATLAB MCP Server |
| simulink/skills | `github.com/simulink/skills` | community Simulink skill folders ("Guy on Simulink") | review before vendoring |
| **System Composer ↔ SysML v2** | `systemcomposer.sysml.*` | export a MATLAB project to `.sysml`, and **read-only** query of a SysML v2 API repository | MATLAB **R2026a+**, System Composer |
| SysML Connector | MathWorks add-on | SysML **1.x** XMI import (not v2) | — |

## 2. Release capability matrix

| Capability | Minimum release |
|------------|-----------------|
| MATLAB MCP Server | R2021a |
| Simulink Agentic Toolkit | R2023a |
| `systemcomposer.sysml.exportFromMLProject(prj, "out.sysml")` | **R2026a** |
| `systemcomposer.sysml.Repository.connect(url[, credentials=…])` → `getProjects` / `getProjectById` → `createWorkspace` → `getElements`, `getRootElements`, `getElementRelationships`, `getElementsByTypeAndName`, `executeQuery`, `getOwnershipHierarchy`, `getUsages`, … | **R2026a** |
| Direct import of SysML v2 into a System Composer architecture | **not available** (as of R2026a docs). Build it with a script (§4A). |

**Recommended install for this workspace:** R2026a or later on Windows, with
MATLAB, Simulink, **System Composer**, **Requirements Toolbox**, Simulink Test,
Stateflow, Simscape (+ Simscape Electrical for battery/motor models).

## 3. Setup on this WSL box (done 2026-09-23 — MATLAB R2026a Update 5 on Windows)

The toolkit's **automated** installer (`setupAgenticToolkit`) runs inside Windows
MATLAB and would configure a *Windows* Claude (`%USERPROFILE%\.claude.json`),
not WSL Claude Code, so the **manual** path was used and wired to WSL:

| Piece | Where |
|-------|-------|
| MCP server v0.13.1 | `C:\Users\potlo\.matlab\agentic-toolkits\bin\matlab-mcp-server.exe` (+ `--setup-matlab` run once against R2026a) |
| Simulink Agentic Toolkit `SATK-2026.09.c` | `C:\Users\potlo\.matlab\agentic-toolkits\simulink` (git clone, pinned tag) |
| MCP registration | `rover_a1/.mcp.json` (project scope) — Windows exe via WSL interop, `--matlab-session-mode=auto`, `--extension-file=…\simulink\tools\tools.json`, `--disable-telemetry=true`, logs in `…\agentic-toolkits\logs` |
| Toolkit skills | Claude plugins from marketplace `matlab/simulink-agentic-toolkit#SATK-2026.09.c`, project scope (`.claude/settings.json` → `enabledPlugins`): model-based-design-core, model-based-system-engineering, verification-validation-and-test, simulink-simulation, physical-modeling, control-systems, simulink-environment-fundamentals |
| MATLAB init | `C:\Users\potlo\Documents\MATLAB\startup.m` → `satk_initialize` (skipped for `-batch`) |

Tools exposed (14): `check_matlab_code`, `detect_matlab_toolboxes`,
`evaluate_matlab_code`, `run_matlab_file`, `run_matlab_test_file` +
`model_overview`, `model_read`, `model_edit`, `model_check`,
`model_read_diagnostics`, `model_query_params`, `model_resolve_params`,
`model_scan`, `model_test`.

**Session behaviour (observed):**
- `auto` mode attaches to a MATLAB that ran `satk_initialize` (i.e. one the
  user opened — `startup.m` does it); otherwise it **starts a new desktop
  MATLAB** (~60 s) that exits when the MCP server stops.
- Paths: MATLAB is Windows. Pass WSL files as `\\wsl.localhost\Ubuntu\home\…`
  (`evaluate_matlab_code` `project_path`, `run_matlab_file` `script_path`).
  Saving `.slx/.sldd/.mldatx` there works (harmless "change notification" warning).
- A tool returning `no response messages received` = the attached MATLAB is
  blocked (modal dialog) or hung. Ask the user to look at the MATLAB window.
  Only kill MATLAB processes the agent itself started (check `StartTime`).
- Update later: `git -C …\simulink fetch --tags && checkout <new tag>`, bump the
  marketplace ref, download the new exe. Trial licenses expire — check
  `detect_matlab_toolboxes` when tools start failing.

## 4. Round-trip pipelines (all three verified 2026-09-23)

**A. SysML v2 text → System Composer** (SysML is the source of truth)
```bash
python3 .claude/skills/system_composer_sysml/scripts/sysml_to_syscomp.py \
  rover_mbse/rover_a1 --root RoverA1 --out rover_mbse/matlab/build_architecture.m
```
then `evaluate_matlab_code(project_path=<mbse\matlab>, code="build_architecture")`.
Generated, idempotent: `arch/RoverA1Arch.slx` (components + parameters with
units), `RoverA1Interfaces.sldd`, `RoverProfile.xml` (`RosTopic` connector
stereotype), `RoverA1Alloc.mldatx`. Cross-hierarchy flows are routed through
generated boundary ports named `<child>_<port>`. Check with `model_overview` /
`model_check`. (A SysML v2 API server + `systemcomposer.sysml.Repository` is an
alternative source, not needed for local models.)

**B. MATLAB project → SysML v2 text**: `rover_mbse/matlab/export_sysml.m` wraps the
artifacts in `RoverA1.prj` (the `arch/` folder **must be on the project path**)
and calls `exportFromMLProject` → `rover_mbse/export/rover_a1_export.sysml`, which
passes `/sysml-validate`. The export is **lossy**: keeps parts, ports, all
connectors, parameters, `RosTopic` metadata, allocations; drops units/quantity
types (all `Real`), turns items→port defs and flows→`connect`, and has **no
requirements, analyses, verifications or provenance docs**. Use it for diffs
only; never overwrite `rover_mbse/rover_a1/`.

**C. Analysis:** `rover_mbse/matlab/analysis_rover_a1.m` reads inputs from the
System Composer **parameters** (never re-typed numbers), evaluates each SysML
calc/analysis/verification case, runs the Simulink twin
(`build_endurance_sim.m` → `EnduranceSim.slx`), and writes
`results/analysis_results.json`. Results go back into the analysis `doc`
(value, margin, release, date) and the `.sysml` is re-validated.

## 5. SysML v2 ↔ System Composer mapping

| SysML v2 | System Composer / MATLAB | API |
|----------|--------------------------|-----|
| `package` | architecture model / data dictionary | `systemcomposer.createModel` |
| `part def` / `part` | component (optionally linked to a Simulink behaviour model) | `addComponent`, `linkToModel` |
| numeric `attribute` | component parameter | `addParameter(comp.Architecture, name, Value="0.1651", Units="m")`; read back `getParameter(name).Value` |
| `port def` + `port` | architecture port + interface | `addPort`, `setInterface` |
| `item def` attributes | interface elements in an interface dictionary | `systemcomposer.createDictionary`, `addInterface`, `addElement` |
| `flow` / `connect` | connector | `connect` |
| `metadata def` (`@RosTopic`) | profile stereotype + properties | `systemcomposer.profile.Profile.createProfile`, `addStereotype`, `applyStereotype` |
| `requirement` + `satisfy` / `verify` | Requirements Toolbox requirement + link | `slreq.new`, `add`, `slreq.createLink` |
| `calc def` / `analysis def` | analysis function over an instance model | `instantiate`, `iterate` |
| `allocate` | allocation set (same model OK) | `createAllocationSet(name, mdl, mdl)` → `as.Scenarios(1)` → `allocate(sc, src, dst)` (no `getDefaultScenario` in R2026a) |
| `state def` | Stateflow chart | — |

## 6. Rules for Claude

- Use the **MCP tools**. Never regex-edit `.slx` / `.sldd` files. Read with
  `model_read` / `model_overview`, edit with `model_edit`, then run
  `model_check`.
- Generated MATLAB code goes in `rover_mbse/matlab/` as **scripts or functions**, so it can be
  re-run and diffed. Close models with `close_system(m, 0)`, dictionaries with
  `Simulink.data.dictionary.closeAll('-discard')` — a "save changes?" dialog
  blocks the MCP session. Run `check_matlab_code` on each one before running it.
- Do not claim SysML v2 import exists in System Composer. It is export plus
  read-only repository access (§2).
- If `detect_matlab_toolboxes` does not list a needed toolbox, stop and report
  it. Do not work around it.
