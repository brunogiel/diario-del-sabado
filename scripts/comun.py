"""
Lo que comparten todos los scripts: dónde viven tus datos y cómo se habla con Gmail.

El código vive en la carpeta del skill. Tus datos viven aparte, en `DIARIO_HOME`
(por defecto `~/.diario-del-sabado/`), así el skill se puede actualizar o borrar
sin perder nada y el repo nunca ve tu mail:

  ~/.diario-del-sabado/
    config.json      quién sos, a dónde llega el diario, tus secciones (lo escribe el kickoff)
    fuentes.json     qué newsletters entran (lo escribe el kickoff; editable a mano)
    perfil.md        lo que «Cómo te afecta» necesita saber de vos
    state/           lo de la corrida de esta semana
    ediciones/       un HTML por sábado + ediciones/kindle/
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path(os.environ.get('DIARIO_HOME', '~/.diario-del-sabado')).expanduser()
SKILL = Path(__file__).resolve().parent.parent
GWS = shutil.which('gws') or next((x for x in ('/opt/homebrew/bin/gws', '/usr/local/bin/gws')
                                   if Path(x).exists()), 'gws')


def zona_del_sistema():
    """La zona horaria de la máquina (macOS y Linux), o UTC si no se puede saber."""
    try:
        destino = os.path.realpath('/etc/localtime')
        return destino.split('zoneinfo/', 1)[1] if 'zoneinfo/' in destino else 'UTC'
    except OSError:
        return 'UTC'


def cortar(msg):
    """Error que el usuario puede arreglar: mensaje corto, sin traceback."""
    sys.exit(f'✗ {msg}')


DEFAULTS = {
    'nombre': '',
    'email': '',
    'kindle': None,
    'zona': zona_del_sistema(),
    'idioma': 'es',
    # Orden de las secciones de «Qué pasó». Una sección nueva que arme el modelo va al final con 📰.
    'secciones': [
        {'nombre': 'Internacional', 'emoji': '🌍'},
        {'nombre': 'AI', 'emoji': '🤖'},
        {'nombre': 'Tecnología y ciencia', 'emoji': '🔬'},
        {'nombre': 'Negocios', 'emoji': '💼'},
        {'nombre': 'Cultura y deportes', 'emoji': '⚽'},
    ],
    # Las 4 áreas con las que arranca cada párrafo del panorama de tapa.
    'panorama': ['Mundo', 'AI y ciencia', 'Negocios', 'Ideas'],
}


def leer_json(p: Path, que: str) -> dict:
    try:
        return json.loads(p.read_text() or '{}')
    except json.JSONDecodeError as e:
        cortar(f'{p} no es un JSON válido ({e}). Arreglalo a mano o corré el kickoff: «configurá el diario».')


def config() -> dict:
    p = HOME / 'config.json'
    c = {**DEFAULTS, **(leer_json(p, 'config') if p.exists() else {})}
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(c['zona'])
    except Exception:
        cortar(f'La zona horaria «{c["zona"]}» de config.json no existe. Usá un nombre como America/Argentina/Buenos_Aires.')
    return c


def fuentes() -> list:
    """Las fuentes activas de fuentes.json, con defaults para los campos opcionales."""
    p = HOME / 'fuentes.json'
    if not p.exists():
        cortar(f'No existe {p}. Corré el kickoff: «configurá el diario».')
    lista = leer_json(p, 'fuentes').get('fuentes')
    if not isinstance(lista, list) or not lista:
        cortar(f'{p} no tiene fuentes. Corré el kickoff o agregá {{"fuentes": [...]}}.')
    salida = []
    for i, f in enumerate(lista, 1):
        if not f.get('slug') or not f.get('remitentes'):
            cortar(f'La fuente {i} de fuentes.json necesita «slug» y «remitentes».')
        if f.get('activa', True):
            salida.append({'nombre': f['slug'], 'idioma': 'es', 'tipo': 'noticias', **f})
    return salida


def secciones():
    """(orden, emoji) de las secciones de noticias según config.json. Acepta textos sueltos."""
    s = [x if isinstance(x, dict) else {'nombre': str(x)} for x in config()['secciones']]
    return [x['nombre'] for x in s], {x['nombre']: x.get('emoji') or '📰' for x in s}


def gws_json(args):
    """Corre gws y devuelve el JSON. La línea del keyring no es JSON: se saltea.

    gws devuelve los errores de la API como JSON ({"error": {...}}) y sale con código 1.
    Eso NO es una respuesta: se levanta con el mensaje real (401 = falta `gws auth login`).
    """
    try:
        r = subprocess.run([GWS] + args, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError('no encuentro gws: npm install -g @googleworkspace/cli')
    out = r.stdout
    i = out.find('{')
    datos = None
    if i != -1:
        try:
            datos = json.loads(out[i:])
        except json.JSONDecodeError:
            pass
    if isinstance(datos, dict) and 'error' in datos:
        e = datos['error']
        msg = e.get('message', e) if isinstance(e, dict) else e
        code = e.get('code') if isinstance(e, dict) else None
        pista = ' (corré `gws auth login`)' if code in (401, 403) or 'invalid_grant' in str(msg) else ''
        raise RuntimeError(f'gws {code or ""}: {msg}{pista}'.replace('gws : ', 'gws: '))
    if datos is None or r.returncode != 0:
        raise RuntimeError(f'gws falló: {(r.stderr or out).strip()[:300]}')
    return datos
