# LOG4SEC — Zoho Auto-Enricher
## Guía de instalación paso a paso

---

## ¿Qué hace este script?

Cada 10 minutos mira tu Zoho CRM. Si encuentra empresas sin Website,
las investiga automáticamente en internet y rellena:
- ✅ Website / URL oficial
- ✅ Descripción (orientada a ciberseguridad)
- ✅ Número de empleados
- ✅ Ciudad y País

---

## PASO 1 — Instalar dependencias

```bash
pip install anthropic requests python-dotenv
```

---

## PASO 2 — Credenciales de Zoho

1. Ve a https://api-console.zoho.eu
2. Crea una nueva aplicación tipo "Server-based Application"
3. En Redirect URI pon: https://www.zoho.eu/crm (no importa, es solo para el setup)
4. Copia el **Client ID** y **Client Secret**
5. Genera el Refresh Token:
   - Ve a esta URL (cambia YOUR_CLIENT_ID):
     ```
     https://accounts.zoho.eu/oauth/v2/auth?scope=ZohoCRM.modules.accounts.ALL&client_id=YOUR_CLIENT_ID&response_type=code&redirect_uri=https://www.zoho.eu/crm&access_type=offline
     ```
   - Autoriza la app
   - Copia el `code` de la URL de redirección
   - Haz esta llamada para obtener el refresh token:
     ```bash
     curl -X POST "https://accounts.zoho.eu/oauth/v2/token" \
       -d "code=TU_CODE&client_id=TU_CLIENT_ID&client_secret=TU_CLIENT_SECRET&redirect_uri=https://www.zoho.eu/crm&grant_type=authorization_code"
     ```
   - Guarda el `refresh_token` del JSON de respuesta

---

## PASO 3 — Credenciales de Anthropic

1. Ve a https://console.anthropic.com
2. API Keys → Create Key
3. Copia la clave (empieza por sk-ant-...)

---

## PASO 4 — Configurar el archivo .env

```bash
cp .env.example .env
```

Edita `.env` con tus datos reales.

---

## PASO 5 — Ejecutar

```bash
# Cargar variables de entorno y ejecutar
export $(cat .env | xargs) && python enrich.py
```

O en Windows:
```cmd
set ZOHO_CLIENT_ID=tu_valor
set ZOHO_CLIENT_SECRET=tu_valor
set ZOHO_REFRESH_TOKEN=tu_valor
set ANTHROPIC_API_KEY=tu_valor
python enrich.py
```

---

## PASO 6 — Ejecutar en background (para que corra solo)

**En Mac/Linux:**
```bash
nohup sh -c 'export $(cat .env | xargs) && python enrich.py' > log4sec_enricher.log 2>&1 &
```

**Con Claude Code** (recomendado):
Dile a Claude Code: *"Ejecuta el script enrich.py en background con las variables del .env"*

---

## Personalización

En el archivo `enrich.py` puedes cambiar:
- `CHECK_INTERVAL_MIN = 10` → cada cuántos minutos comprueba Zoho
- `ZOHO_API_BASE` → si tu cuenta Zoho es .com en lugar de .eu

---

## ¿Tu cuenta Zoho es EU o COM?

- Si accedes a Zoho desde zoho.eu → usa `https://www.zohoapis.eu/crm/v2`
- Si accedes desde zoho.com → cambia a `https://www.zohoapis.com/crm/v2`
  Y el token endpoint: `https://accounts.zoho.com/oauth/v2/token`
