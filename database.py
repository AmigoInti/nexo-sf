"""
database.py — Almacenamiento local en SQLite para NEXO SF.

- Un archivo `nexosf.db` en la carpeta del proyecto.
- Todas las consultas usan parámetros (?), nunca texto concatenado.
- Una sesión y sus series se guardan en UNA transacción: o se guarda todo
  o no se guarda nada.
- Los objetivos de cada sesión se guardan como "foto" (snapshot): si después
  cambias la Configuración, el historial no cambia.
"""

import csv
import io
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from calculations import compliance, session_e1rm, volume_load
from lifts import LIFTS
from smartload import (CheckIn, PreviousSession, SessionInput, SetEntry, Settings,
                       below_minimum, evaluate)

DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexosf.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lift_config (
    lift_key TEXT PRIMARY KEY,
    target_sets INTEGER NOT NULL,
    rep_min INTEGER NOT NULL,
    rep_max INTEGER NOT NULL,
    rir_target INTEGER NOT NULL,
    increment_kg REAL NOT NULL,
    max_increase_pct REAL NOT NULL,
    decrease_pct REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS training_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date TEXT NOT NULL,
    lift_key TEXT NOT NULL,
    variant TEXT NOT NULL,
    session_type TEXT NOT NULL,
    target_sets INTEGER NOT NULL,
    rep_min INTEGER NOT NULL,
    rep_max INTEGER NOT NULL,
    rir_target INTEGER NOT NULL,
    energy INTEGER NOT NULL,
    sleep INTEGER NOT NULL,
    soreness TEXT NOT NULL,
    technique TEXT NOT NULL,
    bodyweight_kg REAL,
    notes TEXT,
    below_min INTEGER NOT NULL,
    volume_load REAL,
    e1rm_added REAL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS set_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES training_session(id) ON DELETE CASCADE,
    set_number INTEGER NOT NULL,
    load_kg REAL NOT NULL,
    reps INTEGER NOT NULL,
    rir INTEGER
);
CREATE TABLE IF NOT EXISTS smartload_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL UNIQUE REFERENCES training_session(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    message TEXT NOT NULL,
    reasons_json TEXT NOT NULL,
    notes_json TEXT NOT NULL,
    current_load_kg REAL,
    suggested_load_kg REAL,
    current_system_kg REAL,
    suggested_system_kg REAL,
    change_pct REAL,
    comparison_session_id INTEGER,
    rule_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@contextmanager
def connect(db_path: str = DEFAULT_DB):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str = DEFAULT_DB) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        for key, lift in LIFTS.items():
            d = lift.defaults
            conn.execute(
                "INSERT OR IGNORE INTO lift_config VALUES (?,?,?,?,?,?,?,?)",
                (key, d.target_sets, d.rep_min, d.rep_max, d.rir_target,
                 d.increment_kg, d.max_increase_pct, 5.0))
        conn.execute("INSERT OR IGNORE INTO app_settings VALUES ('low_wellbeing_threshold', '2')")
    _backfill_e1rm(db_path)


def _backfill_e1rm(db_path: str = DEFAULT_DB) -> None:
    """Recalcula el e1RM guardado de cada sesión (por si cambió la regla de cálculo)."""
    with connect(db_path) as conn:
        sessions = conn.execute("SELECT id, lift_key, bodyweight_kg, e1rm_added FROM training_session").fetchall()
        for r in sessions:
            sets = conn.execute("SELECT load_kg, reps FROM set_record WHERE session_id = ?", (r["id"],)).fetchall()
            sd = [{"load_kg": s["load_kg"], "reps": s["reps"]} for s in sets]
            lift = LIFTS.get(r["lift_key"])
            if not lift or (lift.uses_bodyweight and r["bodyweight_kg"] is None):
                continue
            best = session_e1rm(sd, r["bodyweight_kg"], lift.uses_bodyweight)
            val = best["e1rm_added"] if best else None
            if val != r["e1rm_added"]:
                conn.execute("UPDATE training_session SET e1rm_added = ? WHERE id = ?", (val, r["id"]))


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
def get_setting(key: str, default=None, db_path: str = DEFAULT_DB):
    with connect(db_path) as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value, db_path: str = DEFAULT_DB) -> None:
    with connect(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO app_settings VALUES (?, ?)", (key, str(value)))


def get_lift_config(lift_key: str, db_path: str = DEFAULT_DB) -> dict:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM lift_config WHERE lift_key = ?", (lift_key,)).fetchone()
    return dict(row)


def save_lift_config(lift_key: str, cfg: dict, db_path: str = DEFAULT_DB) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """UPDATE lift_config SET target_sets=?, rep_min=?, rep_max=?, rir_target=?,
               increment_kg=?, max_increase_pct=?, decrease_pct=? WHERE lift_key=?""",
            (cfg["target_sets"], cfg["rep_min"], cfg["rep_max"], cfg["rir_target"],
             cfg["increment_kg"], cfg["max_increase_pct"], cfg["decrease_pct"], lift_key))


def settings_for(lift_key: str, db_path: str = DEFAULT_DB) -> Settings:
    cfg = get_lift_config(lift_key, db_path)
    return Settings(increment_kg=cfg["increment_kg"], max_increase_pct=cfg["max_increase_pct"],
                    decrease_pct=cfg["decrease_pct"],
                    low_wellbeing_threshold=int(get_setting("low_wellbeing_threshold", 2, db_path)))


# ---------------------------------------------------------------------------
# Historial para SmartLoad
# ---------------------------------------------------------------------------
def get_history(lift_key: str, db_path: str = DEFAULT_DB) -> list:
    """Sesiones anteriores del ejercicio como PreviousSession, la más reciente primero."""
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM training_session WHERE lift_key = ?
               ORDER BY session_date DESC, id DESC""", (lift_key,)).fetchall()
    return [PreviousSession(id=r["id"], lift_key=r["lift_key"], variant=r["variant"],
                            session_type=r["session_type"], target_sets=r["target_sets"],
                            rep_min=r["rep_min"], rep_max=r["rep_max"], rir_target=r["rir_target"],
                            below_min=bool(r["below_min"])) for r in rows]


def analyze_and_save(s: SessionInput, session_date: date, notes: str = "",
                     db_path: str = DEFAULT_DB):
    """
    Evalúa la sesión con SmartLoad y, si los datos son válidos, la guarda
    junto con sus series y el resultado. Devuelve (resultado, session_id).
    Si el resultado es INCOMPLETO no se guarda nada (session_id = None).
    """
    result = evaluate(s, get_history(s.lift_key, db_path))
    if result.status == "INCOMPLETO":
        return result, None

    lift = LIFTS[s.lift_key]
    bw = s.checkin.bodyweight_kg
    set_dicts = [{"load_kg": st.load_kg, "reps": st.reps} for st in s.sets]
    vol = volume_load(set_dicts, bw, lift.uses_bodyweight)
    best = session_e1rm(set_dicts, bw, lift.uses_bodyweight)
    now = datetime.now().isoformat(timespec="seconds")

    with connect(db_path) as conn:   # una sola transacción
        cur = conn.execute(
            """INSERT INTO training_session (session_date, lift_key, variant, session_type,
               target_sets, rep_min, rep_max, rir_target, energy, sleep, soreness, technique,
               bodyweight_kg, notes, below_min, volume_load, e1rm_added, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (session_date.isoformat(), s.lift_key, s.variant, s.session_type, s.target_sets,
             s.rep_min, s.rep_max, s.rir_target, s.checkin.energy, s.checkin.sleep,
             s.checkin.soreness, s.checkin.technique, bw, notes.strip() or None,
             int(bool(below_minimum(s.sets, s.rep_min))), vol,
             best["e1rm_added"] if best else None, now))
        sid = cur.lastrowid
        conn.executemany(
            "INSERT INTO set_record (session_id, set_number, load_kg, reps, rir) VALUES (?,?,?,?,?)",
            [(sid, i, st.load_kg, st.reps, st.rir if st.reps > 0 else None)
             for i, st in enumerate(s.sets, start=1)])
        conn.execute(
            """INSERT INTO smartload_result (session_id, status, message, reasons_json, notes_json,
               current_load_kg, suggested_load_kg, current_system_kg, suggested_system_kg,
               change_pct, comparison_session_id, rule_version, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, result.status, result.message, json.dumps(result.reasons, ensure_ascii=False),
             json.dumps(result.notes, ensure_ascii=False), result.current_load_kg,
             result.suggested_load_kg, result.current_system_kg, result.suggested_system_kg,
             result.change_pct, result.comparison_session_id, result.rule_version, now))
    return result, sid


# ---------------------------------------------------------------------------
# Consultas para la interfaz
# ---------------------------------------------------------------------------
_SESSION_QUERY = """
SELECT ts.*, r.status, r.message, r.reasons_json, r.notes_json, r.current_load_kg,
       r.suggested_load_kg, r.current_system_kg, r.change_pct, r.rule_version
FROM training_session ts LEFT JOIN smartload_result r ON r.session_id = ts.id
"""


def list_sessions(lift_key=None, variant=None, session_type=None, db_path: str = DEFAULT_DB) -> list:
    where, params = [], []
    for col, val in (("ts.lift_key", lift_key), ("ts.variant", variant), ("ts.session_type", session_type)):
        if val:
            where.append(f"{col} = ?")
            params.append(val)
    sql = _SESSION_QUERY + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY ts.session_date DESC, ts.id DESC"
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["reasons"] = json.loads(d.pop("reasons_json") or "[]")
        d["notes_list"] = json.loads(d.pop("notes_json") or "[]")
        out.append(d)
    return out


def get_sets(session_id: int, db_path: str = DEFAULT_DB) -> list:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT set_number, load_kg, reps, rir FROM set_record "
                            "WHERE session_id = ? ORDER BY set_number", (session_id,)).fetchall()
    return [dict(r) for r in rows]


def last_session(lift_key: str, variant=None, session_type=None, db_path: str = DEFAULT_DB):
    rows = list_sessions(lift_key, variant, session_type, db_path)
    return rows[0] if rows else None


def last_bodyweight(db_path: str = DEFAULT_DB):
    with connect(db_path) as conn:
        row = conn.execute("SELECT bodyweight_kg FROM training_session WHERE bodyweight_kg IS NOT NULL "
                           "ORDER BY session_date DESC, id DESC LIMIT 1").fetchone()
    return row["bodyweight_kg"] if row else None


def best_e1rm_added(lift_key: str, db_path: str = DEFAULT_DB):
    """Récord personal (mayor e1RM de lastre/barra) del ejercicio."""
    with connect(db_path) as conn:
        row = conn.execute("SELECT MAX(e1rm_added) AS m FROM training_session WHERE lift_key = ?",
                           (lift_key,)).fetchone()
    return row["m"]


def count_sessions(db_path: str = DEFAULT_DB) -> int:
    with connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM training_session").fetchone()[0]


def export_csv(db_path: str = DEFAULT_DB) -> str:
    """CSV con una fila por serie, incluyendo los datos de su sesión y del semáforo."""
    sql = """
    SELECT ts.id AS session_id, ts.session_date, ts.lift_key, ts.variant, ts.session_type,
           ts.target_sets, ts.rep_min, ts.rep_max, ts.rir_target, ts.energy, ts.sleep,
           ts.soreness, ts.technique, ts.bodyweight_kg, ts.volume_load, ts.e1rm_added,
           sr.set_number, sr.load_kg, sr.reps, sr.rir,
           r.status, r.suggested_load_kg, r.change_pct, r.rule_version, ts.notes
    FROM training_session ts
    JOIN set_record sr ON sr.session_id = ts.id
    LEFT JOIN smartload_result r ON r.session_id = ts.id
    ORDER BY ts.session_date, ts.id, sr.set_number"""
    with connect(db_path) as conn:
        cur = conn.execute(sql)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    w.writerows([tuple(r) for r in rows])
    return buf.getvalue()


def reset_all(db_path: str = DEFAULT_DB) -> None:
    """Borra todas las sesiones (la configuración se mantiene)."""
    with connect(db_path) as conn:
        conn.execute("DELETE FROM smartload_result")
        conn.execute("DELETE FROM set_record")
        conn.execute("DELETE FROM training_session")


# ---------------------------------------------------------------------------
# Datos de demostración
# ---------------------------------------------------------------------------
# Para cada ejercicio: variante, tipo y una secuencia de sesiones
# (repeticiones por serie, RIR por serie, check-in opcional).
# La carga NO se escribe a mano: se sigue la sugerencia del semáforo,
# así la demo muestra el sistema funcionando de verdad.
_DEMO = {
    "dominada": ("Prono", "Intensidad", 15.0, [
        ([5, 4, 4], [2, 2, 1], {}),
        ([5, 5, 4], [2, 2, 2], {}),
        ([5, 5, 5], [2, 2, 2], {}),          # SUBIR
        ([5, 4, 4], [2, 1, 1], {}),
        ([5, 5, 5], [3, 2, 2], {"sleep": 2}),  # MANTENER por sueño
        ([5, 5, 5], [3, 2, 2], {}),          # SUBIR
        ([5, 4, 3], [1, 1, 1], {}),
    ]),
    "fondos": ("Paralelas", "Volumen", 20.0, [
        ([8, 7, 6], [2, 2, 1], {}),
        ([8, 8, 7], [2, 2, 2], {}),
        ([8, 8, 8], [3, 2, 2], {}),          # SUBIR
        ([7, 7, 6], [2, 2, 1], {}),
        ([8, 8, 8], [2, 2, 2], {}),          # SUBIR
        ([6, 6, 5], [1, 1, 0], {"soreness": "leves"}),
    ]),
    "sentadilla": ("Barra baja", "Intensidad", 100.0, [
        ([5, 5, 4], [2, 2, 2], {}),
        ([5, 5, 5], [2, 2, 2], {}),          # SUBIR
        ([5, 5, 5], [2, 2, 2], {}),          # SUBIR
        ([3, 2, 2], [0, 0, 0], {}),          # fallo puntual
        ([3, 2, 2], [0, 0, 0], {}),          # BAJAR
        ([5, 5, 4], [2, 2, 1], {}),
    ]),
    "muscle_up": ("Estricto", "Técnica", 0.0, [
        ([3, 2, 2], [1, 1, 0], {}),
        ([3, 3, 2], [1, 1, 1], {}),
        ([3, 3, 3], [2, 1, 1], {}),          # SUBIR a 1,25 kg (doble progresión)
        ([3, 3, 2], [1, 1, 1], {"technique": "revisar"}),  # ALERTA
    ]),
}


def seed_demo(db_path: str = DEFAULT_DB, bodyweight: float = 75.0, start: date | None = None) -> int:
    """Borra las sesiones y carga un historial de ejemplo (~6 semanas). Devuelve cuántas creó."""
    init_db(db_path)
    reset_all(db_path)
    start = start or (date.today() - timedelta(days=42))
    created = 0
    for offset, (lift_key, (variant, stype, load, plan)) in enumerate(_DEMO.items()):
        cfg = get_lift_config(lift_key, db_path)
        settings = settings_for(lift_key, db_path)
        for i, (reps, rirs, extra) in enumerate(plan):
            ci = dict(energy=4, sleep=4, soreness="ninguna", technique="adecuada",
                      bodyweight_kg=round(bodyweight - 0.1 * (i % 3), 1))
            ci.update(extra)
            s = SessionInput(lift_key, variant, stype, cfg["target_sets"], cfg["rep_min"],
                             cfg["rep_max"], cfg["rir_target"],
                             [SetEntry(load, r, x) for r, x in zip(reps, rirs)],
                             CheckIn(**ci), settings)
            result, sid = analyze_and_save(s, start + timedelta(days=i * 6 + offset), "Dato de ejemplo",
                                           db_path)
            if sid:
                created += 1
            if result.suggested_load_kg is not None:
                load = result.suggested_load_kg
    return created


def rir_calibration(lift_key: str, variant: str | None = None, db_path: str = DEFAULT_DB) -> dict:
    """
    Calibración del RIR para un ejercicio (y variante, si se indica).
    Devuelve {"points": [...], "summary": {...}} usando insights.py.
    Las variantes se calibran por separado (una prona y una supina no se mezclan).
    """
    from insights import calibration_points, calibration_summary
    rows = list(reversed(list_sessions(lift_key, variant, None, db_path)))  # cronológico
    by_variant = {}
    for r in rows:
        sets = get_sets(r["id"], db_path)
        first = sets[0] if sets else None
        by_variant.setdefault(r["variant"], []).append(
            {"id": r["id"], "session_date": r["session_date"], "bodyweight_kg": r["bodyweight_kg"],
             "e1rm_added": r["e1rm_added"], "first_set": first})
    points = []
    for sessions in by_variant.values():
        points += calibration_points(sessions, LIFTS[lift_key].uses_bodyweight)
    points.sort(key=lambda p: (p["session_date"], p["session_id"]))
    return {"points": points, "summary": calibration_summary([p["gap"] for p in points])}


def session_summary(row: dict, sets: list) -> dict:
    """Indicadores para mostrar el detalle de una sesión guardada."""
    lift = LIFTS[row["lift_key"]]
    sd = [{"load_kg": s["load_kg"], "reps": s["reps"]} for s in sets]
    return {
        "volume": row["volume_load"],
        "compliance": compliance(sd, row["target_sets"], row["rep_min"]),
        "e1rm": session_e1rm(sd, row["bodyweight_kg"], lift.uses_bodyweight),
    }
