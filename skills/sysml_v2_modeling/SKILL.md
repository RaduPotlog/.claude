---
name: sysml_v2_modeling
description: Write, extend, validate and render SysML v2 textual models (structure, ports/flows, requirements, calculations, analysis and verification cases, allocation, variability) and derive them from the ROS 2 workspace. Validates headlessly with the OMG Pilot kernel. Trigger when the user asks for a SysML / SysML v2 / MBSE model, requirement traceability, a system architecture model, or a model-based analysis of the rover.
---

# SysML v2 Modeling

Write **SysML v2 text** models that validate cleanly and trace back to the
real system.

- Language reference, conventions, ROS 2 mapping, pitfalls: `rules/sysml_v2.md`.
- MATLAB / System Composer side: `rules/matlab_simulink_mbse.md` + skill
  `system_composer_sysml`.
- OMG training examples, one per concept: `~/mbse_ws/ref/SysML-v2-Release/sysml/src/training/`.
- **Reference model** (studied first, then extended): `rover_a1/rover_mbse/rover_a1/`.
- Validator + renderer: `scripts/sysml_validate.py` (this skill folder).

## Toolchain

Already installed on this box:
- Pilot kernel **0.62.0** in the conda env `~/mbse_ws/tools/sysml-env` (Java 21+
  required; this box has 25).
- Spec + library clone: `~/mbse_ws/ref/SysML-v2-Release` (tag `2026-08`).

Reinstall (no conda needed):
```bash
mkdir -p ~/mbse_ws/tools && cd ~/mbse_ws/tools
curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj bin/micromamba
MAMBA_ROOT_PREFIX=~/mbse_ws/tools/mamba ./bin/micromamba create -y -p ~/mbse_ws/tools/sysml-env \
  -c conda-forge "jupyter-sysml-kernel=0.62.0" python=3.12 jupyter_client jupyter_console graphviz
```
When upgrading, match the kernel version to the `SYSML_VERSION` in the
release's `install/jupyter/install.sh`.

Run:
```bash
PY=~/mbse_ws/tools/sysml-env/bin/python
V=.claude/skills/sysml_v2_modeling/scripts/sysml_validate.py
$PY $V rover_mbse/rover_a1                                   # validate (dir = sorted order)
$PY $V rover_mbse/rover_a1 --show RoverA1_Structure::RoverA1 # element tree
$PY $V rover_mbse/rover_a1 --viz RoverA1_Structure::RoverA1@interconnection --out rover_mbse/diagrams
```
Exit codes: `0` clean, `1` model errors (`FAIL file` + `ERROR: … (file line : L column : C)`),
`2` setup problem. Views for `--viz`: `default`, `tree`, `interconnection`,
`state`, `action`, `sequence`, `mixed`.

## First decision: what are you adding?

| Request | Put it in | Pattern (see `rules/sysml_v2.md` §1–2) |
|---------|-----------|----------------------------------------|
| New message / topic / hardware link | `01_interfaces` | `item def` + `port def`; `@RosTopic` on the flow |
| New node, container, board, sensor | `02_structure` | `part def` + ports; compose it inside `part def RoverA1`; `flow`s; `allocate` |
| Formula (energy, speed, load) | `03_calculations` | `calc def` with typed `in`s and `return` |
| "The rover shall …" | `04_requirements` | `requirement def <'R-AREA-NN'>` + usage in the spec group |
| "Does it meet …?" / trade study | `05_analysis` | `analysis def` (objective `require …`) or `TradeStudies` |
| Test procedure | `05_analysis` | `verification def` (objective `verify …`, `PassIf`) |
| New system (not the rover) | `rover_mbse/<system>/` | use `/new-sysml-model` |

## Deriving model content from the workspace

1. Find facts in their source files, not in READMEs (READMEs go stale). In
   order of trust: controller/nav yaml → URDF/xacro → launch → README.
   - Kinematics / mass: `src/rover_ros/rover_description/{config,urdf}`
   - Drive limits / rates: `src/rover_ros/rover_controller/config/*.yaml`
   - Nav 2 limits / footprint: `src/rover_orchestrator/rover_navigation/config/rover_nav_params.yaml`
   - Safety thresholds: `src/rover_ros/rover_safety/config/rover_safety.yaml`
   - Containers: `rover_docker/docker-compose.yml`
   - Topics: grep `create_publisher|create_subscription` and the twist_mux yaml.
2. Model **only what the analysis or traceability needs**. An `item def` gets
   the fields that requirements or calcs use, not the full message.
3. Cite the source file in a `doc`. Mark unknowns `TBD:` and assumptions
   `ASSUMPTION`.

## Step by step

1. Read `rules/sysml_v2.md` and the existing packages you will touch.
2. Find the closest training example (`training/NN. <Concept>/`) and copy its
   syntax.
3. Edit the right numbered file, one package per file, `private import` only.
4. Validate. Fix errors top-down: the first syntax error causes the ones after it.
5. For requirements: add the usage to the spec group, make sure `satisfy`
   covers it, and add or extend an analysis or verification case that
   `require`s or `verify`s it.
6. Put the hand calculation (or MATLAB result + date) for each analysis in its
   `doc`.
7. Render the changed view with `--viz` if it helps a review, into
   `rover_mbse/diagrams/`.
8. Before handing off, run the `sysml-reviewer` agent on the diff.

## Common pitfalls

See `rules/sysml_v2.md` §5. The ones hit most often: reserved words as names
(`frame`, `event`, `message`), subject shadowing in requirement groups,
composition declared in the usage instead of the def, and missing
`private import SI::*;`.
