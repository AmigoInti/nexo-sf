"""
smartload.py — Motor del semáforo de NEXO SF.

SmartLoad es un sistema de REGLAS DETERMINISTAS: con los mismos datos
siempre entrega la misma decisión y las mismas razones. No usa IA.
No sabe nada de la interfaz (Streamlit) ni de la base de datos: recibe
datos y devuelve un resultado. Por eso se puede probar con tests.

Estados del semáforo
--------------------
  🟢 SUBIR       Todas las series en el tope del rango y con el RIR objetivo.
  🟡 MANTENER    Dentro del rango pero sin cumplir todo, fallo puntual,
                 bienestar bajo, molestias leves o salto de carga muy grande.
  🔴 BAJAR       Repeticiones bajo el mínimo en 2 sesiones comparables seguidas.
  🟣 ALERTA      Molestia importante o técnica a revisar: no se recomienda carga.
  ⚪ LINEA_BASE  Primera sesión comparable: se guarda como referencia.
  ⚫ INCOMPLETO  Datos faltantes o inválidos: no se analiza.

Orden de las reglas (la primera que se cumple decide)
-----------------------------------------------------
  0. Datos inválidos ................................ INCOMPLETO
  1. Molestia importante o técnica "revisar" ........ ALERTA
  2. No hay sesión comparable anterior .............. LINEA_BASE
  3. Alguna serie bajo el mínimo de reps:
       - la sesión comparable anterior también ...... BAJAR
       - si no ...................................... MANTENER (fallo puntual)
  4. No todas en el tope del rango o RIR bajo ....... MANTENER
  5. Criterios cumplidos, pero bienestar bajo
     (energía o sueño <= umbral) o molestias leves .. MANTENER
  6. Criterios cumplidos, pero el salto supera el
     límite porcentual .............................. MANTENER
  7. Todo cumplido .................................. SUBIR

Los umbrales numéricos (energía/sueño <= 2, límite 5 %, bajada 5 %) son
DECISIONES DE DISEÑO del prototipo, configurables, no puntos de corte
clínicos ni científicamente validados.
"""

from dataclasses import dataclass, field, asdict

from calculations import round_to_increment, system_load, working_load
from lifts import LIFTS, SESSION_TYPES, SORENESS_LEVELS, TECHNIQUE_LEVELS

RULE_VERSION = "nexosf_street_v1"


def n(x) -> str:
    """Formatea un número al estilo chileno: 22.5 -> '22,5'."""
    return f"{x:g}".replace(".", ",")

STATUS_STYLE = {
    "SUBIR":      {"color": "#22C55E", "emoji": "🟢", "label": "SUBIR"},
    "MANTENER":   {"color": "#FACC15", "emoji": "🟡", "label": "MANTENER"},
    "BAJAR":      {"color": "#EF4444", "emoji": "🔴", "label": "BAJAR"},
    "ALERTA":     {"color": "#A855F7", "emoji": "🟣", "label": "ALERTA"},
    "LINEA_BASE": {"color": "#94A3B8", "emoji": "⚪", "label": "LÍNEA BASE"},
    "INCOMPLETO": {"color": "#475569", "emoji": "⚫", "label": "DATOS INCOMPLETOS"},
}


# ---------------------------------------------------------------------------
# Estructuras de datos de entrada
# ---------------------------------------------------------------------------
@dataclass
class SetEntry:
    load_kg: float          # lastre (dominada/fondos/muscle-up) o barra (sentadilla)
    reps: int
    rir: int | None = None  # puede ser None solo si reps == 0


@dataclass
class CheckIn:
    energy: int                     # 1-5
    sleep: int                      # 1-5
    soreness: str                   # "ninguna" | "leves" | "importantes"
    technique: str                  # "adecuada" | "revisar"
    bodyweight_kg: float | None = None


@dataclass
class Settings:
    increment_kg: float = 2.5
    max_increase_pct: float = 5.0
    decrease_pct: float = 5.0
    low_wellbeing_threshold: int = 2


@dataclass
class SessionInput:
    lift_key: str
    variant: str
    session_type: str
    target_sets: int
    rep_min: int
    rep_max: int
    rir_target: int
    sets: list
    checkin: CheckIn
    settings: Settings = field(default_factory=Settings)


@dataclass
class PreviousSession:
    """Resumen de una sesión ya guardada (lo entrega la base de datos)."""
    id: int
    lift_key: str
    variant: str
    session_type: str
    target_sets: int
    rep_min: int
    rep_max: int
    rir_target: int
    below_min: bool         # ¿alguna serie quedó bajo el mínimo?


@dataclass
class SmartLoadResult:
    status: str
    message: str
    reasons: list
    current_load_kg: float | None = None
    suggested_load_kg: float | None = None
    current_system_kg: float | None = None
    suggested_system_kg: float | None = None
    change_pct: float | None = None
    comparison_session_id: int | None = None
    errors: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    rule_version: str = RULE_VERSION

    @property
    def style(self) -> dict:
        return STATUS_STYLE[self.status]

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Comparabilidad
# ---------------------------------------------------------------------------
def is_comparable(current: SessionInput, prev: PreviousSession) -> bool:
    """Solo se compara mismo ejercicio, variante, tipo de sesión y objetivos."""
    return (prev.lift_key == current.lift_key
            and prev.variant == current.variant
            and prev.session_type == current.session_type
            and prev.target_sets == current.target_sets
            and prev.rep_min == current.rep_min
            and prev.rep_max == current.rep_max
            and prev.rir_target == current.rir_target)


def find_comparable(current: SessionInput, history: list) -> list:
    """Devuelve las sesiones comparables, la más reciente primero (history viene así)."""
    return [p for p in history if is_comparable(current, p)]


def below_minimum(sets: list, rep_min: int) -> list:
    """Números de serie (1, 2, ...) que quedaron bajo el mínimo."""
    return [i for i, s in enumerate(sets, start=1) if s.reps < rep_min]


# ---------------------------------------------------------------------------
# Regla 0: validación
# ---------------------------------------------------------------------------
def validate(s: SessionInput) -> list:
    errors = []
    lift = LIFTS.get(s.lift_key)
    if lift is None:
        return [f"Ejercicio desconocido: {s.lift_key}"]
    if s.variant not in lift.variants:
        errors.append(f"Variante no válida para {lift.name}: {s.variant}")
    if s.session_type not in SESSION_TYPES:
        errors.append(f"Tipo de sesión no válido: {s.session_type}")

    # Objetivos
    if not isinstance(s.target_sets, int) or s.target_sets < 1:
        errors.append("Series objetivo: debe ser un entero mayor o igual a 1.")
    if not isinstance(s.rep_min, int) or s.rep_min < 1:
        errors.append("Repeticiones mínimas: debe ser un entero mayor que 0.")
    if not isinstance(s.rep_max, int) or s.rep_max < s.rep_min:
        errors.append("Repeticiones máximas: deben ser mayores o iguales al mínimo.")
    if not isinstance(s.rir_target, int) or not 0 <= s.rir_target <= 5:
        errors.append("RIR objetivo: entero entre 0 y 5.")

    # Series
    if isinstance(s.target_sets, int) and len(s.sets) != s.target_sets:
        errors.append(f"Registraste {len(s.sets)} series de {s.target_sets} objetivo. "
                      "Si no completaste una serie, regístrala con 0 repeticiones.")
    for i, st in enumerate(s.sets, start=1):
        if lift.uses_bodyweight:
            if st.load_kg is None or st.load_kg < 0:
                errors.append(f"Serie {i}: el lastre no puede ser negativo (usa 0 si fue solo peso corporal).")
        elif st.load_kg is None or st.load_kg <= 0:
            errors.append(f"Serie {i}: la carga en barra debe ser mayor que 0.")
        if not isinstance(st.reps, int) or st.reps < 0:
            errors.append(f"Serie {i}: las repeticiones deben ser un entero mayor o igual a 0.")
        elif st.reps > 0 and (st.rir is None or not isinstance(st.rir, int) or not 0 <= st.rir <= 5):
            errors.append(f"Serie {i}: indica un RIR entre 0 y 5.")

    # Check-in
    c = s.checkin
    if not isinstance(c.energy, int) or not 1 <= c.energy <= 5:
        errors.append("Energía: entero entre 1 y 5.")
    if not isinstance(c.sleep, int) or not 1 <= c.sleep <= 5:
        errors.append("Sueño: entero entre 1 y 5.")
    if c.soreness not in SORENESS_LEVELS:
        errors.append("Molestias: elige ninguna, leves o importantes.")
    if c.technique not in TECHNIQUE_LEVELS:
        errors.append("Técnica: elige adecuada o revisar.")
    if lift.uses_bodyweight and (c.bodyweight_kg is None or not 30 <= c.bodyweight_kg <= 250):
        errors.append(f"Peso corporal: necesario para {lift.name} (entre 30 y 250 kg).")

    # Configuración
    if s.settings.increment_kg <= 0:
        errors.append("Incremento disponible: debe ser mayor que 0.")
    if s.settings.max_increase_pct <= 0:
        errors.append("Límite de aumento: debe ser mayor que 0 %.")
    if s.settings.decrease_pct <= 0:
        errors.append("Porcentaje de bajada: debe ser mayor que 0 %.")
    return errors


# ---------------------------------------------------------------------------
# Motor principal
# ---------------------------------------------------------------------------
def evaluate(s: SessionInput, history: list | None = None) -> SmartLoadResult:
    """
    Evalúa una sesión y devuelve la decisión del semáforo.
    `history`: sesiones anteriores (PreviousSession), la más reciente primero.
    """
    history = history or []

    # --- Regla 0: datos válidos -------------------------------------------
    errors = validate(s)
    if errors:
        return SmartLoadResult(
            status="INCOMPLETO",
            message="Corrige los datos marcados para poder analizar la sesión. Lo que ingresaste se conserva.",
            reasons=["Hay datos faltantes o inválidos."],
            errors=errors,
        )

    lift = LIFTS[s.lift_key]
    cfg = s.settings
    bw = s.checkin.bodyweight_kg
    unit = "de lastre" if lift.uses_bodyweight else "en barra"

    current = working_load([st.load_kg for st in s.sets])
    current_sys = system_load(current, bw, lift.uses_bodyweight)
    notes = []
    if len({st.load_kg for st in s.sets}) > 1:
        notes.append(f"Usaste cargas distintas entre series; se toma {n(current)} kg como carga de trabajo "
                     "(la más repetida).")
    if lift.uses_bodyweight:
        notes.append(f"Carga del sistema: {n(bw)} kg de peso corporal + {n(current)} kg de lastre = {n(current_sys)} kg.")

    base = dict(current_load_kg=current, current_system_kg=current_sys, notes=notes)
    comparables = find_comparable(s, history)
    prev = comparables[0] if comparables else None
    prev_id = prev.id if prev else None

    # --- Regla 1: ALERTA ---------------------------------------------------
    alert_reasons = []
    if s.checkin.soreness == "importantes":
        alert_reasons.append("Reportaste molestias importantes.")
    if s.checkin.technique == "revisar":
        alert_reasons.append("Marcaste que la técnica necesita revisión.")
    if alert_reasons:
        return SmartLoadResult(
            status="ALERTA",
            message="No cambies la carga por ahora. Revisa la sesión con tu entrenador o con tu propio "
                    "criterio antes de la próxima. NEXO SF no diagnostica lesiones.",
            reasons=alert_reasons + ["Esta señal tiene prioridad sobre cualquier progreso de rendimiento."],
            suggested_load_kg=None, comparison_session_id=prev_id, **base,
        )

    failed_sets = below_minimum(s.sets, s.rep_min)

    # --- Regla 2: LÍNEA BASE -----------------------------------------------
    if prev is None:
        reasons = [f"Es tu primer registro comparable de {lift.name} ({s.variant}, {s.session_type}, "
                   f"{s.target_sets}x{s.rep_min}-{s.rep_max} @ RIR {s.rir_target})."]
        if failed_sets:
            reasons.append(f"Serie(s) {', '.join(map(str, failed_sets))} bajo el mínimo de {s.rep_min} reps: "
                           "considera una carga menor la próxima vez.")
        return SmartLoadResult(
            status="LINEA_BASE",
            message=f"Sesión guardada como referencia con {n(current)} kg {unit}. "
                    "En la próxima sesión comparable el semáforo podrá recomendarte qué hacer.",
            reasons=reasons, suggested_load_kg=current, comparison_session_id=None, **base,
        )

    # --- Regla 3: reps bajo el mínimo (BAJAR o fallo puntual) ---------------
    if failed_sets:
        failed_txt = ", ".join(map(str, failed_sets))
        if prev.below_min:
            return _decrease(s, lift, current, current_sys, bw, failed_txt, prev_id, base)
        return SmartLoadResult(
            status="MANTENER",
            message=f"Mantén {n(current)} kg {unit}. Fue un fallo puntual: si en la próxima sesión "
                    "comparable vuelves a quedar bajo el mínimo, el semáforo te sugerirá bajar.",
            reasons=[f"Serie(s) {failed_txt} no alcanzaron el mínimo de {s.rep_min} reps.",
                     "La sesión comparable anterior sí cumplió el mínimo."],
            suggested_load_kg=current, suggested_system_kg=current_sys, change_pct=0.0,
            comparison_session_id=prev_id, **base,
        )

    # --- Regla 4: dentro del rango pero sin cumplir todo ---------------------
    not_top = [i for i, st in enumerate(s.sets, 1) if st.reps < s.rep_max]
    low_rir = [i for i, st in enumerate(s.sets, 1) if st.rir is not None and st.rir < s.rir_target]
    if not_top or low_rir:
        reasons = []
        if not_top:
            reasons.append(f"Serie(s) {', '.join(map(str, not_top))} no llegaron al tope de {s.rep_max} reps.")
        if low_rir:
            reasons.append(f"Serie(s) {', '.join(map(str, low_rir))} quedaron con RIR menor al objetivo ({s.rir_target}).")
        return SmartLoadResult(
            status="MANTENER",
            message=f"Mantén {n(current)} kg {unit}. Completaste el rango; ahora busca llegar a "
                    f"{s.rep_max} reps en todas las series con RIR {s.rir_target} o más.",
            reasons=reasons, suggested_load_kg=current, suggested_system_kg=current_sys,
            change_pct=0.0, comparison_session_id=prev_id, **base,
        )

    # A partir de aquí, el rendimiento cumple los criterios de progreso.
    perf_ok = (f"Las {s.target_sets} series llegaron a {s.rep_max}+ reps con RIR {s.rir_target} o más.")

    # --- Regla 5: bienestar bajo o molestias leves bloquean la subida --------
    blockers = []
    t = cfg.low_wellbeing_threshold
    if s.checkin.energy <= t:
        blockers.append(f"Energía reportada baja ({s.checkin.energy}/5).")
    if s.checkin.sleep <= t:
        blockers.append(f"Sueño reportado bajo ({s.checkin.sleep}/5).")
    if s.checkin.soreness == "leves":
        blockers.append("Reportaste molestias leves.")
    if blockers:
        return SmartLoadResult(
            status="MANTENER",
            message=f"Rendiste bien, pero hoy no es buen día para subir. Mantén {n(current)} kg {unit} "
                    "y confirma el progreso en la próxima sesión.",
            reasons=[perf_ok] + blockers, suggested_load_kg=current, suggested_system_kg=current_sys,
            change_pct=0.0, comparison_session_id=prev_id, **base,
        )

    # --- Reglas 6 y 7: salto de carga ---------------------------------------
    inc = cfg.increment_kg
    pct = round(inc / current_sys * 100, 2)
    new_load = round(current + inc, 2)
    new_sys = round(current_sys + inc, 2)

    if pct > cfg.max_increase_pct:
        return SmartLoadResult(
            status="MANTENER",
            message=f"Mantén {n(current)} kg {unit}. El incremento disponible ({n(inc)} kg) equivale a "
                    f"{n(pct)} % y supera tu límite de {n(cfg.max_increase_pct)} %. "
                    "Ajusta el incremento en Configuración si tienes discos más pequeños.",
            reasons=[perf_ok, f"Salto de {n(inc)} kg sobre {n(current_sys)} kg = {n(pct)} % "
                              f"> límite {n(cfg.max_increase_pct)} %."],
            suggested_load_kg=current, suggested_system_kg=current_sys, change_pct=0.0,
            comparison_session_id=prev_id, **base,
        )

    if lift.uses_bodyweight and current == 0:
        msg = (f"¡Dominaste el rango con peso corporal! Próxima sesión comparable: empieza con "
               f"{n(new_load)} kg de lastre (+{n(pct)} % de la carga del sistema).")
        extra = ["Doble progresión: primero se progresa en repeticiones y, al llegar al tope del rango, "
                 "se agrega el lastre mínimo disponible."]
    else:
        msg = (f"Próxima sesión comparable: prueba {n(new_load)} kg {unit} (+{n(inc)} kg, "
               f"+{n(pct)} % de la carga del sistema). Es una sugerencia: confirma que tu planificación lo permite.")
        extra = []
    return SmartLoadResult(
        status="SUBIR", message=msg,
        reasons=[perf_ok, "Sin molestias, técnica adecuada y bienestar sobre el umbral.",
                 f"Salto de {n(pct)} % dentro del límite de {n(cfg.max_increase_pct)} %."] + extra,
        suggested_load_kg=new_load, suggested_system_kg=new_sys, change_pct=pct,
        comparison_session_id=prev_id, **base,
    )


def _decrease(s, lift, current, current_sys, bw, failed_txt, prev_id, base) -> SmartLoadResult:
    """Regla 3a: dos sesiones comparables seguidas bajo el mínimo -> BAJAR."""
    cfg = s.settings
    reasons = [f"Serie(s) {failed_txt} no alcanzaron el mínimo de {s.rep_min} reps.",
               "La sesión comparable anterior tampoco alcanzó el mínimo (2 seguidas)."]
    unit = "de lastre" if lift.uses_bodyweight else "en barra"

    if lift.uses_bodyweight and current == 0:
        return SmartLoadResult(
            status="BAJAR",
            message="Ya estás entrenando sin lastre. Baja el rango de repeticiones objetivo "
                    "o usa una asistencia (banda elástica) hasta volver a cumplir el mínimo.",
            reasons=reasons, suggested_load_kg=0.0, suggested_system_kg=current_sys,
            change_pct=0.0, comparison_session_id=prev_id, **base,
        )

    # Reducción = % de la carga del sistema, redondeada hacia arriba al disco disponible
    reduction = round_to_increment(current_sys * cfg.decrease_pct / 100, cfg.increment_kg, mode="up")
    reduction = max(reduction, cfg.increment_kg)
    floor = 0.0 if lift.uses_bodyweight else cfg.increment_kg
    new_load = max(round(current - reduction, 2), floor)
    new_sys = system_load(new_load, bw, lift.uses_bodyweight)
    pct = round((new_sys - current_sys) / current_sys * 100, 2)
    return SmartLoadResult(
        status="BAJAR",
        message=f"Baja a {n(new_load)} kg {unit} ({n(pct)} % de la carga del sistema) y reconstruye "
                "desde ahí. Bajar a tiempo también es progresar.",
        reasons=reasons + [f"Bajada configurada: {n(cfg.decrease_pct)} % de {n(current_sys)} kg, "
                           f"redondeada a discos de {n(cfg.increment_kg)} kg."],
        suggested_load_kg=new_load, suggested_system_kg=new_sys, change_pct=pct,
        comparison_session_id=prev_id, **base,
    )
