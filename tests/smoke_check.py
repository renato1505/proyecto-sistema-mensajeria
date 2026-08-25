import re
import sys
import os
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
os.environ["LOGIN_REQUIRED"] = "0"

from main import app


def extraer_csrf(html):
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if not match:
        raise RuntimeError("No se encontro csrf_token")
    return match.group(1)


def main():
    client = app.test_client()

    for ruta in [
        "/crear_envio",
        "/nuevo_envio",
        "/carga_masiva",
        "/catalogos",
        "/catalogos?tab=destinatarios",
        "/envios",
        "/en_proceso",
        "/historico",
        "/of_correo",
        "/configuracion",
        "/operacion",
    ]:
        response = client.get(ruta)
        print(f"{ruta}: {response.status_code}")
        if response.status_code != 200:
            raise SystemExit(1)

    inicio = client.get("/", follow_redirects=False)
    reportes_retirado = client.get("/reportes")
    admin_retirado = client.get("/admin")
    print(f"/: {inicio.status_code}")
    print(f"/reportes retirado: {reportes_retirado.status_code}")
    print(f"/admin retirado: {admin_retirado.status_code}")
    if inicio.status_code != 200:
        raise SystemExit(1)
    if reportes_retirado.status_code != 404:
        raise SystemExit(1)
    if admin_retirado.status_code != 404:
        raise SystemExit(1)

    sin_token = client.post("/descargar_historico_seleccionados")

    historico_html = client.get("/historico").data.decode("utf-8", errors="ignore")
    token = extraer_csrf(historico_html)
    con_token = client.post(
        "/descargar_historico_seleccionados",
        data={"csrf_token": token},
        follow_redirects=False,
    )

    print(f"POST sin CSRF: {sin_token.status_code}")
    print(f"POST con CSRF: {con_token.status_code} -> {con_token.headers.get('Location')}")

    if sin_token.status_code != 400:
        raise SystemExit(1)

    if con_token.status_code != 302:
        raise SystemExit(1)

    for ruta in [
        "/buscar_comunas?q=Santiago",
        "/buscar_remitentes?q=a",
        "/buscar_destinatarios?q=a",
    ]:
        response = client.get(ruta)
        print(f"{ruta}: {response.status_code}")
        if response.status_code != 200:
            raise SystemExit(1)

    nuevo_envio_html = client.get("/nuevo_envio").data.decode("utf-8", errors="ignore")
    token_catalogo = extraer_csrf(nuevo_envio_html)

    ajax_sin_token = client.post("/guardar_remitente")
    ajax_invalido = client.post(
        "/guardar_destinatario",
        data={"csrf_token": token_catalogo, "rut_destinatario": "0"},
    )
    catalogos_html = client.get("/catalogos").data.decode("utf-8", errors="ignore")
    token_catalogos = extraer_csrf(catalogos_html)
    remitente_invalido = client.post(
        "/catalogos/remitentes/guardar",
        data={
            "csrf_token": token_catalogos,
            "remitente": "Juan 123",
            "correo_remitente": "correo_malo",
            "division": "DL",
            "centro_costo": "ABC",
        },
        follow_redirects=False,
    )

    print(f"AJAX sin CSRF: {ajax_sin_token.status_code}")
    print(f"Destinatario invalido: {ajax_invalido.status_code}")
    print(f"Remitente catalogo invalido: {remitente_invalido.status_code}")

    if ajax_sin_token.status_code != 400:
        raise SystemExit(1)

    if ajax_invalido.status_code != 400:
        raise SystemExit(1)

    if remitente_invalido.status_code != 302:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
