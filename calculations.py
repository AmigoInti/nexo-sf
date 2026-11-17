"""
calculations.py — Indicadores de la sesión (sin interfaz ni base de datos).

Todas las funciones son "puras": reciben números y devuelven números.
Eso permite probarlas con tests y explicarlas fácilmente.

Unidades: todo en kilogramos (kg).
"""

from collections import Counter

EPLEY_MAX_REPS = 12  # Epley se usa solo con series de 1 a 12 repeticiones (pierde precisión con más)


# ---------------------------------------------------------------------------
# Carga del sistema
# ---------------------------------------------------------------------------
def system_load(load_kg: float, bodyweight_kg: float | None, uses_bodyweight: bool) -> float:
    """
    Carga real que mueve el atleta.
    - Dominada / fondos / muscle-up: peso corporal + lastre.
    - Sentadilla: solo la carga de la barra.
    """
    if uses_bodyweight:
        if bodyweight_kg is None:
            raise ValueError("Se necesita el peso corporal para ejercicios con peso corporal.")
        return round(bodyweight_kg + load_kg, 2)
    return round(load_kg, 2)


def working_load(loads: list[float]) -> float:
    """
    "Carga actual" de la sesión: la carga que más se repite entre las series
    de trabajo. Si hay empate, se toma la mayor (criterio conservador para
    no sugerir subir desde una carga menor).
    """
    if not loads:
        raise ValueError("No hay series.")
    counts = Counter(loads)
    top = max(counts.values())
    return max(load for load, c in counts.items() if c == top)


# ---------------------------------------------------------------------------
# Indicadores de la sesión
# ---------------------------------------------------------------------------
def volume_load(sets: list[dict], bodyweight_kg: float | None, uses_bodyweight: bool) -> float:
    """Volumen-carga = suma de (carga del sistema x repeticiones). Unidad: kg·rep."""
    return round(sum(system_load(s["load_kg"], bodyweight_kg, uses_bodyweight) * s["reps"]
                     for s in sets), 1)


def total_reps(sets: list[dict]) -> int:
    return sum(s["reps"] for s in sets)


def compliance(sets: list[dict], target_sets: int, rep_min: int) -> dict:
    """
    Cumplimiento: series que alcanzaron al menos el mínimo de repeticiones,
    sobre las series objetivo. Devuelve numerador, denominador y porcentaje.
    """
    done = sum(1 for s in sets if s["reps"] >= rep_min)
    pct = round(done / target_sets * 100, 1) if target_sets else 0.0
    return {"done": done, "target": target_sets, "pct": pct}


def epley_1rm(load: float, reps: int) -> float | None:
    """e1RM de Epley: carga x (1 + reps/30). Solo se usa con 1–12 reps."""
    if reps < 1 or reps > EPLEY_MAX_REPS:
        return None
    return round(load * (1 + reps / 30), 1)


def session_e1rm(sets: list[dict], bodyweight_kg: float | None, uses_bodyweight: bool) -> dict | None:
    """
    Mejor e1RM de la sesión.
    Devuelve:
      - e1rm_system: estimación de la carga total (cuerpo + lastre, o barra).
      - e1rm_added: para ejercicios con peso corporal, el lastre máximo estimado
                    (e1rm_system - peso corporal). Es el número del Street Lifting.
      - set_number, load_kg, reps de la serie que lo produjo.
    """
    best = None
    for i, s in enumerate(sets, start=1):
        sys_load = system_load(s["load_kg"], bodyweight_kg, uses_bodyweight)
        e = epley_1rm(sys_load, s["reps"])
        if e is not None and (best is None or e > best["e1rm_system"]):
            best = {"e1rm_system": e, "set_number": i, "load_kg": s["load_kg"], "reps": s["reps"]}
    if best is None:
        return None
    best["e1rm_added"] = round(best["e1rm_system"] - bodyweight_kg, 1) if uses_bodyweight else best["e1rm_system"]
    return best


def estimated_total(e1rm_added_by_lift: dict) -> dict:
    """
    Total estimado Street Lifting: suma de los e1RM de lastre (o barra en
    sentadilla) más recientes de cada ejercicio. Descriptivo, NO oficial.
    Si falta algún ejercicio, el total se marca como incompleto.
    """
    values = {k: v for k, v in e1rm_added_by_lift.items() if v is not None}
    return {"total": round(sum(values.values()), 1),
            "complete": len(values) == len(e1rm_added_by_lift),
            "missing": [k for k, v in e1rm_added_by_lift.items() if v is None]}


def relative_strength(total_kg: float, bodyweight_kg: float) -> float | None:
    """Fuerza relativa = total / peso corporal."""
    if not bodyweight_kg:
        return None
    return round(total_kg / bodyweight_kg, 2)


# ---------------------------------------------------------------------------
# Utilidades de carga
# ---------------------------------------------------------------------------
def round_to_increment(value: float, increment: float, mode: str = "nearest") -> float:
    """Redondea una carga al múltiplo del incremento disponible (los discos que hay)."""
    steps = value / increment
    if mode == "down":
        import math
        steps = math.floor(steps + 1e-9)
    elif mode == "up":
        import math
        steps = math.ceil(steps - 1e-9)
    else:
        steps = round(steps)
    return round(steps * increment, 2)


def plate_breakdown(target_kg: float, plates=(20, 15, 10, 5, 2.5, 1.25),
                    bar_kg: float = 0.0, per_side: bool = False) -> dict:
    """
    Calculadora de discos.
    - Cinturón de lastre: bar_kg=0, per_side=False  -> discos totales a colgar.
    - Barra de sentadilla: bar_kg=20, per_side=True -> discos por lado.
    Devuelve los discos y el sobrante que no se pudo armar.
    """
    remaining = target_kg - bar_kg
    if per_side:
        remaining /= 2
    used = []
    for p in sorted(plates, reverse=True):
        while remaining >= p - 1e-9:
            used.append(p)
            remaining = round(remaining - p, 3)
    return {"plates": used, "leftover": round(remaining * (2 if per_side else 1), 2)}
