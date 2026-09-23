#!/usr/bin/env python3
"""Generate a System Composer build script (MATLAB) from a SysML v2 model.

Pipeline A of rules/matlab_simulink_mbse.md. Reads the convention-constrained
subset used in mbse/<system>/ (see rules/sysml_v2.md §3):

  item def  (+ typed attributes)        -> interface dictionary interface (+ elements, units)
  port def  (in/out/inout item)         -> port direction + interface
  part def  (ports, parts, attributes)  -> component (+ parameters with units), nested
  flow of T from a.p.i to b.q.j {@RosTopic}-> connector (+ RosTopic stereotype), routed
                                           through parent boundary ports when needed
  interface : D connect a.p to b.q       -> connector
  allocate x to y                        -> allocation set (same model)

Every composition is auto-arranged (addComponent stacks children at one spot).

Validate the model first (/sysml-validate); this parser assumes it is valid.

Usage:
  sysml_to_syscomp.py MODEL_DIR --root RoverA1 --out mbse/matlab/build_architecture.m
      [--name RoverA1]   prefix for generated artifacts (default: --root)
"""
import argparse
import pathlib
import re
import sys

UNITS = {  # ISQ quantity type -> Simulink unit string
    "LengthValue": "m", "SpeedValue": "m/s", "AccelerationValue": "m/s^2",
    "AngularVelocityValue": "rad/s", "AngularMeasureValue": "rad", "MassValue": "kg",
    "DurationValue": "s", "FrequencyValue": "Hz", "ElectricCurrentValue": "A",
    "ElectricPotentialValue": "V", "ElectricChargeValue": "A*h", "PowerValue": "W",
    "ThermodynamicTemperatureValue": "K", "Real": "", "Integer": "", "Boolean": "",
}
UNIT_LITERAL = {"A*h": "A*h", "m/s^2": "m/s^2"}


# ----------------------------------------------------------------- parsing
def strip_comments(text):
    text = re.sub(r"\bdoc\s*/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def statements(body):
    """Split a body into depth-0 statements: (head, block_or_None)."""
    out, i, n, start = [], 0, len(body), 0
    while i < n:
        ch = body[i]
        if ch == ";":
            head = body[start:i].strip()
            if head:
                out.append((head, None))
            start = i + 1
        elif ch == "{":
            depth, j = 1, i + 1
            while depth:
                depth += {"{": 1, "}": -1}.get(body[j], 0)
                j += 1
            out.append((body[start:i].strip(), body[i + 1:j - 1]))
            i, start = j - 1, j
        i += 1
    tail = body[start:].strip()
    if tail:
        out.append((tail, None))
    return out


class Model:
    def __init__(self):
        self.items, self.port_defs, self.part_defs, self.allocs = {}, {}, {}, []

    def load(self, text):
        for head, block in statements(strip_comments(text)):
            m = re.match(r"package\s+(\w+)", head)
            if m and block is not None:
                self._package(block)

    def _package(self, body):
        for head, block in statements(body):
            if m := re.match(r"item def (\w+)", head):
                attrs = []
                for h, _ in statements(block or ""):
                    if a := re.match(r"attribute (\w+)\s*:\s*([\w:]+)", h):
                        attrs.append((a[1], a[2].split("::")[-1]))
                self.items[m[1]] = attrs
            elif m := re.match(r"port def (\w+)", head):
                items = []
                for h, _ in statements(block or ""):
                    if a := re.match(r"(in|out|inout) item (\w+)\s*:\s*(\w+)", h):
                        items.append((a[1], a[2], a[3]))
                self.port_defs[m[1]] = items
            elif m := re.match(r"part def (\w+)", head):
                self.part_defs[m[1]] = self._part_def(block or "")
            elif m := re.search(r"allocate\s+[\w]+\.([\w.]+)\s+to\s+[\w]+\.([\w.]+)", head):
                self.allocs.append((m[1], m[2]))

    def _part_def(self, body):
        d = {"ports": [], "parts": [], "attrs": [], "flows": [], "links": []}
        for head, block in statements(body):
            if m := re.match(r"port (\w+)(?:\[(\d+)\])?\s*:\s*(~?)(\w+)$", head):
                d["ports"].append((m[1], int(m[2] or 1), m[3] == "~", m[4]))
            elif m := re.match(r"part (\w+)(?:\[(\d+)\])?\s*:\s*(\w+)$", head):
                d["parts"].append((m[1], int(m[2] or 1), m[3]))
            elif m := re.match(r"attribute (\w+)\s*:\s*([\w:]+)\s*=\s*([-+0-9.eE]+)\s*(?:\[([^\]]+)\])?$", head):
                d["attrs"].append((m[1], m[3], (m[4] or "").strip()))
            elif m := re.match(r"flow of (\w+) from ([\w.]+) to ([\w.]+)$", head):
                meta = {}
                if block:
                    for k, v in re.findall(r"(\w+)\s*=\s*(\"[^\"]*\"|[\w:]+)\s*;", block):
                        meta[k] = v.strip('"').split("::")[-1]
                d["flows"].append((m[1], m[2], m[3], meta))
            elif m := re.match(r"interface\s*:\s*(\w+)\s+connect ([\w.]+) to ([\w.]+)$", head):
                d["links"].append((m[1], m[2], m[3]))
        return d


# ----------------------------------------------------------------- component tree
class Comp:
    def __init__(self, name, typ, parent):
        self.name, self.typ, self.parent, self.children = name, typ, parent, {}
        self.ports = {}  # name -> [direction, interface]

    @property
    def path(self):
        return [] if self.parent is None else self.parent.path + [self.name]

    def var(self):
        return "arch" if self.parent is None else "c_" + "_".join(self.path)


def build_tree(model, root_type):
    root = Comp(root_type, root_type, None)

    def expand(comp):
        d = model.part_defs.get(comp.typ)
        if not d:
            return
        for pname, mult, conj, pdef in d["ports"]:
            items = model.port_defs.get(pdef, [])
            direction, iface = "inout", None
            if items:
                dirn, _, iface = items[0]
                direction = {"out": "in", "in": "out"}.get(dirn, dirn) if conj else dirn
            for k in range(mult):
                comp.ports[pname if mult == 1 else f"{pname}_{k + 1}"] = [direction, iface]
        for name, mult, typ in d["parts"]:
            for k in range(mult):
                child = Comp(name if mult == 1 else f"{name}_{k + 1}", typ, comp)
                comp.children[child.name] = child
                expand(child)

    expand(root)
    return root


def resolve(root, dotted):
    """a.b.port.item -> list of (comp, portName); expands multiplicity."""
    segs, cur = dotted.split("."), [root]
    for i, s in enumerate(segs):
        nxt = []
        for c in cur:
            if s in c.children:
                nxt.append(c.children[s])
            else:
                multi = sorted((k for k in c.children if re.fullmatch(rf"{s}_\d+", k)),
                               key=lambda k: int(k.rsplit("_", 1)[1]))
                nxt += [c.children[k] for k in multi]
        if nxt:
            cur = nxt
            continue
        out = []  # s is a port on every comp in cur
        for c in cur:
            if s in c.ports:
                out.append((c, s))
            else:
                multi = sorted((k for k in c.ports if re.fullmatch(rf"{s}_\d+", k)),
                               key=lambda k: int(k.rsplit("_", 1)[1]))
                out += [(c, k) for k in multi]
        if not out:
            raise SystemExit(f"cannot resolve '{dotted}' at '{s}'")
        return out
    raise SystemExit(f"'{dotted}' names a part, not a port")


# ----------------------------------------------------------------- emit MATLAB
def q(s):
    return '"' + s.replace('"', '""') + '"'


def emit(model, root, name, src_dir):
    L = []
    w = L.append
    rootdef = model.part_defs[root.typ]
    w(f"%% build_architecture.m — GENERATED from SysML v2 ({src_dir}) by")
    w("%% .claude/skills/system_composer_sysml/scripts/sysml_to_syscomp.py. Do not edit; re-generate.")
    w("%% Builds <name>Arch.slx + <name>Interfaces.sldd + RoverProfile.xml + <name>Alloc.mldatx in ./arch")
    w("function build_architecture()")
    w("here = fileparts(mfilename('fullpath')); out = fullfile(here, 'arch');")
    w("if ~isfolder(out), mkdir(out); end")
    w("old = cd(out); cleanup = onCleanup(@() cd(old));")
    w(f"mdl = {q(name + 'Arch')}; dd = {q(name + 'Interfaces.sldd')}; prof = \"RoverProfile\"; aset = {q(name + 'Alloc')};")
    w("% --- idempotent: close + delete previous artifacts without dialogs")
    w("if bdIsLoaded(mdl), close_system(mdl, 0); end")
    w("systemcomposer.allocation.AllocationSet.closeAll; systemcomposer.profile.Profile.closeAll;")
    w("Simulink.data.dictionary.closeAll('-discard');")
    w("for f = [mdl + \".slx\", dd, prof + \".xml\", aset + \".mldatx\"], if isfile(f), delete(f); end, end")
    w("")
    w("model = systemcomposer.createModel(mdl); arch = model.Architecture;")
    w("% --- interfaces (item defs)")
    w("dict = systemcomposer.createDictionary(dd); I = struct();")
    for item, attrs in sorted(model.items.items()):
        w(f"I.{item} = addInterface(dict, {q(item)});")
        for an, at in attrs:
            w(f"addElement(I.{item}, {q(an)}, Type=\"double\", Units={q(UNITS.get(at, ''))});")
    w("linkDictionary(model, dd);")
    w("% --- profile: RosTopic stereotype for connectors")
    w("profile = systemcomposer.profile.Profile.createProfile(prof);")
    w("st = addStereotype(profile, \"RosTopic\", AppliesTo=\"Connector\");")
    w("addProperty(st, \"topic\", Type=\"string\"); addProperty(st, \"msgType\", Type=\"string\"); addProperty(st, \"qos\", Type=\"string\");")
    w("save(profile); applyProfile(model, prof);")
    w("")

    # pre-scan interface links to orient inout ports (first end = out)
    for _, a, b in rootdef["links"]:
        for c, p in resolve(root, a):
            c.ports[p][0] = "out"
        for c, p in resolve(root, b):
            c.ports[p][0] = "in"

    w("% --- components, ports, parameters")
    counts = {"components": 0, "ports": 0, "params": 0, "connectors": 0}

    compositions = []  # Simulink paths of components that own children

    def walk(comp):
        if comp.children:
            compositions.append("/".join([name + "Arch"] + comp.path))
        for child in comp.children.values():
            w(f"{child.var()} = addComponent({comp.var() if comp.parent else 'arch'}{'.Architecture' if comp.parent else ''}, {q(child.name)});")
            counts["components"] += 1
            for pn, (dirn, iface) in child.ports.items():
                w(f"p = addPort({child.var()}.Architecture, {q(pn)}, {q('in' if dirn == 'in' else 'out')});"
                  + (f" setInterface(p, I.{iface});" if iface and iface in model.items else ""))
                counts["ports"] += 1
            for an, val, unit in model.part_defs.get(child.typ, {}).get("attrs", []):
                w(f"addParameter({child.var()}.Architecture, {q(an)}, Value={q(val)}, Units={q(UNIT_LITERAL.get(unit, unit))});")
                counts["params"] += 1
            walk(child)

    for an, val, unit in rootdef["attrs"]:
        w(f"addParameter(arch, {q(an)}, Value={q(val)}, Units={q(UNIT_LITERAL.get(unit, unit))});")
        counts["params"] += 1
    walk(root)
    w("")
    w("% --- connectors (flows + interface links), routed through parent boundary ports")
    w("C = {};")

    boundary = set()

    def arch_of(comp):
        return "arch" if comp.parent is None else f"{comp.var()}.Architecture"

    def port_ref(comp, pn, from_inside):
        # from_inside: reference the port as seen inside comp's own architecture
        return f"getPort({arch_of(comp)}, {q(pn)})" if from_inside else f"getPort({comp.var()}, {q(pn)})"

    def up(comp, pn, direction, iface):
        """Promote comp.pn to its parent boundary; return (parent, newPortName)."""
        parent = comp.parent
        bp = f"{comp.name}_{pn}"
        if (parent.var(), bp) not in boundary:
            boundary.add((parent.var(), bp))
            w(f"p = addPort({arch_of(parent)}, {q(bp)}, {q(direction)});"
              + (f" setInterface(p, I.{iface});" if iface and iface in model.items else ""))
            if direction == "out":
                w(f"connect({port_ref(comp, pn, False)}, {port_ref(parent, bp, True)});")
            else:
                w(f"connect({port_ref(parent, bp, True)}, {port_ref(comp, pn, False)});")
            counts["connectors"] += 1
        return parent, bp

    def connect_pair(src, sp, dst, dp, iface, meta):
        s_path, d_path = src.path, dst.path
        k = 0
        while k < min(len(s_path), len(d_path)) - 1 and s_path[k] == d_path[k]:
            k += 1
        common_len = k if s_path[:k] == d_path[:k] else 0
        while len(src.path) - 1 > common_len:
            src, sp = up(src, sp, "out", iface)
        while len(dst.path) - 1 > common_len:
            dst, dp = up(dst, dp, "in", iface)
        w(f"C{{end+1}} = connect({port_ref(src, sp, False)}, {port_ref(dst, dp, False)});")
        counts["connectors"] += 1
        if meta.get("topic"):
            w("applyStereotype(C{end}, \"RoverProfile.RosTopic\");")
            for key in ("topic", "msgType", "qos"):
                if key in meta:
                    w(f"setProperty(C{{end}}, \"RoverProfile.RosTopic.{key}\", {repr_str(meta[key])});")

    for typ, a, b, meta in rootdef["flows"]:
        srcs, dsts = resolve(root, a), resolve(root, b)
        pairs = list(zip(srcs, dsts)) if len(srcs) == len(dsts) else [(s, d) for s in srcs for d in dsts]
        for (sc, sp), (dc, dp) in pairs:
            connect_pair(sc, sp, dc, dp, typ, meta)
    for _, a, b in rootdef["links"]:
        (sc, sp), = resolve(root, a)
        (dc, dp), = resolve(root, b)
        connect_pair(sc, sp, dc, dp, None, {})

    w("")
    w("% --- layout: auto-arrange every composition (addComponent stacks children at one spot)")
    ordered = sorted(compositions, key=lambda s: -s.count("/"))  # deepest first, root last
    w("for s = [" + ", ".join(q(s) for s in ordered) + "], Simulink.BlockDiagram.arrangeSystem(s); end")
    w("")
    w("% --- allocation (software services -> compute), same-model allocation set")
    w("as = systemcomposer.allocation.createAllocationSet(aset, mdl, mdl); sc = as.Scenarios(1);")
    for sw, hw in model.allocs:
        w(f"allocate(sc, lookup(model, Path={q(name + 'Arch/' + sw.replace('.', '/'))}), lookup(model, Path={q(name + 'Arch/' + hw.replace('.', '/'))}));")
    w("")
    w("save(dict); save(model); save(as);")
    w("fprintf('Built %s: %d components, %d ports, %d parameters, %d connectors, %d allocations\\n', ...")
    w(f"    mdl, {counts['components']}, {counts['ports']}, {counts['params']}, {counts['connectors']}, {len(model.allocs)});")
    w("end")
    return "\n".join(L) + "\n", counts


def repr_str(s):
    # MATLAB char literal containing a double-quoted string expression: '"cmd_vel"'
    return "'\"" + s.replace("'", "''") + "\"'"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model_dir")
    ap.add_argument("--root", required=True, help="system part def, e.g. RoverA1")
    ap.add_argument("--name", help="artifact prefix (default: --root)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    model = Model()
    files = sorted(pathlib.Path(args.model_dir).glob("*.sysml"))
    if not files:
        sys.exit("no .sysml files")
    for f in files:
        model.load(f.read_text(encoding="utf-8"))
    if args.root not in model.part_defs:
        sys.exit(f"part def {args.root} not found")
    root = build_tree(model, args.root)
    text, counts = emit(model, root, args.name or args.root, args.model_dir)
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text(text, encoding="utf-8")
    print(f"wrote {args.out}: " + ", ".join(f"{v} {k}" for k, v in counts.items())
          + f", {len(model.allocs)} allocations, {len(model.items)} interfaces")


if __name__ == "__main__":
    main()
