"""
demo_semaforo.py — Prueba rápida del motor NEXO SF desde Spyder.

Abre este archivo en Spyder y presiona F5 (Run). Verás en la consola
cómo cambia el semáforo según los datos de la sesión.
"""
from smartload import CheckIn, PreviousSession, SessionInput, SetEntry, evaluate

BW = 75.0


def mostrar(titulo, sesion, historial):
    r = evaluate(sesion, historial)
    print("=" * 70)
    print(titulo)
    print(f"{r.style['emoji']}  {r.style['label']}")
    print("Qué hacer:", r.message)
    print("Por qué:")
    for razon in r.reasons:
        print("  -", razon)
    for nota in r.notes:
        print("  (nota)", nota)
    for err in r.errors:
        print("  (error)", err)


def dominada(reps, rirs, lastre=20, **checkin):
    ci = dict(energy=4, sleep=4, soreness="ninguna", technique="adecuada", bodyweight_kg=BW)
    ci.update(checkin)
    return SessionInput("dominada", "Prono", "Intensidad", 3, 3, 5, 2,
                        [SetEntry(lastre, r, i) for r, i in zip(reps, rirs)], CheckIn(**ci))


def anterior(below_min=False):
    return [PreviousSession(1, "dominada", "Prono", "Intensidad", 3, 3, 5, 2, below_min)]


if __name__ == "__main__":
    mostrar("1. Primera sesión de dominada con 20 kg", dominada([5, 5, 5], [2, 2, 2]), [])
    mostrar("2. Misma sesión, ya hay una anterior comparable", dominada([5, 5, 5], [3, 2, 2]), anterior())
    mostrar("3. Una serie no llegó al tope", dominada([5, 4, 5], [2, 2, 2]), anterior())
    mostrar("4. Rendimiento perfecto pero dormiste mal", dominada([5, 5, 5], [3, 3, 3], sleep=2), anterior())
    mostrar("5. Molestia importante", dominada([5, 5, 5], [3, 3, 3], soreness="importantes"), anterior())
    mostrar("6. Bajo el mínimo dos sesiones seguidas", dominada([3, 2, 2], [0, 0, 0]), anterior(below_min=True))
