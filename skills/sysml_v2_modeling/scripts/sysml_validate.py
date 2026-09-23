#!/usr/bin/env python3
"""Headless SysML v2 / KerML validator + diagram renderer (OMG Pilot Implementation kernel).

Executes each .sysml/.kerml file as one kernel cell, in order (directories are
expanded sorted, so prefix files 01_, 02_, ... when later files import earlier
packages), and reports parser / name-resolution / typing diagnostics.

Exit code: 0 = no errors, 1 = model errors, 2 = setup problem.

Usage:
  sysml_validate.py PATH [PATH ...]
      [--show QualifiedName]...                 print the element tree
      [--viz QualifiedName[@view]]... [--out DIR]  render SVG diagrams
      [--timeout S]

  view ∈ default|tree|interconnection|state|action|sequence|mixed (default: default)

Env:
  SYSML_ENV      env holding jupyter-sysml-kernel (default ~/mbse_ws/tools/sysml-env)
  SYSML_VERBOSE  print kernel output for passing files too
"""
import argparse
import os
import pathlib
import re
import subprocess
import sys

ENV = pathlib.Path(os.environ.get("SYSML_ENV", pathlib.Path.home() / "mbse_ws/tools/sysml-env"))
ERROR_RE = re.compile(r"^ERROR", re.MULTILINE)
CELL_RE = re.compile(r"\(\d+\.sysml line")


def collect(paths):
    files = []
    for p in map(pathlib.Path, paths):
        if p.is_dir():
            files += sorted(q for q in p.rglob("*") if q.suffix in (".sysml", ".kerml"))
        else:
            files.append(p)
    return files


def run_cell(kc, code, timeout):
    """Execute one cell; return (text output, rich data dict)."""
    msg_id = kc.execute(code, store_history=False)
    out, data = [], {}
    while True:
        msg = kc.get_iopub_msg(timeout=timeout)
        if msg["parent_header"].get("msg_id") != msg_id:
            continue
        kind, content = msg["msg_type"], msg["content"]
        if kind == "stream":
            out.append(content["text"])
        elif kind in ("execute_result", "display_data"):
            data.update(content["data"])
            if "image/svg+xml" not in content["data"]:
                out.append(content["data"].get("text/plain", ""))
        elif kind == "error":
            out.append("ERROR: " + content.get("evalue", "") + "\n")
        elif kind == "status" and content["execution_state"] == "idle":
            return "".join(out), data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--show", action="append", default=[], help="print %%show <name> after loading")
    ap.add_argument("--viz", action="append", default=[], help="render <name>[@view] to SVG")
    ap.add_argument("--out", default=".", help="directory for --viz SVGs")
    ap.add_argument("--timeout", type=float, default=180.0)
    args = ap.parse_args()

    if not (ENV / "share/jupyter/kernels/sysml/kernel.json").exists():
        print(f"SysML kernel not found in {ENV}; see skills/sysml_v2_modeling/SKILL.md (Toolchain).",
              file=sys.stderr)
        return 2
    os.environ["JUPYTER_PATH"] = str(ENV / "share/jupyter")
    os.environ["PATH"] = f"{ENV / 'bin'}:{os.environ['PATH']}"  # graphviz for %viz
    sys.path.insert(0, str(next((ENV / "lib").glob("python3*/site-packages"))))
    from jupyter_client.manager import start_new_kernel  # noqa: E402

    files = collect(args.paths)
    if not files:
        print("no .sysml/.kerml files found", file=sys.stderr)
        return 2

    km, kc = start_new_kernel(kernel_name="sysml", startup_timeout=args.timeout,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    failed = False
    try:
        for f in files:
            text, _ = run_cell(kc, f.read_text(encoding="utf-8"), args.timeout)
            text = CELL_RE.sub(f"({f.name} line", text)
            bad = bool(ERROR_RE.search(text))
            failed |= bad
            print(f"{'FAIL' if bad else 'OK  '} {f}")
            if bad or os.environ.get("SYSML_VERBOSE"):
                print("  " + text.strip().replace("\n", "\n  "))
        for name in args.show:
            print(run_cell(kc, f"%show {name}", args.timeout)[0])
        for spec in args.viz:
            name, _, view = spec.partition("@")
            cmd = f"%viz --view={view} {name}" if view else f"%viz {name}"
            text, data = run_cell(kc, cmd, args.timeout)
            svg = data.get("image/svg+xml")
            if not svg:
                print(f"VIZ FAIL {spec}: {text.strip()}")
                failed = True
                continue
            out = pathlib.Path(args.out) / f"{name.replace('::', '.')}{'.' + view if view else ''}.svg"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(svg, encoding="utf-8")
            print(f"VIZ  {out}")
    finally:
        kc.stop_channels()
        km.shutdown_kernel(now=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
