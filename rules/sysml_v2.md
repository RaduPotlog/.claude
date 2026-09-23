# SysML v2 Textual Notation Reference

Quick reference and project conventions for writing **SysML v2** models
(OMG SysML v2.0 / KerML 1.0) as text. Source: `~/mbse_ws/ref/SysML-v2-Release/`
(git tag `2026-08`, Pilot Implementation **0.62.0**).

- Language spec, BNF, examples: `~/mbse_ws/ref/SysML-v2-Release/{doc,bnf,sysml/src}`.
- **Training examples, one folder per concept** (`01. Packages` … `42. Views`):
  `sysml/src/training/`. Copy syntax from these instead of guessing.
- Standard library (ISQ/SI units, `VerificationCases`, `TradeStudies`, …):
  `sysml.library/`.
- Validator + renderer: `skills/sysml_v2_modeling/scripts/sysml_validate.py`
  (run through `/sysml-validate`). Pilot kernel env: `~/mbse_ws/tools/sysml-env`.
- Seed model: `rover_a1/mbse/rover_a1/` (`01_interfaces` … `05_analysis`).
- MATLAB / System Composer side: `matlab_simulink_mbse.md`.

---

## 1. Definition vs usage (the core idea)

Every concept has a **definition** (`… def`, a type) and a **usage** (a typed
feature in a context). Model with defs, then compose with usages.

| Concept | Definition | Usage | Notes |
|---------|-----------|-------|-------|
| Structure | `part def Wheel { … }` | `part wheel : Wheel[4];` | parts own parts, ports, attributes |
| Value | `attribute def Temp :> ScalarQuantityValue;` | `attribute radius :> ISQ::length = 0.1651 [m];` | quantities come from `ISQ` |
| Things that flow | `item def TwistStamped { … }` | `out item cmd : TwistStamped;` | messages, energy, material |
| Interaction point | `port def TwistPort { out item cmd : TwistStamped; }` | `port cmdIn : ~TwistPort;` | `~` = conjugate (reverses in/out) |
| Link | `interface def ModbusLink { end a : ModbusPort; end b : ModbusPort; }` | `interface : ModbusLink connect x.p to y.p;` | typed connection between ports |
| Transfer | — | `flow of T from a.p.item to b.q.item;` | directed item transfer |
| Enumeration | `enum def Qos { enum Reliable; }` | `attribute qos : Qos;` | |
| Behaviour | `action def Dock { in … out … }` / `state def Mode { … }` | `perform action dock : Dock;` / `exhibit state mode : Mode;` | |
| Math | `calc def Endurance { in …; return r : T = expr; }` | `Endurance(a, b, c)` | pure functions |
| Constraint | `constraint def PowerBalance { … }` | `assert constraint { … }` | |
| Requirement | `requirement def <'R-X-01'> Name { subject s : T; require constraint { … } }` | `requirement r : Name { subject = …; }` | `<'id'>` = short name |
| Traceability | — | `satisfy spec by roverA1;` / `verify spec.r;` | |
| Analysis | `analysis def A { subject …; objective { require … } return … }` | `analysis a : A { subject rover = roverA1; }` | |
| Verification | `verification def T { objective { verify … } return verdict : VerdictKind = … }` | `verification t : T { … }` | needs `private import VerificationCases::*;` |
| Allocation | `allocation def SwToHw { end software : Parts::Part; end hardware : Compute; }` | `allocation a : SwToHw allocate x to y;` | |
| Metadata | `metadata def RosTopic { attribute topic : String; }` | `@RosTopic { topic = "cmd_vel"; }` inside an element body | our stereotype-like annotation |
| Variability | `variation part def BatteryChoice { variant part liIon : LiIon; variant part lfp : LiFePO4; }` | `part roverLfp : Rover { part :>> battery = BatteryChoice::lfp; }` | trade studies / product lines (`TradeStudies` library) |

Relationship shorthands: `:>` specializes/subsets · `:>>` redefines ·
`::` qualified name · `#(i)` index a sequence · `[m]`, `[m/s^2]`, `[A*h]`
unit literal · `'quoted name'` for any name (including keywords).

## 2. Idioms (all verified with the Pilot kernel)

```sysml
package RoverA1_Requirements {
    private import ISQ::*;                 // quantity types: LengthValue, SpeedValue, …
    private import SI::*;                  // units: m, s, A, V, W, h, K, Hz, rad, kg
    private import RoverA1_Structure::*;

    requirement def <'R-SAF-01'> CommandTimeout {
        doc /* The rover shall stop driving within 0.5 s after its velocity command stream stops. */
        subject rover : RoverA1;
        attribute maxTimeout : DurationValue = 0.5 [s];
        require constraint { rover.platform.driveController.cmdTimeout <= maxTimeout }
    }
    requirement roverA1Specification {
        subject vehicle : RoverA1;         // NOT 'rover' — see pitfall 4
        requirement cmdTimeout : CommandTimeout { subject = vehicle; }
    }
    satisfy roverA1Specification by roverA1;
}
```

Analysis objective → `require <requirement usage>;`. Verification objective →
`verify <requirement usage>;` and return `PassIf(<boolean>)` as a `VerdictKind`.

## 3. Project conventions

| Topic | Rule |
|-------|------|
| Layout | `mbse/<system>/NN_<layer>.sysml`, **one package per file**, numbered in dependency order (`01_interfaces`, `02_structure`, `03_calculations`, `04_requirements`, `05_analysis`). The validator loads a directory in sorted order. |
| Package names | `<System>_<Layer>` (e.g. `RoverA1_Structure`). Import with `private import` only. |
| Naming | `PascalCase` for defs, `camelCase` for usages and attributes. Requirement ids `<'R-<AREA>-NN'>` with AREA ∈ PERF, SAF, CTRL, END, IF, ENV. |
| Provenance | Every numeric value has a `doc` or `//` comment naming its **source file** (URDF, controller yaml, datasheet). |
| Unknowns | Never invent numbers. Write `TBD:` in the doc and, if a value is needed, label it `ASSUMPTION` with its reason. |
| Requirement status | Values taken from current configs are **BASELINE** (to be confirmed by the owner), not external specs. Say so in the package doc. |
| Units | Always typed quantities + unit literals. Temperatures in **K** (`ThermodynamicTemperatureValue`). SI `'°C'` is a temperature *difference* unit. |
| Truth of constraints | The Pilot kernel checks syntax, names and typing, **not** whether constraints hold. Evaluate numbers in MATLAB (`system_composer_sysml` skill) or state the hand calculation in the analysis `doc`. |

## 4. ROS 2 ↔ SysML v2 mapping (this workspace)

| ROS 2 / rover concept | SysML v2 element |
|-----------------------|------------------|
| message type (`geometry_msgs/TwistStamped`) | `item def TwistStamped { attribute … }` (only the fields the model reasons about) |
| publisher / subscriber endpoint | `port def XPort { out item … }`; subscriber = `~XPort` |
| topic (+ QoS) | `flow of T from a.port.item to b.port.item { @RosTopic { topic = "…"; msgType = "…"; qos = QosProfile::… ; } }` |
| service / action | `interface def` with request/response items, or an `action def` performed by the server part |
| node / package | `part def` (software), grouped by container |
| balena service / container | `part def <Name>Service` owning node parts |
| container → computer | `allocation … allocate roverA1.platform to roverA1.compute;` |
| ros2_control hardware component | `part def` with command/state interfaces as ports |
| controller params (limits, rates) | `attribute`s with units on the software part |
| Nav 2 params / footprint | `attribute`s on `Navigation`, constrained by requirements |
| lifecycle / mode logic | `state def` exhibited by the part |
| VDA 5050 fleet interface | `interface def` + `item def`s per message (see `vda5050_messages.md`) |

## 5. Pitfalls (each one hit in practice)

1. **Reserved keywords used as names** break parsing with `no viable
   alternative at input`. Common collisions: `frame`, `event`, `message`,
   `state`, `flow`, `port`, `item`, `part`, `action`, `end`, `in`, `out`,
   `then`, `first`, `via`, `at`, `when`, `do`, `entry`, `exit`, `merge`,
   `join`, `fork`, `decide`, `loop`, `until`, `while`, `render`, `view`,
   `filter`, `library`, `standard`, `language`, `snapshot`, `timeslice`,
   `individual`, `variant`, `variation`, `occurrence`, `default`, `derived`,
   `constant`, `ordered`, `all`, `new`, `null`, `alias`, `use`, `send`,
   `accept`, `assign`, `terminate`, `parallel`, `about`. Rename the element
   (e.g. `packet`), or quote it: `'frame'`.
2. **`Part` is not in scope** for allocation ends. Write `Parts::Part`.
3. An **allocation usage with a body but no ends** gives `Must have at least two
   related elements`. Use `allocation a : Def allocate x to y;` per pair.
4. **Subject shadowing.** Inside `requirement r : R { subject = rover; }`, the
   name `rover` resolves to `r`'s *own* subject when `R` also names its subject
   `rover`. Give the group subject a different name (`vehicle`).
5. **Composition in the def.** When requirements navigate
   `rover.battery.capacity`, the parts must be declared in `part def RoverA1`,
   not only in the usage `part roverA1 : RoverA1 { … }`.
6. **Multiplicity navigation.** `rover.drive.wheel.radius` is a sequence when
   `drive[4]`. Index it: `rover.drive#(1).wheel.radius`.
7. **Units need `private import SI::*;`**. Otherwise `[m]` fails to resolve.
8. **Diagram limit.** `%viz` of a large element prints `EXCEEDS THE LIMIT`.
   Render a sub-tree (a single part def or package) instead of the whole model.
