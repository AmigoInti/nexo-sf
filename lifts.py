"""
lifts.py — Catálogo de ejercicios de NEXO SF (Street Lifting).

Aquí se define QUÉ ejercicios existen, sus variantes y los valores iniciales
de cada uno. Todo es editable: si el grupo decide otro rango de repeticiones
o incremento, se cambia aquí (o desde Configuración en la app), no en el motor.

Concepto clave del Street Lifting:
- En dominadas, fondos y muscle-up el atleta mueve SU CUERPO + el LASTRE.
  Por eso `uses_bodyweight = True` y la "carga del sistema" es
  peso corporal + lastre.
- En sentadilla la carga es la barra (el peso corporal no se suma).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LiftDefaults:
    """Valores iniciales de un ejercicio (decisiones de diseño del prototipo)."""
    target_sets: int
    rep_min: int
    rep_max: int
    rir_target: int
    increment_kg: float        # menor salto de carga que el atleta puede montar
    max_increase_pct: float    # límite de aumento por recomendación (% de la carga del sistema)


@dataclass(frozen=True)
class Lift:
    key: str
    name: str
    emoji: str
    uses_bodyweight: bool
    variants: tuple
    defaults: LiftDefaults
    load_label: str = field(default="Lastre (kg)")


LIFTS = {
    "dominada": Lift(
        key="dominada",
        name="Dominada",
        emoji="🧗",
        uses_bodyweight=True,
        variants=("Prono", "Supino", "Sin especificar"),
        defaults=LiftDefaults(target_sets=3, rep_min=3, rep_max=5, rir_target=2,
                              increment_kg=2.5, max_increase_pct=5.0),
    ),
    "fondos": Lift(
        key="fondos",
        name="Fondos",
        emoji="💪",
        uses_bodyweight=True,
        variants=("Paralelas", "Sin especificar"),
        defaults=LiftDefaults(target_sets=3, rep_min=5, rep_max=8, rir_target=2,
                              increment_kg=2.5, max_increase_pct=5.0),
    ),
    "sentadilla": Lift(
        key="sentadilla",
        name="Sentadilla",
        emoji="🏋️",
        uses_bodyweight=False,
        variants=("Barra alta", "Barra baja", "Sin especificar"),
        defaults=LiftDefaults(target_sets=3, rep_min=3, rep_max=5, rir_target=2,
                              increment_kg=2.5, max_increase_pct=5.0),
        load_label="Carga en barra (kg)",
    ),
    "muscle_up": Lift(
        key="muscle_up",
        name="Muscle-up",
        emoji="🤸",
        uses_bodyweight=True,
        variants=("Estricto", "Con kipping", "Sin especificar"),
        # Ejercicio muy técnico: rangos bajos y saltos de carga pequeños.
        defaults=LiftDefaults(target_sets=3, rep_min=1, rep_max=3, rir_target=1,
                              increment_kg=1.25, max_increase_pct=5.0),
    ),
}

SESSION_TYPES = ("Técnica", "Volumen", "Intensidad")
SORENESS_LEVELS = ("ninguna", "leves", "importantes")
TECHNIQUE_LEVELS = ("adecuada", "revisar")


def get_lift(key: str) -> Lift:
    if key not in LIFTS:
        raise KeyError(f"Ejercicio desconocido: {key}")
    return LIFTS[key]
