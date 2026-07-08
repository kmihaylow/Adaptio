"""Convert a power-targeted bike workout into a Zwift/MyWhoosh .zwo file.

Only meaningful for workouts whose segments carry power targets (fractions of
FTP) — i.e. athletes with a smart trainer or power meter (изискване т.8).
"""

from __future__ import annotations

import xml.sax.saxutils as sx


def to_zwo(workout: dict) -> str:
    parts = []
    for s in workout["segments"]:
        if s.get("target_kind") != "power":
            continue
        dur = int(s["duration_s"])
        lo = round(float(s["low"]), 3)
        hi = round(float(s["high"]), 3)
        cad = s.get("cadence_rpm")
        cad_attr = f' Cadence="{int(cad)}"' if cad else ""
        t = s["type"]
        if t == "warmup":
            parts.append(f'    <Warmup Duration="{dur}" PowerLow="{lo}" PowerHigh="{hi}"{cad_attr}/>')
        elif t == "cooldown":
            parts.append(f'    <Cooldown Duration="{dur}" PowerLow="{hi}" PowerHigh="{lo}"{cad_attr}/>')
        else:
            power = hi if t == "interval_on" else lo if t == "interval_off" else round((lo + hi) / 2, 3)
            parts.append(f'    <SteadyState Duration="{dur}" Power="{power}"{cad_attr}/>')

    name = sx.escape(workout["name"])
    desc = sx.escape(workout.get("description", ""))
    body = "\n".join(parts)
    return f"""<workout_file>
  <author>Adaptio</author>
  <name>{name}</name>
  <description>{desc}</description>
  <sportType>bike</sportType>
  <tags/>
  <workout>
{body}
  </workout>
</workout_file>
"""


def is_zwo_exportable(workout: dict) -> bool:
    return workout.get("sport") == "bike" and any(
        s.get("target_kind") == "power" for s in workout.get("segments", [])
    )
