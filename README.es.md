# Festival Setlist Creator

Crea una playlist de Spotify con los setlists mas recientes de tus artistas favoritos de festival.

## Como funciona

1. Busca artistas — la app consulta la base de datos de setlist.fm con autocompletado.
2. Agrega hasta 20 artistas a tu Festival Lineup. Arrastra y suelta (o usa el boton de intercambio en movil) para reordenarlos.
3. Configura las opciones de la playlist:
   - **Preferir grabacion original** — cuando un artista toca un cover, intenta encontrar primero la version del artista original en Spotify.
   - **Incluir tracks de fondo/grabados** — incluye canciones reproducidas desde grabaciones en lugar de tocadas en vivo.
   - **Nombre personalizado** — por defecto es `Festival Setlist – DD/MM/YYYY`.
4. Haz clic en **Create Festival Setlist** — la app descarga el setlist mas reciente de cada artista desde setlist.fm, resuelve cada cancion a un track de Spotify y crea una playlist privada en tu cuenta.
5. Aparece una tarjeta de resultado con un resumen por artista, advertencias de canciones faltantes y un reproductor de Spotify embebido.

**Manejo de medleys:** las canciones listadas como `Cancion A / Cancion B` se dividen y buscan individualmente de forma automatica.

---

## Variables de entorno

| Variable | Requerida | Descripcion |
| --- | --- | --- |
| `SPOTIPY_CLIENT_ID` | Si | Client ID de tu app de Spotify |
| `SPOTIPY_CLIENT_SECRET` | Si | Client Secret de tu app de Spotify |
| `SPOTIPY_REFRESH_TOKEN` | Si | Refresh token de larga duracion de Spotify (ver abajo) |
| `SETLISTFM_API_KEY` | Si | API key de setlist.fm |
| `PORT` | No | Puerto del servidor (por defecto: `3000`) |

---

## Instalacion local

```bash
# 1. Entrar al proyecto
cd festival-setlistfm

# 2. Crear y activar un entorno virtual
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Crear un archivo .env con tus claves
# SPOTIPY_CLIENT_ID=...
# SPOTIPY_CLIENT_SECRET=...
# SPOTIPY_REFRESH_TOKEN=...
# SETLISTFM_API_KEY=...

# 5. Ejecutar la app
python app.py
# Abrir http://localhost:3000
```

---

## Deploy en Railway

1. Sube este repositorio a GitHub.
2. Ve a [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
3. Selecciona el repositorio.
4. En **Variables**, agrega las cuatro variables de entorno requeridas de la tabla de arriba.
5. Railway detecta automaticamente el `Procfile` y hace el deploy (gunicorn, 2 workers, 4 threads).

---

## Referencia de la API

### `GET /api/search-artist?q=<nombre>`

Devuelve artistas que coincidan con la busqueda desde setlist.fm.

**Limite de velocidad:** 60 requests/minuto.

**Respuesta:**

```json
{
  "artists": [
    {
      "id": "mbid-o-nombre",
      "mbid": "musicbrainz-id",
      "name": "Nombre del artista",
      "sortName": "Artista, Nombre",
      "disambiguation": "era o tipo de banda",
      "url": "https://www.setlist.fm/..."
    }
  ]
}
```

### `POST /api/create-playlist`

Descarga setlists, resuelve tracks y crea una playlist de Spotify.

**Limite de velocidad:** 5 requests/minuto.

**Cuerpo de la solicitud:**

```json
{
  "artists": [{ "id": "...", "mbid": "...", "name": "..." }],
  "prefer_original": true,
  "include_taped": false,
  "playlist_name": "Mi Festival"
}
```

**Respuesta:**

```json
{
  "playlist_url": "https://open.spotify.com/playlist/...",
  "playlist_id": "...",
  "total_tracks": 150,
  "failed_chunks": 0,
  "artists": [
    { "name": "Artista", "status": "ok", "tracks": 25, "missing": [] }
  ]
}
```

Valores de `status` por artista: `ok`, `no_tracks`, `no_setlist`.

---

## Obtencion de API Keys

### Spotify

1. Ve a [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) e inicia sesion.
2. Haz clic en **Create App**. Completa nombre y descripcion.
3. Copia el **Client ID** y el **Client Secret** — son `SPOTIPY_CLIENT_ID` y `SPOTIPY_CLIENT_SECRET`.
4. Para obtener el **Refresh Token**, ejecuta `tokens.py` (incluido en este repositorio) o usa una herramienta como el [Spotify Refresh Token Generator](https://github.com/kylesarre/Spotify-RefreshTokenGenerator). Scopes requeridos: `playlist-modify-private playlist-modify-public`.

### setlist.fm

1. Ve a [api.setlist.fm](https://api.setlist.fm) y crea una cuenta gratuita.
2. Solicita una API key desde la configuracion de tu cuenta.
3. Copia la clave en `SETLISTFM_API_KEY`.

---

## Stack tecnologico

- **Backend:** Flask 3, Requests, python-dotenv, Flask-Limiter, gunicorn
- **APIs:** Spotify Web API, setlist.fm API v1
- **Frontend:** JavaScript vanilla, fuente Space Mono, mobile-drag-drop (CDN)
- **Concurrencia:** `ThreadPoolExecutor` (32 workers) para resolucion paralela de artistas y tracks
- **Cache:** Cache TTL en memoria (1 hora) para respuestas de setlist.fm
