"""
insights.py — Funciones de apoyo "inteligentes" de NEXO SF (sin IA, reglas explicables).

1. Semáforo previo (readiness): con el check-in, ANTES de entrenar, anticipa
   si hoy es un día para intentar progresar.
2. Calentamiento automático: series de aproximación según la carga de trabajo,
   considerando el peso corporal en ejercicios con lastre.
3. Calibración del RIR: compara el RIR que reporta el atleta con el RIR que
   predice su mejor e1RM reciente (Epley invertido). Sirve para educar la
   autopercepción del esfuerzo.

Todos los porcentajes y umbrales son DECISIONES DE DISEÑO del prototipo.
"""

from calculations import round_to_increment
from smartload import STATUS_STYLE, n

# ---------------------------------------------------------------------------
# 1. Semáforo previo
# ---------------------------------------------------------------------------
def readiness(energy: int, sleep: int, soreness: str, threshold: int = 2) -> dict:
    """
    Anticipa el resultado posible del semáforo usando solo el check-in.
    Es coherente con smartload.py: las mismas señales que bloquean SUBIR
    después de la sesión se muestran aquí antes de empezar.
    """
    if soreness == "importantes":
        return {"status": "ALERTA", "color": STATUS_STYLE["ALERTA"]["color"],
                "title": "Día para cuidarte",
                "text": "Reportas molestias importantes. Considera no cargar este ejercicio hoy y "
                        "consulta a un profesional si la molestia persiste. El semáforo no recomendará carga.",
                "reasons": ["Molestias importantes."]}
    reasons = []
    if energy <= threshold:
        reasons.append(f"Energía baja ({energy}/5).")
    if sleep <= threshold:
        reasons.append(f"Sueño bajo ({sleep}/5).")
    if soreness == "leves":
        reasons.append("Molestias leves.")
    if reasons:
        return {"status": "MANTENER", "color": STATUS_STYLE["MANTENER"]["color"],
                "title": "Día para consolidar",
                "text": "Entrena con calidad, pero hoy el semáforo no recomendará subir aunque cumplas "
                        "todo. Enfócate en técnica y en repetir tu carga.",
                "reasons": reasons}
    return {"status": "SUBIR", "color": STATUS_STYLE["SUBIR"]["color"],
            "title": "Buen día para progresar",
            "text": "Tu bienestar está sobre el umbral. Si completas el objetivo con el RIR indicado, "
                    "el semáforo puede recomendarte subir.",
            "reasons": ["Energía, sueño y molestias en rango adecuado."]}


# ---------------------------------------------------------------------------
# 2. Calentamiento automático
# ---------------------------------------------------------------------------
# (porcentaje de la carga del sistema, repeticiones). Progresión clásica:
# muchas reps con poca carga -> pocas reps cerca de la carga de trabajo.
WARMUP_SCHEME = [(0.40, 5), (0.60, 3), (0.75, 2), (0.90, 1)]      # sentadilla: % de la barra de trabajo
WARMUP_SCHEME_ADDED = [(0.25, 3), (0.60, 2), (0.85, 1)]             # con lastre: % del lastre de trabajo


def warmup_plan(work_load: float, bodyweight: float | None, uses_bodyweight: bool,
                increment: float = 2.5, bar_kg: float = 20.0) -> list:
    """
    Devuelve una lista de series de aproximación:
      [{"load_kg": lastre o barra, "reps": int, "label": texto}, ...]

    - Ejercicios con peso corporal: el peso corporal ya es una carga alta
      (≈80-90 % de la carga del sistema), así que se parte con peso corporal
      y luego se agregan fracciones del lastre de trabajo, redondeadas hacia
      abajo a los discos disponibles.
    - Sentadilla: parte con la barra vacía y sube por porcentajes de la carga
      de trabajo, redondeando a los discos disponibles.
    """
    plan = []
    if uses_bodyweight:
        plan.append({"load_kg": 0.0, "reps": 5 if work_load > 0 else 3,
                     "label": "Peso corporal" + ("" if work_load > 0 else " · ritmo controlado, lejos del fallo")})
        if work_load <= 0:
            return plan
        for pct, reps in WARMUP_SCHEME_ADDED:
            added = round_to_increment(work_load * pct, increment, mode="down")
            if added <= 0 or added >= work_load or any(p["load_kg"] == added for p in plan):
                continue
            plan.append({"load_kg": added, "reps": reps, "label": f"+{n(added)} kg de lastre"})
        return plan

    # Sentadilla (barra)
    if work_load <= bar_kg:
        return [{"load_kg": bar_kg, "reps": 5, "label": "Barra vacía"}]
    plan.append({"load_kg": bar_kg, "reps": 8, "label": "Barra vacía"})
    for pct, reps in WARMUP_SCHEME:
        load = round_to_increment(work_load * pct, increment)
        if load <= bar_kg or load >= work_load or any(p["load_kg"] == load for p in plan):
            continue
        plan.append({"load_kg": load, "reps": reps, "label": f"{n(load)} kg"})
    return plan


# ---------------------------------------------------------------------------
# 3. Calibración del RIR
# ---------------------------------------------------------------------------
MAX_RELIABLE_REPS = 15   # tope de reps predichas; más allá la estimación no es confiable
CALIBRATION_MIN_SESSIONS = 3
CALIBRATION_WINDOW = 6   # últimas sesiones usadas en el resumen
REFERENCE_WINDOW = 5     # sesiones previas para la referencia de e1RM


def predicted_reps_to_failure(load_system: float, e1rm_system: float) -> float | None:
    """Epley invertido: reps máximas posibles = 30 x (e1RM / carga - 1)."""
    if load_system <= 0 or e1rm_system <= 0:
        return None
    reps = 30 * (e1rm_system / load_system - 1)
    if reps < 0 or reps > MAX_RELIABLE_REPS:
        return None
    return round(reps, 1)


def rir_gap(load_system: float, reps: int, reported_rir: int, ref_e1rm_system: float) -> dict | None:
    """
    Compara el RIR reportado con el RIR que predice la referencia.
      gap > 0 -> reportaste MÁS reserva de la estimada (estabas más cerca del fallo).
      gap < 0 -> reportaste MENOS reserva de la estimada (te quedaban más reps).
    Devuelve None si la comparación no es válida (p. ej., superaste la referencia).
    """
    max_reps = predicted_reps_to_failure(load_system, ref_e1rm_system)
    if max_reps is None or reps <= 0 or reported_rir is None:
        return None
    predicted_rir = round(max_reps - reps, 1)
    if predicted_rir < 0:
        return None   # hiciste más reps que lo posible según la referencia: mejoraste
    return {"reported": reported_rir, "predicted": predicted_rir,
            "gap": round(reported_rir - predicted_rir, 1)}


def calibration_summary(gaps: list) -> dict:
    """Resume la tendencia de las últimas sesiones."""
    recent = gaps[-CALIBRATION_WINDOW:]
    if len(recent) < CALIBRATION_MIN_SESSIONS:
        return {"ready": False, "count": len(recent),
                "title": f"Calibrando… {len(recent)}/{CALIBRATION_MIN_SESSIONS}",
                "text": f"Necesitamos {CALIBRATION_MIN_SESSIONS} sesiones válidas para estimar tu precisión "
                        f"(llevas {len(recent)}). Una sesión es válida si: (1) hay una sesión ANTERIOR del mismo "
                        "ejercicio y variante que sirva de referencia de fuerza, (2) tu primera serie tiene entre "
                        "1 y 12 reps con RIR anotado y (3) no superaste la referencia (si la superas, ¡mejoraste!)."}
    mean = round(sum(recent) / len(recent), 1)
    if mean > 1:
        title = "Sobreestimas tu reserva"
        text = (f"En promedio reportas {n(mean)} reps más en reserva de las que estima tu e1RM. "
                "Probablemente terminas tus series más cerca del fallo de lo que crees: sé más "
                "conservador al anotar el RIR.")
    elif mean < -1:
        title = "Subestimas tu reserva"
        text = (f"En promedio reportas {n(abs(mean))} reps menos en reserva de las estimadas. Te quedan "
                "más repeticiones de las que crees, algo frecuente según la literatura. Podrías exigirte "
                "un poco más.")
    else:
        title = "RIR bien calibrado"
        text = (f"Tu RIR reportado difiere en promedio {n(mean)} reps del estimado. Tu percepción del "
                "esfuerzo es consistente: el semáforo puede confiar en tus datos.")
    return {"ready": True, "count": len(recent), "mean": mean, "title": title, "text": text}


def calibration_points(sessions: list, uses_bodyweight: bool) -> list:
    """
    sessions: sesiones del MISMO ejercicio y variante, en orden cronológico, cada una con
      {"id", "session_date", "bodyweight_kg", "e1rm_added", "first_set": {"load_kg","reps","rir"}}
    Para cada sesión usa como referencia el mejor e1RM de las REFERENCE_WINDOW sesiones previas
    y solo la PRIMERA serie (la menos afectada por la fatiga acumulada).
    """
    points, previous = [], []
    for s in sessions:
        fs = s.get("first_set")
        bw = (s.get("bodyweight_kg") or 0.0) if uses_bodyweight else 0.0
        ref_added = max((p for p in previous[-REFERENCE_WINDOW:] if p is not None), default=None)
        if fs and ref_added is not None and fs["rir"] is not None:
            load_sys = fs["load_kg"] + bw
            ref_sys = ref_added + bw
            g = rir_gap(load_sys, fs["reps"], fs["rir"], ref_sys)
            if g:
                g.update({"session_id": s["id"], "session_date": s["session_date"]})
                points.append(g)
        previous.append(s.get("e1rm_added"))
    return points
