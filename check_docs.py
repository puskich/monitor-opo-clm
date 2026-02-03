import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

URL = "https://empleopublico.castillalamancha.es/procesos-selectivos/abiertos/promocion-interna/2023-2024-cuerpo-tecnico-escala-tecnica-de-sistemas"

STATE_FILE = Path("state.json")

def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def fetch_html(url: str) -> str:
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text

def extract_documentation_entries(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # Estrategia: localizar un encabezado que sea exactamente "Documentación"
    # y extraer enlaces cercanos.
    header = None
    for tag in soup.find_all(["h2", "h3", "h4"]):
        if normalize_space(tag.get_text()).lower() == "documentación":
            header = tag
            break

    if not header:
        # Si el sitio cambia la estructura, fallamos “de forma visible”
        raise RuntimeError('No se encontró el encabezado "Documentación" en la página.')

    # Tomamos el bloque contenedor más razonable: el siguiente elemento “grande”
    # o el padre cercano; y extraemos todos los links que parezcan documentos.
    container = header.find_parent()  # suele ser suficiente
    links = container.find_all("a", href=True)

    entries = []
    seen = set()
    for a in links:
        text = normalize_space(a.get_text())
        href = a["href"].strip()
        full = urljoin(URL, href)

        # Filtrado suave: solo enlaces con texto y que no sean anchors internos vacíos
        if not text:
            continue
        key = (text, full)
        if key in seen:
            continue
        seen.add(key)
        entries.append({"title": text, "url": full})

    # Orden estable
    entries.sort(key=lambda x: (x["title"].lower(), x["url"]))
    return entries

def load_state():
    if not STATE_FILE.exists():
        return {"entries": []}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))

def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    html = fetch_html(URL)
    current = extract_documentation_entries(html)

    state = load_state()
    previous = state.get("entries", [])

    prev_set = {(e["title"], e["url"]) for e in previous}
    curr_set = {(e["title"], e["url"]) for e in current}

    added = sorted(list(curr_set - prev_set))
    removed = sorted(list(prev_set - curr_set))

    if not STATE_FILE.exists():
        # Primera ejecución: solo guardamos estado, sin “alerta”
        save_state({"entries": current})
        print("Estado inicial guardado (sin notificación).")
        return

    if not added and not removed:
        print("Sin cambios en Documentación.")
        return

    # Guardar nuevo estado para que el workflow lo commitee
    save_state({"entries": current})

    print("Cambios detectados en Documentación.")
    if added:
        print("Nuevos:")
        for title, url in added:
            print(f"- {title} -> {url}")
    if removed:
        print("Eliminados:")
        for title, url in removed:
            print(f"- {title} -> {url}")

if __name__ == "__main__":
    main()
