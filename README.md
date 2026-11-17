# NEXO SF — Street Lifting

Aplicación para registrar sesiones de **Dominada, Fondos, Sentadilla y Muscle-up** (con o sin lastre) y recibir una recomendación de carga tipo **semáforo**:

| | Estado | Significado |
|---|---|---|
| 🟢 | SUBIR | Todas las series en el tope del rango con el RIR objetivo |
| 🟡 | MANTENER | En rango pero sin cumplir todo, fallo puntual, bienestar bajo o salto muy grande |
| 🔴 | BAJAR | Bajo el mínimo de repeticiones en 2 sesiones comparables seguidas |
| 🟣 | ALERTA | Molestia importante o técnica a revisar |
| ⚪ | LÍNEA BASE | Primera sesión comparable |

## Estado del proyecto
- [x] Motor del semáforo (`smartload.py`) y cálculos (`calculations.py`)
- [x] Tests automáticos (41 casos)
- [x] Semáforo previo (readiness), calentamiento automático y calibración del RIR (`insights.py`)
- [x] Pestaña Guía: preguntas frecuentes y referencias
- [x] Interfaz Streamlit para celular: Inicio, Registrar, Historial, Ajustes
- [x] Base de datos SQLite, historial, datos demo, exportar CSV
- [ ] Gráficos avanzados (Plotly), importar CSV, publicación con link público

## Cómo abrir la app
```bash
conda activate nexosf
cd ~/Documents/NEXOSFSTREET
streamlit run app.py
```
Se abre en el navegador. Para verla en el celular (misma red WiFi), abre la **Network URL** que muestra la Terminal.

## Estructura
```
app.py            Interfaz (Streamlit)
database.py       SQLite: guardar sesiones, historial, demo, CSV
insights.py       Semáforo previo, calentamiento, calibración del RIR
lifts.py          Catálogo de ejercicios, variantes y valores iniciales
calculations.py   Carga del sistema, volumen, cumplimiento, e1RM, fuerza relativa, discos
smartload.py      Motor del semáforo (reglas deterministas, sin interfaz)
demo_semaforo.py  Demostración en consola (F5 en Spyder)
tests/            Casos de aceptación (pytest)
.streamlit/       Tema visual (oscuro + verde lima)
```

## Cómo probar
```bash
python demo_semaforo.py
python -m pytest -v
```

## Limitaciones (se muestran también en la app)
- El RIR es una percepción del deportista, no una medición objetiva.
- El e1RM (Epley, 1–12 reps) es una estimación de seguimiento, no una prueba máxima.
- Los umbrales (energía/sueño ≤ 2, límite 5 %, bajada 5 %) son decisiones de diseño del prototipo, configurables.
- NEXO SF no diagnostica lesiones ni reemplaza al entrenador.
