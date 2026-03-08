#!/usr/bin/env python3
"""
Log4sec — Zoho CRM Auto-Enricher
Vigila Zoho cada X minutos, detecta empresas nuevas sin rellenar,
las investiga con Claude + web search y actualiza los campos automáticamente.
"""

import os
import json
import time
import requests
import anthropic
from datetime import datetime, timezone

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
ZOHO_CLIENT_ID     = os.environ["ZOHO_CLIENT_ID"]
ZOHO_CLIENT_SECRET = os.environ["ZOHO_CLIENT_SECRET"]
ZOHO_REFRESH_TOKEN = os.environ["ZOHO_REFRESH_TOKEN"]
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
ZOHO_API_BASE      = "https://www.zohoapis.eu/crm/v2"   # Cambia a .com si tu cuenta no es EU
CHECK_INTERVAL_MIN = 10                                  # Cada cuántos minutos vigila Zoho

# ─── ZOHO AUTH ────────────────────────────────────────────────────────────────
def get_access_token() -> str:
    """Obtiene access token usando refresh token."""
    r = requests.post("https://accounts.zoho.eu/oauth/v2/token", params={
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "client_id":     ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "grant_type":    "refresh_token",
    })
    r.raise_for_status()
    return r.json()["access_token"]


def zoho_get(endpoint: str, token: str, params: dict = None) -> dict:
    headers = {"Authorization": f"Zoho-oauthtoken {token}"}
    r = requests.get(f"{ZOHO_API_BASE}/{endpoint}", headers=headers, params=params)
    r.raise_for_status()
    return r.json()


def zoho_update(account_id: str, data: dict, token: str) -> bool:
    """Actualiza campos de una empresa en Zoho."""
    headers = {
        "Authorization": f"Zoho-oauthtoken {token}",
        "Content-Type":  "application/json",
    }
    payload = {"data": [{"id": account_id, **data}]}
    r = requests.put(f"{ZOHO_API_BASE}/Accounts/{account_id}", headers=headers, json=payload)
    return r.status_code in (200, 201)


# ─── DETECCIÓN DE EMPRESAS SIN ENRIQUECER ─────────────────────────────────────
def get_unenriched_accounts(token: str) -> list:
    """
    Devuelve cuentas creadas en las últimas 24h que no tienen Website ni Descripción.
    Criterio: Website vacío = pendiente de enriquecer.
    """
    try:
        data = zoho_get("Accounts", token, params={
            "fields":   "id,Account_Name,Website,Description,Employees,City,Country",
            "sort_by":  "Created_Time",
            "sort_order": "desc",
            "per_page": 50,
        })
        accounts = data.get("data", [])
        # Filtra: sin website (campo vacío o None)
        pending = [a for a in accounts if not a.get("Website")]
        return pending
    except Exception as e:
        print(f"[ERROR] Al obtener cuentas de Zoho: {e}")
        return []


# ─── INVESTIGACIÓN CON CLAUDE ─────────────────────────────────────────────────
def research_company(company_name: str) -> dict:
    """
    Usa Claude con web search para investigar la empresa
    y devuelve los campos listos para Zoho.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""Investiga la empresa llamada "{company_name}" usando búsqueda web.

Necesito exactamente estos datos en formato JSON (sin markdown, solo el JSON):
{{
  "website": "URL oficial completa con https://",
  "description": "Descripción de 3-4 frases en español. Enfocada en: qué hace la empresa, sector, tamaño aproximado, y datos relevantes para una empresa de ciberseguridad que quiere venderles (sistemas críticos, datos sensibles, infraestructura digital). Tono profesional y directo.",
  "employees": número entero aproximado de empleados (solo el número, sin texto),
  "city": "Ciudad principal de la empresa",
  "country": "País"
}}

Si no encuentras algún dato, pon null para ese campo.
Responde SOLO con el JSON, sin explicaciones adicionales."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )

    # Extraer texto de la respuesta
    result_text = ""
    for block in response.content:
        if block.type == "text":
            result_text += block.text

    # Parsear JSON
    result_text = result_text.strip()
    if result_text.startswith("```"):
        result_text = result_text.split("```")[1]
        if result_text.startswith("json"):
            result_text = result_text[4:]

    data = json.loads(result_text)
    return data


# ─── ENRIQUECER UNA EMPRESA ───────────────────────────────────────────────────
def enrich_account(account: dict, token: str):
    account_id   = account["id"]
    account_name = account.get("Account_Name", "Desconocido")

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Investigando: {account_name}")

    try:
        info = research_company(account_name)
        print(f"  → Web: {info.get('website')}")
        print(f"  → Empleados: {info.get('employees')}")
        print(f"  → Ciudad: {info.get('city')}, {info.get('country')}")

        # Construir payload para Zoho (solo campos con datos)
        update_data = {}
        if info.get("website"):
            update_data["Website"] = info["website"]
        if info.get("description"):
            update_data["Description"] = info["description"]
        if info.get("employees") and isinstance(info["employees"], (int, float)):
            update_data["Employees"] = int(info["employees"])
        if info.get("city"):
            update_data["City"] = info["city"]
            update_data["Billing_City"] = info["city"]
        if info.get("country"):
            update_data["Country"] = info["country"]
            update_data["Billing_Country"] = info["country"]

        if update_data:
            success = zoho_update(account_id, update_data, token)
            if success:
                print(f"  ✅ Zoho actualizado correctamente")
            else:
                print(f"  ❌ Error al actualizar Zoho")
        else:
            print(f"  ⚠️  No se encontraron datos suficientes")

    except json.JSONDecodeError as e:
        print(f"  ❌ Error parseando respuesta de Claude: {e}")
    except Exception as e:
        print(f"  ❌ Error inesperado: {e}")


# ─── BUCLE PRINCIPAL ──────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  LOG4SEC — Zoho CRM Auto-Enricher")
    print(f"  Intervalo: cada {CHECK_INTERVAL_MIN} minutos")
    print(f"  Zoho API: {ZOHO_API_BASE}")
    print("=" * 55)

    while True:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Comprobando empresas nuevas en Zoho...")

        try:
            token    = get_access_token()
            accounts = get_unenriched_accounts(token)

            if not accounts:
                print("  → No hay empresas pendientes de enriquecer.")
            else:
                print(f"  → {len(accounts)} empresa(s) pendientes.")
                for account in accounts:
                    enrich_account(account, token)
                    time.sleep(3)  # Pausa entre llamadas para no saturar APIs

        except Exception as e:
            print(f"[ERROR] {e}")

        print(f"\n  Próxima comprobación en {CHECK_INTERVAL_MIN} minutos...")
        time.sleep(CHECK_INTERVAL_MIN * 60)


if __name__ == "__main__":
    main()
