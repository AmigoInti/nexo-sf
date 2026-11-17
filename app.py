"""
app.py — Interfaz de NEXO SF (Streamlit).

Ejecutar desde la carpeta del proyecto:
    conda activate nexosf
    streamlit run app.py

La interfaz solo muestra y recoge datos. Las decisiones las toma
smartload.py y el guardado lo hace database.py.
"""

import html
from datetime import date

import pandas as pd
import streamlit as st

import database as db
from calculations import estimated_total, plate_breakdown, relative_strength
from insights import readiness, warmup_plan
from lifts import LIFTS, SESSION_TYPES, SORENESS_LEVELS, TECHNIQUE_LEVELS
from smartload import RULE_VERSION, STATUS_STYLE, CheckIn, SessionInput, SetEntry, n

st.set_page_config(page_title="NEXO SF", page_icon="🚦", layout="centered",
                   initial_sidebar_state="collapsed")
db.init_db()

LIGHTS = [("BAJAR", "#EF4444"), ("MANTENER", "#FACC15"), ("SUBIR", "#22C55E")]
DOT = {"SUBIR": "green", "MANTENER": "orange", "BAJAR": "red", "ALERTA": "violet",
       "LINEA_BASE": "gray", "INCOMPLETO": "gray"}  # colores de texto de Streamlit
PAGES = ["Inicio", "Registrar", "Historial", "Guía", "Ajustes"]

# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,500;0,600;0,700;0,800;1,800&family=Barlow:wght@400;500;600;700&display=swap');

:root {
  --bg:#0A0A0A; --surface:#141414; --surface2:#1C1C1C; --line:#2A2A2A;
  --text:#F5F5F5; --muted:#9A9A9A; --cond:'Barlow Condensed', 'Arial Narrow', sans-serif;
}
html, body, .stApp, p, label, input, textarea, li, button, h1, h2, h3, h4, h5, h6,
[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] {
  font-family: 'Barlow', system-ui, sans-serif;
}
.stApp {background: var(--bg);}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {display:none !important;}
header[data-testid="stHeader"] {background: transparent; height: 0;}
.block-container {padding-top: 2.6rem !important; padding-bottom: 4rem; max-width: 620px;}
h1, h2, h3, h4, h5 {font-family: var(--cond) !important; text-transform: uppercase; letter-spacing:.02em;}
[data-testid="stCaptionContainer"] p {color: var(--muted);}

/* ---------- Marca ---------- */
.nx-brand {display:flex; align-items:flex-end; justify-content:space-between; gap:.5rem;
           padding: .4rem 0 .5rem; margin-bottom:0;}
.nx-logo {font-family: var(--cond); font-weight:800; font-style:italic; font-size:2.6rem;
          line-height:1.05; letter-spacing:-.01em; padding-right:.15em; white-space:nowrap;}
.nx-logo .sf {color: transparent; -webkit-text-stroke: 1.6px var(--text); margin-left:.12em;}
.nx-tag {font-family: var(--cond); font-weight:600; font-size:.78rem; letter-spacing:.22em;
         color: var(--muted); text-transform:uppercase; text-align:right; line-height:1.3; padding-bottom:.45rem;}

/* ---------- Pestañas (radio estilizado) ----------
   Estructura real de Streamlit:
   radiogroup > div[data-selected] > label[stRadioOption] > span(input) + div > [div(círculo), stMarkdownContainer > p] */
[class*="st-key-nxtab_"] [data-testid="stElementContainer"],
[class*="st-key-nxtab_"] [data-testid="stRadio"] {width:100% !important;}
[class*="st-key-nxtab_"] [role="radiogroup"] {display:flex !important; flex-wrap:nowrap !important; gap:0 !important;
  width:100% !important; border-bottom:1px solid var(--line);}
[class*="st-key-nxtab_"] [role="radiogroup"] > div {flex:1 1 0 !important; min-width:0 !important; display:flex !important;
  margin:0 !important; padding:0 !important; border-bottom:3px solid transparent;}
[class*="st-key-nxtab_"] [role="radiogroup"] > div[data-selected="true"] {border-bottom-color: var(--text);}
[class*="st-key-nxtab_"] [data-testid="stRadioOption"] {width:100% !important; justify-content:center !important;
  margin:0 !important; padding:.75rem .1rem .6rem !important; cursor:pointer;}
/* oculta el círculo: todo bloque dentro de la opción que NO contiene el texto */
[class*="st-key-nxtab_"] [data-testid="stRadioOption"] div:not(:has(p)):not([data-testid="stMarkdownContainer"] *) {display:none !important;}
[class*="st-key-nxtab_"] [data-testid="stRadioOption"] div:has(p) {padding-left:0 !important; margin-left:0 !important; gap:0 !important;
  width:100% !important; justify-content:center !important; text-align:center !important;}
[class*="st-key-nxtab_"] [data-testid="stRadioOption"] p {font-family: var(--cond) !important; font-weight:700 !important;
  text-transform:uppercase !important; letter-spacing:.06em; font-size:1rem !important; color: var(--muted) !important;
  white-space:nowrap; text-align:center; margin:0 !important;}
[class*="st-key-nxtab_"] [data-selected="true"] p {color: var(--text) !important;}
[class*="st-key-nxtab_"] [data-testid="stRadioOption"]:hover p {color: var(--text) !important;}
/* oculta el aviso "Press Enter to submit form" que se encima en los campos */
[data-testid="InputInstructions"] {display:none !important;}

/* ---------- Botones ---------- */
.stButton button, .stFormSubmitButton button, .stDownloadButton button {
  width:100%; border-radius:6px; min-height:3.1rem; border:1px solid var(--line);}
.stButton button p, .stFormSubmitButton button p, .stDownloadButton button p {
  font-family: var(--cond) !important; font-weight:800 !important; text-transform:uppercase;
  letter-spacing:.12em; font-size:1.05rem !important;}
button[kind="primary"], button[kind="primaryFormSubmit"], button[data-testid^="stBaseButton-primary"] {
  background: var(--text) !important; border-color: var(--text) !important;}
button[kind="primary"] p, button[kind="primaryFormSubmit"] p, button[data-testid^="stBaseButton-primary"] p {
  color: #0A0A0A !important;}
button[kind="primary"]:hover, button[data-testid^="stBaseButton-primary"]:hover {background:#D9D9D9 !important;}

/* ---------- Bloques ---------- */
[data-testid="stExpander"] details {border-radius:6px !important; border-color: var(--line) !important; background: var(--surface);}
[data-testid="stExpander"] summary p {font-family: var(--cond) !important; font-weight:700; text-transform:uppercase; letter-spacing:.06em;}
.nx-eyebrow {font-family: var(--cond); font-weight:700; font-size:.8rem; letter-spacing:.25em;
             color: var(--muted); text-transform: uppercase; margin: 1.1rem 0 .5rem;}
.nx-hero {padding: .2rem 0 .6rem;}
.nx-h1 {font-family: var(--cond); font-weight:800; font-size:2.7rem; line-height:.95; text-transform:uppercase;}
.nx-h1 .dim {color: var(--muted);}
.nx-step {font-family: var(--cond); font-weight:800; font-size:1.35rem; text-transform:uppercase;
          letter-spacing:.03em; margin: 1.3rem 0 .3rem; display:flex; align-items:center; gap:.6rem;}
.nx-step .num {display:inline-flex; width:1.7rem; height:1.7rem; align-items:center; justify-content:center;
               background: var(--text); color:#0A0A0A; border-radius:4px; font-size:1rem;}

/* ---------- Tarjeta del semáforo ---------- */
.nx-card {background: var(--surface); border:1px solid var(--line); border-top: 4px solid var(--c);
          border-radius:8px; padding:1.1rem 1.15rem; margin:.6rem 0 1rem;}
.nx-top {display:flex; gap:1rem; align-items:center;}
.nx-tl {background:#050505; border:1px solid var(--line); border-radius:10px; padding:6px;
        display:flex; flex-direction:column; gap:6px;}
.nx-tl span {width:18px; height:18px; border-radius:50%; display:block;}
.nx-status {font-family: var(--cond); font-weight:800; font-size:2.4rem; color:var(--c);
            letter-spacing:.01em; line-height:.9; text-transform:uppercase;}
.nx-load {font-family: var(--cond); font-weight:600; font-size:1.2rem; margin-top:.3rem; text-transform:uppercase; letter-spacing:.03em;}
.nx-msg {margin:.9rem 0 .4rem; font-size:1rem; line-height:1.45;}
.nx-why-t {font-family: var(--cond); font-weight:700; font-size:.78rem; letter-spacing:.22em;
           text-transform:uppercase; color: var(--muted); margin-top:.6rem;}
.nx-why {font-size:.9rem; margin:.25rem 0 0; padding-left:1.1rem; color:#D4D4D4;}
.nx-note {font-size:.78rem; color: var(--muted); margin-top:.5rem;}

/* ---------- Semáforo previo / calibración ---------- */
.nx-ready {background: var(--surface); border:1px solid var(--line); border-left:4px solid var(--c);
           border-radius:8px; padding:.75rem .9rem; margin:.7rem 0 .4rem;}
.nx-ready .nx-why-t {margin-top:0;}
.nx-ready .t {font-family: var(--cond); font-weight:800; font-size:1.35rem; text-transform:uppercase; color: var(--c); line-height:1.1;}
.nx-ready .x {font-size:.9rem; color:#D4D4D4; margin-top:.2rem; line-height:1.4;}
/* ---------- Calentamiento ---------- */
table.nx-warm {width:100%; border-collapse:collapse; font-size:.9rem; margin:.3rem 0 .2rem;}
table.nx-warm td {padding:.45rem .3rem; border-bottom:1px solid var(--line); vertical-align:middle;}
table.nx-warm td:first-child {font-family: var(--cond); font-weight:800; color: var(--muted); width:1.6rem;}
table.nx-warm td.d {color: var(--muted); font-size:.8rem; text-align:right;}
table.nx-warm tr.w td {border-bottom:none; color: var(--text);}
table.nx-warm tr.h td {font-family: var(--cond); font-weight:700; font-size:.72rem; letter-spacing:.15em;
                       text-transform:uppercase; color: var(--muted); padding-top:0;}
table.nx-warm tr.w td:first-child {color: var(--text);}

/* ---------- Tarjetas de ejercicio y KPIs ---------- */
.nx-lift {background: var(--surface); border:1px solid var(--line); border-radius:8px;
          padding:.85rem .9rem; margin-bottom:.6rem; min-height:132px;}
.nx-lift .name {font-family: var(--cond); font-weight:800; font-size:1.15rem; text-transform:uppercase; letter-spacing:.04em;}
.nx-lift .big {font-family: var(--cond); font-weight:800; font-size:2rem; line-height:1.05; margin-top:.2rem;}
.nx-lift .big small {font-size:1rem; color: var(--muted); font-weight:600;}
.nx-lift .sub {font-size:.75rem; color: var(--muted);}
.nx-pill {display:inline-flex; align-items:center; gap:.35rem; font-family: var(--cond); font-weight:700;
          font-size:.78rem; letter-spacing:.12em; text-transform:uppercase; padding:.15rem .5rem;
          border-radius:999px; border:1px solid var(--line); margin-top:.35rem;}
.nx-dot {display:inline-block; width:8px; height:8px; border-radius:50%;}
.nx-kpi {background: var(--surface); border:1px solid var(--line); border-radius:8px; padding:.7rem .8rem;}
.nx-kpi .v {font-family: var(--cond); font-weight:800; font-size:1.7rem; line-height:1.1;}
.nx-kpi .l {font-family: var(--cond); font-weight:600; font-size:.72rem; letter-spacing:.14em;
            text-transform:uppercase; color: var(--muted);}
.nx-foot {font-size:.72rem; color: var(--muted); opacity:.7; text-align:center; margin-top:2.2rem;}

/* ---------- Celular ---------- */
@media (max-width: 640px) {
  .block-container {padding-left: 1rem !important; padding-right: 1rem !important;}
  div[data-testid="stHorizontalBlock"] {flex-wrap: nowrap !important; gap: .5rem !important;}
  div[data-testid="stHorizontalBlock"] > div {min-width: 0 !important; flex: 1 1 0 !important; width: auto !important;}
  button[data-testid="stNumberInputStepUp"], button[data-testid="stNumberInputStepDown"] {display:none !important;}
  .nx-logo {font-size:2.2rem;}
  .nx-tag {font-size:.62rem; letter-spacing:.16em;}
  .nx-h1 {font-size:2.2rem;}
  [class*="st-key-nxtab_"] [data-testid="stRadioOption"] p {font-size:.86rem !important; letter-spacing:.03em;}
  .st-key-nxtab_nav [data-testid="stRadioOption"] p {font-size:.8rem !important; letter-spacing:.02em;}
  .block-container {padding-top: 1.6rem !important;}
  .nx-kpi .v {font-size:1.35rem;}
  .nx-kpi {padding:.6rem .65rem;}
  .nx-kpi .l {font-size:.62rem; letter-spacing:.06em;}
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Utilidades de interfaz
# ---------------------------------------------------------------------------
def fdate(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}-{m}-{y}"


def choice(label, options, key, format_func=str):
    """Pestañas: un radio horizontal estilizado como tabs (ver CSS .st-key-nxtab_*)."""
    with st.container(key=f"nxtab_{key}"):
        val = st.radio(label, options, key=key, format_func=format_func, horizontal=True,
                       label_visibility="collapsed")
    return val if val is not None else options[0]


def go(page: str):
    st.session_state["nav"] = page


def lift_label(key: str) -> str:
    return LIFTS[key].name


def unit_for(lift_key: str) -> str:
    return "de lastre" if LIFTS[lift_key].uses_bodyweight else "en barra"


def result_card(status, message, reasons, notes=(), lift_key=None, suggested=None):
    """Tarjeta del semáforo. Nunca depende solo del color: siempre hay palabra y explicación."""
    sty = STATUS_STYLE[status]
    lights = "".join(
        f'<span style="background:{c if s == status else "#232323"};'
        f'box-shadow:{"0 0 16px 4px " + c if s == status else "none"}"></span>'
        for s, c in LIGHTS)
    if status in ("SUBIR", "MANTENER", "BAJAR") and suggested is not None:
        headline = f"Próxima sesión: {n(suggested)} kg {unit_for(lift_key)}"
    elif status == "LINEA_BASE" and suggested is not None:
        headline = f"Referencia: {n(suggested)} kg {unit_for(lift_key)}"
    elif status == "ALERTA":
        headline = "Sin recomendación de carga"
    else:
        headline = ""
    why = "".join(f"<li>{html.escape(r)}</li>" for r in reasons)
    note = "".join(f"<div class='nx-note'>{html.escape(x)}</div>" for x in notes)
    st.markdown(f"""
<div class="nx-card" style="--c:{sty['color']}">
  <div class="nx-top">
    <div class="nx-tl">{lights}</div>
    <div><div class="nx-status">{sty['label']}</div>
         <div class="nx-load">{headline}</div></div>
  </div>
  <div class="nx-msg">{html.escape(message)}</div>
  <div class="nx-why-t">Por qué</div>
  <ul class="nx-why">{why}</ul>
  {note}
</div>""", unsafe_allow_html=True)


def eyebrow(text: str):
    st.markdown(f"<div class='nx-eyebrow'>{html.escape(text)}</div>", unsafe_allow_html=True)


def step(num: int, text: str):
    st.markdown(f"<div class='nx-step'><span class='num'>{num}</span>{html.escape(text)}</div>",
                unsafe_allow_html=True)


DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def today_label() -> str:
    t = date.today()
    return f"{DIAS[t.weekday()]} {t.day} {MESES[t.month - 1]}"


def discs_text(load: float, uses_bodyweight: bool) -> str:
    """Texto corto con los discos necesarios (cinturón: total; barra: por lado)."""
    if uses_bodyweight:
        if load <= 0:
            return "sin lastre"
        pb = plate_breakdown(load)
    else:
        if load <= 20:
            return "barra sola"
        pb = plate_breakdown(load, bar_kg=20, per_side=True)
    txt = " + ".join(n(x) for x in pb["plates"]) + ("" if uses_bodyweight else " /lado")
    return txt + (f" (faltan {n(pb['leftover'])})" if pb["leftover"] else "")


def calibration_card(cal: dict, today=None):
    """Tarjeta de calibración del RIR (resumen + comparación de la sesión de hoy si existe)."""
    sm = cal["summary"]
    color = "#9A9A9A" if not sm["ready"] else ("#22C55E" if abs(sm["mean"]) <= 1 else "#FACC15")
    today_html = ""
    if today:
        today_html = (f"<div class='x' style='margin-top:.4rem'><b>Hoy, primera serie:</b> reportaste RIR "
                      f"{today['reported']} · tu e1RM reciente estima ≈ {n(today['predicted'])}.</div>")
    st.markdown(f"""<div class="nx-ready" style="--c:{color}">
      <div class="nx-why-t">Calibración de tu RIR</div>
      <div class="t">{sm['title']}</div><div class="x">{html.escape(sm['text'])}</div>{today_html}</div>""",
                unsafe_allow_html=True)


def kpi(col, value, label):
    col.markdown(f"<div class='nx-kpi'><div class='v'>{value}</div><div class='l'>{label}</div></div>",
                 unsafe_allow_html=True)


def disclaimer():
    st.markdown("<div class='nx-foot'>NEXO SF orienta el entrenamiento; no diagnostica lesiones "
                "ni reemplaza a tu entrenador. RIR y bienestar son autorreportados; el e1RM es una "
                f"estimación. Reglas: {RULE_VERSION}</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Encabezado y navegación
# ---------------------------------------------------------------------------
st.markdown("""<div class="nx-brand"><span class="nx-logo">NEXO<span class="sf">SF</span></span>
<span class="nx-tag">Street Lifting<br>Semáforo de carga</span></div>""", unsafe_allow_html=True)

page = choice("Menú", PAGES, key="nav")


# ---------------------------------------------------------------------------
# INICIO
# ---------------------------------------------------------------------------
def page_home():
    total_sessions = db.count_sessions()
    if total_sessions == 0:
        st.markdown(f"""<div class="nx-hero"><div class="nx-eyebrow">{today_label()}</div>
        <div class="nx-h1">Entrena.<br>Registra.<br><span class="dim">Progresa.</span></div></div>
        <p style="color:#9A9A9A">Registra tu primera sesión para iniciar el historial. El semáforo necesita
        una sesión de referencia antes de recomendarte subir, mantener o bajar.</p>""",
                    unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.button("Registrar sesión", type="primary", on_click=go, args=(PAGES[1],))
        if c2.button("Cargar demo"):
            db.seed_demo()
            st.rerun()
    else:
        st.markdown(f"""<div class="nx-hero"><div class="nx-eyebrow">{today_label()}</div>
        <div class="nx-h1">Tu próxima carga,<br><span class="dim">explicada.</span></div></div>""",
                    unsafe_allow_html=True)
        st.button("Registrar sesión", type="primary", on_click=go, args=(PAGES[1],))

        # KPIs: peso corporal, total estimado, fuerza relativa
        bw = db.last_bodyweight()
        latest = {k: (db.last_session(k) or {}).get("e1rm_added") for k in LIFTS}
        tot = estimated_total(latest)
        rel = relative_strength(tot["total"], bw) if bw and tot["complete"] else None
        c1, c2, c3 = st.columns(3)
        kpi(c1, f"{n(bw)} kg" if bw else "—", "Peso corporal")
        kpi(c2, f"{n(tot['total'])} kg" if tot["total"] else "—", "Total est." + ("" if tot["complete"] else "*"))
        kpi(c3, f"{n(rel)}x" if rel else "—", "Fuerza relativa")
        st.caption("Total estimado = suma de los e1RM de lastre (y barra en sentadilla) más recientes. "
                   "Descriptivo, no oficial." + (" *Falta registrar algún ejercicio." if not tot["complete"] else ""))

        eyebrow("Tus ejercicios")
        keys = list(LIFTS)
        for row_keys in (keys[:2], keys[2:]):
            cols = st.columns(2)
            for col, k in zip(cols, row_keys):
                last = db.last_session(k)
                if last is None:
                    col.markdown(f"<div class='nx-lift'><div class='name'>{lift_label(k)}</div>"
                                 "<div class='big'>—</div><div class='sub'>Sin registros todavía</div></div>",
                                 unsafe_allow_html=True)
                    continue
                sty = STATUS_STYLE[last["status"]]
                nxt = last["suggested_load_kg"]
                pr = db.best_e1rm_added(k)
                big = f"{n(nxt)}<small> kg</small>" if nxt is not None else "—"
                col.markdown(f"""<div class='nx-lift'><div class='name'>{lift_label(k)}</div>
                <div class='big'>{big}</div>
                <div class='sub'>próxima sesión · {html.escape(last['variant'])}</div>
                <span class='nx-pill'><span class='nx-dot' style='background:{sty["color"]}'></span>{sty['label']}</span>
                <div class='sub' style='margin-top:.35rem'>PR e1RM {n(pr) + ' kg' if pr is not None else '—'} · {fdate(last['session_date'])}</div></div>""",
                             unsafe_allow_html=True)

    with st.expander("¿Cómo decide el semáforo?"):
        st.markdown("""
Las reglas se revisan **en este orden** y la primera que se cumple decide:

1. **⚫ Datos incompletos**: falta algo o hay un valor inválido. No se analiza.
2. **🟣 ALERTA**: molestia importante o técnica marcada "revisar". No se recomienda carga.
3. **⚪ LÍNEA BASE**: primera sesión comparable (mismo ejercicio, variante, tipo y objetivos).
4. **Reps bajo el mínimo**: si también pasó en la sesión anterior → **🔴 BAJAR** (≈5 % de la carga
   del sistema, redondeado a tus discos). Si es la primera vez → **🟡 MANTENER**.
5. **🟡 MANTENER**: alguna serie no llegó al tope del rango o quedó con RIR menor al objetivo.
6. **🟡 MANTENER**: rendiste perfecto, pero dormiste mal, tienes poca energía o molestias leves.
7. **🟡 MANTENER**: el salto de carga disponible supera tu límite (5 % por defecto).
8. **🟢 SUBIR**: todas las series en el tope con el RIR objetivo.

**Carga del sistema.** En dominada, fondos y muscle-up movemos el cuerpo + el lastre. Por eso los
porcentajes se calculan sobre *peso corporal + lastre*: subir 2,5 kg con 75 kg de peso corporal y
20 kg de lastre es +2,6 %, no +12,5 %.

**Doble progresión.** Sin lastre se progresa en repeticiones; al llegar al tope del rango, el
semáforo sugiere empezar con el lastre mínimo disponible.

*Los umbrales son decisiones de diseño del prototipo y se pueden cambiar en Ajustes.*
""")
    disclaimer()


# ---------------------------------------------------------------------------
# REGISTRAR
# ---------------------------------------------------------------------------
def page_register():
    lift_key = choice("Ejercicio", list(LIFTS), key="reg_lift", format_func=lift_label)
    lift = LIFTS[lift_key]
    cfg = db.get_lift_config(lift_key)

    c1, c2 = st.columns(2)
    variant = c1.selectbox("Variante", lift.variants, key=f"var_{lift_key}")
    stype = c2.selectbox("Tipo de sesión", SESSION_TYPES, index=2, key=f"type_{lift_key}")

    k = lambda name: f"{name}_{lift_key}"  # noqa: E731  (claves de widgets por ejercicio)
    for name in ("target_sets", "rep_min", "rep_max", "rir_target"):
        st.session_state.setdefault(k(name), int(cfg[name]))
    summary = (f"{st.session_state[k('target_sets')]} x {st.session_state[k('rep_min')]}-"
               f"{st.session_state[k('rep_max')]} reps @ RIR {st.session_state[k('rir_target')]}")
    with st.expander(f"Objetivo · {summary}"):
        a, b = st.columns(2)
        a.number_input("Series", 1, 10, step=1, key=k("target_sets"))
        b.number_input("RIR objetivo", 0, 5, step=1, key=k("rir_target"))
        a.number_input("Reps mínimas", 1, 30, step=1, key=k("rep_min"))
        b.number_input("Reps máximas", 1, 30, step=1, key=k("rep_max"))
        st.caption("Los valores iniciales vienen de Ajustes. Solo se comparan sesiones con el mismo objetivo.")

    target_sets = int(st.session_state[k("target_sets")])

    # Carga sugerida a partir de la última sesión comparable
    last = db.last_session(lift_key, variant, stype)
    if last and last["suggested_load_kg"] is not None:
        default_load = float(last["suggested_load_kg"])
        sty = STATUS_STYLE[last["status"]]
        st.info(f"{sty['emoji']} Última sesión ({fdate(last['session_date'])}): **{sty['label']}** → "
                f"hoy toca **{n(default_load)} kg** {unit_for(lift_key)}.")
    elif last:
        default_load = float(last["current_load_kg"] or 0)
    else:
        default_load = 0.0 if lift.uses_bodyweight else 20.0

    bw_default = float(db.last_bodyweight() or 70.0)

    # --- Paso 1: check-in FUERA del formulario para que el semáforo previo se actualice en vivo
    step(1, "¿Cómo llegas hoy?")
    c1, c2 = st.columns(2)
    energy = c1.select_slider("Energía", options=[1, 2, 3, 4, 5], value=4, key=k("energy"))
    sleep = c2.select_slider("Sueño", options=[1, 2, 3, 4, 5], value=4, key=k("sleep"))
    soreness = st.radio("Molestias", SORENESS_LEVELS, horizontal=True, key=k("soreness"),
                        format_func=str.capitalize)
    bw = st.number_input("Peso corporal (kg)" + ("" if lift.uses_bodyweight else " · opcional"),
                         min_value=0.0, max_value=250.0, value=bw_default, step=0.1, format="%.1f", key=k("bw"))
    rd = readiness(int(energy), int(sleep), soreness, int(db.get_setting("low_wellbeing_threshold", 2)))
    st.markdown(f"""<div class="nx-ready" style="--c:{rd['color']}">
      <div class="nx-why-t">Semáforo previo</div>
      <div class="t">{rd['title']}</div><div class="x">{html.escape(rd['text'])}</div></div>""",
                unsafe_allow_html=True)

    # --- Paso 2: calentamiento sugerido (con discos)
    step(2, "Calentamiento")
    plan = warmup_plan(default_load, float(bw) if bw else None, lift.uses_bodyweight,
                       increment=float(cfg["increment_kg"]))
    rows_html = "".join(
        f"<tr><td>{i}</td><td><b>{html.escape(p['label'])}</b></td><td>× {p['reps']}</td>"
        f"<td class='d'>{discs_text(p['load_kg'], lift.uses_bodyweight)}</td></tr>"
        for i, p in enumerate(plan, start=1))
    work = (f"<tr class='w'><td>▶</td><td><b>Trabajo: {n(default_load)} kg</b></td><td>"
            f"{st.session_state[k('rep_min')]}-{st.session_state[k('rep_max')]}</td>"
            f"<td class='d'>{discs_text(default_load, lift.uses_bodyweight)}</td></tr>")
    head = "<tr class='h'><td></td><td>Serie</td><td>Reps</td><td class='d'>Discos</td></tr>"
    st.markdown(f"<table class='nx-warm'>{head}{rows_html}{work}</table>", unsafe_allow_html=True)
    st.caption("Series de aproximación lejos del fallo, descansando 1-2 min. Discos: "
               + ("total a colgar en el cinturón." if lift.uses_bodyweight else "por lado, con barra de 20 kg."))

    with st.form(f"form_{lift_key}", clear_on_submit=False, border=False):
        step(3, "Tus series")
        st.caption(f"{lift.load_label}: peso total agregado, no por lado. "
                   "Si no completaste una serie, regístrala con 0 reps.")
        entries = []
        for i in range(target_sets):
            a, b, c = st.columns([1.3, 1, 1])
            load = a.number_input(f"S{i + 1} · kg", min_value=0.0, max_value=500.0, value=default_load,
                                  step=1.25, format="%.2f", key=k(f"load{i}"))
            reps = b.number_input("Reps", min_value=0, max_value=50, value=None, step=1, key=k(f"reps{i}"))
            rir = c.number_input("RIR", min_value=0, max_value=5, value=None, step=1, key=k(f"rir{i}"))
            entries.append((load, reps, rir))

        step(4, "Cierre")
        technique = st.radio("Técnica percibida", TECHNIQUE_LEVELS, horizontal=True, key=k("technique"),
                             format_func=lambda t: "Adecuada" if t == "adecuada" else "Necesito revisar")
        sdate = st.date_input("Fecha", value=date.today(), format="DD/MM/YYYY", key=k("date"))
        notes = st.text_area("Notas (opcional)", max_chars=300, key=k("notes"),
                             placeholder="Ej.: buen agarre, última serie lenta…")
        submitted = st.form_submit_button("Analizar y guardar", type="primary")

    if submitted:
        session = SessionInput(
            lift_key=lift_key, variant=variant, session_type=stype, target_sets=target_sets,
            rep_min=int(st.session_state[k("rep_min")]), rep_max=int(st.session_state[k("rep_max")]),
            rir_target=int(st.session_state[k("rir_target")]),
            sets=[SetEntry(float(ld), int(r) if r is not None else None,
                           int(x) if x is not None else None) for ld, r, x in entries],
            checkin=CheckIn(energy=int(energy), sleep=int(sleep), soreness=soreness, technique=technique,
                            bodyweight_kg=float(bw) if bw else None),
            settings=db.settings_for(lift_key))
        prev_pr = db.best_e1rm_added(lift_key)
        result, sid = db.analyze_and_save(session, sdate, notes or "")
        if sid is None:
            st.error("No se guardó la sesión. Revisa:\n\n" + "\n".join(f"- {e}" for e in result.errors))
        else:
            new = db.list_sessions(lift_key)[0] if db.list_sessions(lift_key) else {}
            is_pr = new.get("e1rm_added") is not None and (prev_pr is None or new["e1rm_added"] > prev_pr)
            long_sets = all(st_.reps > 12 for st_ in session.sets if st_.reps)
            cal = db.rir_calibration(lift_key, variant)
            today_pt = next((p for p in cal["points"] if p["session_id"] == sid), None)
            st.session_state["last_result"] = {"lift_key": lift_key, "result": result.to_dict(),
                                               "pr": is_pr and prev_pr is not None,
                                               "e1rm": new.get("e1rm_added"), "cal": cal, "today": today_pt,
                                               "long_sets": long_sets}
            st.toast("Sesión guardada ✅")

    lr = st.session_state.get("last_result")
    if lr and lr["lift_key"] == lift_key:
        r = lr["result"]
        eyebrow("Resultado")
        if lr["pr"]:
            st.success(f"🏆 ¡Nuevo récord estimado! e1RM {n(lr['e1rm'])} kg {unit_for(lift_key)}")
            if submitted:
                st.balloons()
        result_card(r["status"], r["message"], r["reasons"], r["notes"], lift_key, r["suggested_load_kg"])
        if lr.get("long_sets"):
            st.markdown("""<div class="nx-ready" style="--c:#9A9A9A"><div class="nx-why-t">Nota</div>
            <div class="x">Tus series superaron las 12 repeticiones. El semáforo funciona normal, pero el
            <b>e1RM</b> y la <b>calibración del RIR</b> no se calculan con series tan largas, porque las
            estimaciones pierden precisión. Ver <i>Guía → ¿Qué es el e1RM?</i></div></div>""",
                        unsafe_allow_html=True)
        if lr.get("cal"):
            calibration_card(lr["cal"], lr.get("today"))
    disclaimer()


# ---------------------------------------------------------------------------
# HISTORIAL
# ---------------------------------------------------------------------------
def page_history():
    lift_key = choice("Ejercicio", list(LIFTS), key="hist_lift", format_func=lift_label)
    lift = LIFTS[lift_key]
    c1, c2 = st.columns(2)
    variant = c1.selectbox("Variante", ("Todas",) + lift.variants, key=f"hvar_{lift_key}")
    stype = c2.selectbox("Tipo", ("Todos",) + SESSION_TYPES, key=f"htype_{lift_key}")
    rows = db.list_sessions(lift_key, None if variant == "Todas" else variant,
                            None if stype == "Todos" else stype)
    if not rows:
        st.info("No hay sesiones con estos filtros todavía.")
        disclaimer()
        return

    # Calibración del RIR (por variante; si no se elige, se calcula por separado y se combina)
    cal = db.rir_calibration(lift_key, None if variant == "Todas" else variant)
    calibration_card(cal)
    if len(cal["points"]) >= 2:
        gdf = pd.DataFrame([{"Sesión": f"S{i:02d} · {fdate(p['session_date'])[:5]}",
                             "Diferencia RIR (reportado − estimado)": p["gap"]}
                            for i, p in enumerate(cal["points"], start=1)])
        st.bar_chart(gdf.set_index("Sesión"), height=170, color="#BDBDBD")
        st.caption("Barras sobre 0: reportaste más reserva de la estimada. Bajo 0: te quedaban más reps "
                   "de las que creías. La meta es acercarse a 0 (±1).")

    # Gráfico simple: solo sin mezclar variantes ni tipos de sesión
    if variant != "Todas" and stype != "Todos" and len(rows) >= 2:
        df = pd.DataFrame([{"Fecha": r["session_date"], f"Carga ({'lastre' if lift.uses_bodyweight else 'barra'})":
                            r["current_load_kg"], "e1RM estimado": r["e1rm_added"]} for r in reversed(rows)])
        df["Fecha"] = pd.to_datetime(df["Fecha"])
        st.line_chart(df.set_index("Fecha"), height=220)
        st.caption("kg por fecha. El e1RM (Epley) es una estimación de seguimiento.")
    else:
        st.caption("Elige una variante y un tipo de sesión para ver el gráfico (no se mezclan sesiones distintas).")

    for r in rows:
        sty = STATUS_STYLE[r["status"]]
        title = (f":{DOT[r['status']]}[●] {fdate(r['session_date'])} · {r['variant']} · {r['session_type']} · "
                 f"{n(r['current_load_kg'])} kg · {sty['label']}")
        with st.expander(title):
            sets = db.get_sets(r["id"])
            summ = db.session_summary(r, sets)
            a, b, c = st.columns(3)
            kpi(a, f"{summ['compliance']['done']}/{summ['compliance']['target']}", "Cumplimiento")
            kpi(b, n(round(summ["volume"])) if summ["volume"] else "—", "Vol-carga")
            kpi(c, n(summ["e1rm"]["e1rm_added"]) if summ["e1rm"] else "—", "e1RM kg")
            st.dataframe(pd.DataFrame([{"Serie": str(s["set_number"]), "kg": n(s["load_kg"]), "Reps": str(s["reps"]),
                                        "RIR": str(s["rir"]) if s["rir"] is not None else "—"} for s in sets]),
                         hide_index=True)
            st.caption(f"Objetivo {r['target_sets']}x{r['rep_min']}-{r['rep_max']} @ RIR {r['rir_target']} · "
                       f"Energía {r['energy']}/5 · Sueño {r['sleep']}/5 · Molestias {r['soreness']} · "
                       f"Técnica {r['technique']}" + (f" · PC {n(r['bodyweight_kg'])} kg" if r["bodyweight_kg"] else ""))
            if r["notes"]:
                st.caption(f"📝 {r['notes']}")
            result_card(r["status"], r["message"], r["reasons"], r["notes_list"], lift_key, r["suggested_load_kg"])
    disclaimer()


# ---------------------------------------------------------------------------
# GUÍA (preguntas frecuentes + referencias)
# ---------------------------------------------------------------------------
def page_guide():
    st.markdown("""<div class="nx-hero"><div class="nx-eyebrow">Guía NEXO SF</div>
    <div class="nx-h1">Entiende<br><span class="dim">tu semáforo.</span></div></div>""", unsafe_allow_html=True)

    eyebrow("Lo básico")
    with st.expander("¿Cómo se usa NEXO SF?"):
        st.markdown("""
1. **Elige el ejercicio**, la variante y el tipo de sesión en *Registrar*.
2. **Haz el check-in** (energía, sueño, molestias, peso corporal). El *semáforo previo* te dice
   si hoy es un buen día para intentar progresar.
3. **Calienta** con las series de aproximación sugeridas.
4. **Anota tus series**: carga, repeticiones y RIR de cada una.
5. **Analiza y guarda**: el semáforo decide si en la próxima sesión comparable te conviene
   **subir, mantener o bajar** la carga, y te explica por qué.
""")
    with st.expander("¿Qué es el RIR?"):
        st.markdown("""
**RIR** significa *repeticiones en reserva*: cuántas repeticiones más crees que podrías haber hecho
al terminar la serie, con buena técnica. Es una forma práctica de medir qué tan cerca del fallo
entrenas, y se relaciona con la escala de esfuerzo percibido (RPE) adaptada al entrenamiento de
fuerza (Zourdos et al., 2016; Helms et al., 2016).

| RIR | Qué significa | RPE equivalente |
|---|---|---|
| 0 | No podía hacer ni una más | 10 |
| 1 | Me quedaba 1 | 9 |
| 2 | Me quedaban 2 | 8 |
| 3 | Me quedaban 3 | 7 |
| 4–5 | Esfuerzo moderado | 5–6 |

Es una **percepción**, no una medición exacta. Por eso NEXO SF incluye la *calibración del RIR*.
""")
    with st.expander("¿Qué significa cada color?"):
        st.markdown("""
- 🟢 **SUBIR**: todas las series llegaron al tope del rango con el RIR objetivo, sin señales de alerta.
  Se sugiere el incremento mínimo que configuraste, si no supera tu límite porcentual.
- 🟡 **MANTENER**: estás dentro del rango pero falta consolidar, tuviste un fallo puntual, o el
  bienestar del día no acompaña. Repite la carga y busca mejorar repeticiones o RIR.
- 🔴 **BAJAR**: no alcanzaste el mínimo de repeticiones en **dos sesiones comparables seguidas**.
  Se sugiere bajar ≈5 % de la carga del sistema, redondeado a tus discos.
- 🟣 **ALERTA**: molestia importante o técnica a revisar. No se recomienda carga.
- ⚪ **LÍNEA BASE**: primera sesión comparable; se guarda como punto de partida.

Una sesión es **comparable** solo si coincide en ejercicio, variante, tipo de sesión y objetivo
(series, rango de reps y RIR). Así nunca se compara una dominada prona con una supina.
""")

    eyebrow("Street Lifting")
    with st.expander("¿Por qué se suma mi peso corporal?"):
        st.markdown("""
En dominada, fondos y muscle-up mueves **tu cuerpo + el lastre**. A eso le llamamos
**carga del sistema**. Todos los porcentajes (límite de subida, bajada, e1RM) se calculan sobre ella.

*Ejemplo:* pesas 75 kg y usas 20 kg de lastre → mueves 95 kg. Subir 2,5 kg es **+2,6 %**,
no +12,5 % como parecería si solo miráramos el lastre. En sentadilla, la carga es solo la barra.
""")
    with st.expander("¿Qué es la doble progresión?"):
        st.markdown("""
Primero progresas en **repeticiones** dentro de un rango (p. ej. de 5 a 8). Cuando completas el tope
del rango en todas las series con el RIR objetivo, progresas en **carga** y vuelves a la parte baja del
rango. Sin lastre, NEXO SF te sugiere empezar con el lastre mínimo disponible. Es una aplicación del
principio de sobrecarga progresiva (ACSM, 2009).
""")
    with st.expander("¿Qué es el e1RM y qué tan exacto es?"):
        st.markdown("""
El **e1RM** es una estimación de tu máximo a una repetición calculada con la fórmula de **Epley**:
`e1RM = carga × (1 + reps / 30)`. En dominada, fondos y muscle-up se calcula sobre la carga del sistema
y luego se resta el peso corporal para mostrar tu **lastre máximo estimado**.

Las ecuaciones de predicción se relacionan fuertemente con el 1RM real, pero su exactitud cambia según
el ejercicio (LeSuer et al., 1997). Por eso NEXO SF solo usa series de 1 a 12 repeticiones y lo
muestra como **estimación de seguimiento**, no como marca oficial.
""")

    eyebrow("Funciones inteligentes")
    with st.expander("¿Qué es el semáforo previo?"):
        st.markdown("""
Antes de entrenar, con tu check-in, NEXO SF anticipa qué puede pasar: si duermes o te sientes mal,
te avisa que hoy es un **día para consolidar** y que el semáforo no recomendará subir aunque cumplas
todo. Ajustar el entrenamiento según el estado del día es la idea central de la **autorregulación**
(Greig et al., 2020).
""")
    with st.expander("¿Qué es la calibración del RIR?"):
        st.markdown("""
Las personas no son perfectas estimando cuántas repeticiones les quedan: en promedio tienden a
**subestimarlas en cerca de una repetición**, y la estimación mejora cerca del fallo y con cargas más
altas (Halperin et al., 2022).

NEXO SF toma tu **mejor e1RM reciente** y calcula cuántas repeticiones deberías haber podido hacer con la
carga de tu **primera serie** (la menos afectada por la fatiga). Luego lo compara con el RIR que anotaste:

- **Bien calibrado** (diferencia de ±1): el semáforo puede confiar en tus datos.
- **Sobreestimas tu reserva**: terminas más cerca del fallo de lo que crees.
- **Subestimas tu reserva**: te quedan más reps de las que crees.

Necesita al menos 3 sesiones comparables. Es una estimación educativa, no un test de laboratorio.
""")
    with st.expander("¿Cómo se calcula el calentamiento?"):
        st.markdown("""
- **Con lastre**: partes con peso corporal × 5 y luego agregas ≈25 %, 60 % y 85 % de tu lastre de trabajo
  (× 3, × 2, × 1), redondeado a tus discos.
- **Sentadilla**: barra vacía × 8 y luego ≈40 %, 60 %, 75 % y 90 % de la carga de trabajo.

Son series de aproximación **lejos del fallo**: preparan el gesto técnico sin generar fatiga. Las
revisiones sobre calentamiento lo asocian, en general, con un mejor rendimiento (Fradkin et al., 2010).
Los porcentajes son una decisión de diseño del prototipo.
""")
    with st.expander("¿Por qué no me deja subir si dormí mal?"):
        st.markdown("""
Porque un buen rendimiento con poco descanso puede ser una excepción y no una adaptación estable.
NEXO SF prefiere **confirmar** el progreso en una sesión con buen bienestar. El umbral (energía o sueño
≤ 2 de 5) es una **decisión de diseño** del prototipo y se puede cambiar en *Ajustes*.
""")

    eyebrow("Límites")
    with st.expander("¿Qué NO hace NEXO SF?"):
        st.markdown("""
- No diagnostica lesiones ni reemplaza a un entrenador o profesional de la salud.
- No mide el esfuerzo de forma objetiva: RIR, molestias y bienestar son **autorreportados**.
- No crea rutinas ni planifica temporadas: orienta la carga de **un ejercicio** sesión a sesión.
- Los umbrales numéricos son **decisiones de diseño** configurables, no puntos de corte clínicos.
""")

    eyebrow("Referencias")
    st.markdown("""<div style="font-size:.82rem; color:#BDBDBD; line-height:1.5">

American College of Sports Medicine. (2009). Progression models in resistance training for healthy adults.
<i>Medicine &amp; Science in Sports &amp; Exercise, 41</i>(3), 687–708. https://doi.org/10.1249/MSS.0b013e3181915670<br><br>
Fradkin, A. J., Zazryn, T. R., &amp; Smoliga, J. M. (2010). Effects of warming-up on physical performance: A systematic
review with meta-analysis. <i>Journal of Strength and Conditioning Research, 24</i>(1), 140–148.
https://doi.org/10.1519/JSC.0b013e3181c643a0<br><br>
Greig, L., Stephens Hemingway, B. H., Aspe, R. R., Cooper, K., Comfort, P., &amp; Swinton, P. A. (2020). Autoregulation
in resistance training: Addressing the inconsistencies. <i>Sports Medicine, 50</i>(11), 1873–1887.
https://doi.org/10.1007/s40279-020-01330-8<br><br>
Halperin, I., Malleron, T., Har-Nir, I., Androulakis-Korakakis, P., Wolf, M., Fisher, J., &amp; Steele, J. (2022).
Accuracy in predicting repetitions to task failure in resistance exercise: A scoping review and exploratory
meta-analysis. <i>Sports Medicine, 52</i>(2), 377–390. https://doi.org/10.1007/s40279-021-01559-x<br><br>
Helms, E. R., Cronin, J., Storey, A., &amp; Zourdos, M. C. (2016). Application of the repetitions in reserve-based
rating of perceived exertion scale for resistance training. <i>Strength and Conditioning Journal, 38</i>(4), 42–49.<br><br>
LeSuer, D. A., McCormick, J. H., Mayhew, J. L., Wasserstein, R. L., &amp; Arnold, M. D. (1997). The accuracy of
prediction equations for estimating 1-RM performance in the bench press, squat, and deadlift.
<i>Journal of Strength and Conditioning Research, 11</i>(4), 211–213.<br><br>
Zourdos, M. C., Klemp, A., Dolan, C., Quiles, J. M., Schau, K. A., Jo, E., Helms, E., Esgro, B., Duncan, S.,
Garcia Merino, S., &amp; Blanco, R. (2016). Novel resistance training–specific rating of perceived exertion scale
measuring repetitions in reserve. <i>Journal of Strength and Conditioning Research, 30</i>(1), 267–275.
https://doi.org/10.1519/JSC.0000000000001049
</div>""", unsafe_allow_html=True)
    disclaimer()


# ---------------------------------------------------------------------------
# AJUSTES
# ---------------------------------------------------------------------------
PUBLIC_URL = "https://nexo-sf.streamlit.app"


def share_block():
    """Código QR con el link público (para la presentación). Usa segno si está instalado."""
    eyebrow("Compartir")
    try:
        import segno
        svg = segno.make(PUBLIC_URL, error="m").svg_inline(scale=7, dark="#0A0A0A", light="#F5F5F5", border=3)
        st.markdown(f"""<div style="display:flex; flex-direction:column; align-items:center; gap:.6rem;
            background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:1.2rem;">
            <div style="border-radius:6px; overflow:hidden; line-height:0">{svg}</div>
            <div class="nx-load" style="margin:0">Escanea y prueba NEXO SF</div>
            <div style="color:var(--muted); font-size:.9rem">{PUBLIC_URL.replace("https://", "")}</div></div>""",
                    unsafe_allow_html=True)
    except Exception:  # segno no instalado (o versión distinta): mostrar solo el link
        st.info(f"Link público: {PUBLIC_URL}  \n(Instala `segno` para ver el código QR aquí.)")


def page_settings():
    share_block()
    eyebrow("Objetivos por ejercicio")
    lift_key = choice("Ejercicio", list(LIFTS), key="cfg_lift", format_func=lift_label)
    cfg = db.get_lift_config(lift_key)
    with st.form(f"cfg_{lift_key}", border=False):
        a, b = st.columns(2)
        ts = a.number_input("Series", 1, 10, int(cfg["target_sets"]))
        rir = b.number_input("RIR objetivo", 0, 5, int(cfg["rir_target"]))
        rmin = a.number_input("Reps mínimas", 1, 30, int(cfg["rep_min"]))
        rmax = b.number_input("Reps máximas", 1, 30, int(cfg["rep_max"]))
        inc = a.number_input("Incremento disponible (kg)", 0.25, 20.0, float(cfg["increment_kg"]), step=0.25,
                             help="Menor salto total que puedes montar (no por lado).")
        mx = b.number_input("Límite de subida (%)", 1.0, 20.0, float(cfg["max_increase_pct"]), step=0.5)
        dec = a.number_input("Bajada sugerida (%)", 1.0, 20.0, float(cfg["decrease_pct"]), step=0.5)
        if st.form_submit_button("Guardar objetivos"):
            if rmax < rmin:
                st.error("Las reps máximas deben ser mayores o iguales a las mínimas.")
            else:
                db.save_lift_config(lift_key, dict(target_sets=int(ts), rep_min=int(rmin), rep_max=int(rmax),
                                                   rir_target=int(rir), increment_kg=float(inc),
                                                   max_increase_pct=float(mx), decrease_pct=float(dec)))
                for name in ("target_sets", "rep_min", "rep_max", "rir_target"):
                    st.session_state.pop(f"{name}_{lift_key}", None)
                st.success("Objetivos guardados.")

    eyebrow("Bienestar")
    thr = int(db.get_setting("low_wellbeing_threshold", 2))
    new_thr = st.select_slider("Energía o sueño iguales o menores a este valor bloquean la subida",
                               options=[1, 2, 3], value=thr)
    if new_thr != thr:
        db.set_setting("low_wellbeing_threshold", new_thr)
        st.toast("Umbral actualizado")

    eyebrow("Datos")
    st.download_button("Exportar CSV", data=db.export_csv().encode("utf-8-sig"),
                       file_name=f"nexosf_{date.today().isoformat()}.csv", mime="text/csv")
    if st.button("Cargar datos de demostración"):
        db.seed_demo()
        st.session_state.pop("last_result", None)
        st.success("Demo cargada: ~6 semanas de ejemplo en los 4 ejercicios.")
    confirm = st.checkbox("Confirmo que quiero borrar todas las sesiones")
    if st.button("Borrar todo", disabled=not confirm):
        db.reset_all()
        st.session_state.pop("last_result", None)
        st.success("Historial borrado.")

    eyebrow("Limitaciones")
    st.markdown("""
- El **RIR** es una percepción del deportista, no una medición objetiva.
- El **e1RM** (Epley, 1–12 reps) es una estimación de seguimiento, no una prueba máxima.
- Las recomendaciones **no reemplazan** al entrenador ni al criterio del deportista.
- Molestias y bienestar son **autorreportados**; NEXO SF no diagnostica.
- Los umbrales son **decisiones de diseño** del prototipo, no puntos de corte clínicos.
""")
    disclaimer()


{PAGES[0]: page_home, PAGES[1]: page_register, PAGES[2]: page_history, PAGES[3]: page_guide,
 PAGES[4]: page_settings}[page]()
