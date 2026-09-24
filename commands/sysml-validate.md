---
description: Validate SysML v2 models with the OMG Pilot kernel and optionally render diagrams (SVG).
argument-hint: "[path ...] [--viz Qualified::Name[@view]] [--show Qualified::Name]"
allowed-tools: ["Bash", "Read"]
---

Validate SysML v2 / KerML files headlessly and report diagnostics.

Argument handling (`$ARGUMENTS`):
1. Paths (files or directories). Default: `rover_mbse/`. Directories load in sorted
   order, so numbered files resolve their imports.
2. Optional `--viz <name>[@view]` (view ∈ default, tree, interconnection,
   state, action, sequence, mixed) writes SVGs to `rover_mbse/diagrams/`.
3. Optional `--show <name>` prints the element tree.

Process:
1. Run:
   ```bash
   ~/mbse_ws/tools/sysml-env/bin/python .claude/skills/sysml_v2_modeling/scripts/sysml_validate.py \
     <paths> [--viz …] [--show …] --out rover_mbse/diagrams
   ```
2. On exit code `2` (setup problem), print the reinstall recipe from the
   `sysml_v2_modeling` skill (Toolchain) and stop.
3. On exit code `1`, list each `ERROR` as `file:line:col — message`, grouped
   by file. Point out the first error per file, because later ones usually
   follow from it. For errors that match a known pitfall
   (`rules/sysml_v2.md` §5), give the fix.
4. On success, print `PASS` and the files checked, plus any SVGs written.
