#!/usr/bin/env python3
"""
Paso 1 del diario del sábado [DET]: junta los newsletters de la semana.

Busca en Gmail por remitente (sin filtro de carpeta: toma bandeja y archivados),
lee cada mail con `gws gmail +read` y deja por fuente:
  - texto plano recortado (para que lo destile un subagente)
  - links numerados con id estable `slug:edicion:n`
  - el link a la versión web de la edición, id `slug:edicion:web`
  - minutos de lectura estimados de la edición

El modelo nunca escribe una URL: cita ids. `armar.py` resuelve los ids contra
`state/semana.json`, así un link inventado no puede llegar al diario.

Uso:
  juntar.py                       # semana que termina hoy (sábado anterior 00:00 → ahora)
  juntar.py --desde 2026-10-03 --hasta 2026-10-10

Salida:
  state/semana.json               # índice completo: fuentes, ediciones, links
  state/fuentes/<slug>.txt        # el material que lee el subagente de esa fuente
  state/completo/<slug>-<n>.txt   # el texto entero de cada edición, sin recortar (lo usa kindle.py)
  state/lecturas_semana.json      # las lecturas pendientes de state/lecturas.json (vía lecturas.py)

Todas las rutas son relativas a DIARIO_HOME (ver comun.py).
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

from comun import HOME as BASE, config, cortar, fuentes, gws_json

ART = ZoneInfo(config()['zona'])
MAX_TEXTO = 14000        # caracteres de texto por edición que ve el subagente
MAX_LINKS = 45           # links por edición
PALABRAS_POR_MIN = 230

WEB_RX = re.compile(
    r'(view|read|open|see)\s+(this\s+|it\s+|the\s+)?(email\s+|post\s+|newsletter\s+)?'
    r'(in|on)\s+(your\s+|a\s+|the\s+)?(browser|web|online)|view online|read online|'
    r'web version|online version|ver (en|la versi[oó]n) (el\s+)?(navegador|web|online)|'
    r'versi[oó]n (web|online)|ver online|leer online|read in app|ver en la web',
    re.I)
WEB_HREF_RX = re.compile(r'campaign-archive\.com|mailchi\.mp/|substack\.com/p/|beehiiv\.com/p/', re.I)
BASURA_RX = re.compile(
    r'unsubscribe|desuscrib|darse de baja|manage (your )?(preferences|subscription)|'
    r'privacy|terms|preferences|update your|advertise|sponsor|gift|refer|download the app|'
    r'facebook|twitter|instagram|linkedin|youtube|tiktok|mailto:|forward', re.I)



class Anclas(HTMLParser):
    """Junta (texto, href) de cada <a>."""

    def __init__(self):
        super().__init__()
        self.anclas, self._href, self._txt = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self._href = dict(attrs).get('href')
            self._txt = []
        elif tag == 'img' and self._href is not None:
            alt = dict(attrs).get('alt')
            if alt:
                self._txt.append(alt)

    def handle_data(self, data):
        if self._href is not None:
            self._txt.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self._href is not None:
            txt = re.sub(r'\s+', ' ', ''.join(self._txt).replace('\xad', '')).strip()
            self.anclas.append((txt, self._href.strip()))
            self._href = None


def limpiar_texto(t):
    t = t.replace('​', '').replace('͏', '').replace('\xad', '')
    t = re.sub(r'\(\s*https?://\S+\s*\)', '', t)      # links entre paréntesis del text/plain
    t = re.sub(r'https?://\S+', '', t)
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n\s*\n+', '\n\n', t)
    return t.strip()


def desenvolver(url):
    """Saca la URL real de los links de tracking que la traen adentro (TLDR, Every,
    Kit, Substack) y le quita los utm_. Achica el mail y evita el rastreo. Si no
    reconoce el formato, devuelve el link tal cual."""
    import base64
    from urllib.parse import unquote, urlsplit, urlunsplit, parse_qsl, urlencode
    real = url
    try:
        if '/CL0/' in url:                                    # TLDR, Every (icu.every.to)
            real = unquote(url.split('/CL0/', 1)[1].split('/', 1)[0])
        elif 'substack.com/redirect/' in url:                 # Substack: base64 de un JSON con "e"
            tramo = url.split('/redirect/', 1)[1].split('/')[1].split('?')[0].split('.')[0]
            real = json.loads(base64.urlsafe_b64decode(tramo + '=' * (-len(tramo) % 4)))['e']
        else:                                                 # Kit / ConvertKit: último tramo en base64
            tramo = urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1]
            if tramo.startswith('aHR0c'):
                real = base64.urlsafe_b64decode(tramo + '=' * (-len(tramo) % 4)).decode()
        if not real.startswith('http'):
            return url
        u = urlsplit(real)
        q = [(k, v) for k, v in parse_qsl(u.query) if not k.lower().startswith(('utm_', 'mc_', 'ref', 'token')) and k != 'r']
        return urlunsplit((u.scheme, u.netloc, u.path, urlencode(q), ''))
    except Exception:
        return url


def extraer(msg):
    texto = limpiar_texto(msg.get('body_text') or '')
    anclas = []
    if msg.get('body_html'):
        p = Anclas()
        try:
            p.feed(msg['body_html'])
        except Exception:
            pass
        anclas = p.anclas
        # Algunos (NYT) mandan un text/plain de 2 líneas: si el HTML trae más, manda el HTML.
        crudo = re.sub(r'<(script|style|head)[^>]*>.*?</\1>', ' ', msg['body_html'], flags=re.S | re.I)
        crudo = re.sub(r'<(br|/p|/div|/tr|/h\d|/li)[^>]*>', '\n', crudo, flags=re.I)
        desde_html = limpiar_texto(html.unescape(re.sub(r'<[^>]+>', ' ', crudo)))
        if len(desde_html) > 2 * len(texto):
            texto = desde_html
    asunto = re.sub(r'\W+', ' ', (msg.get('subject') or '').lower()).strip()
    web = None
    for txt, href in anclas:        # 1) el link que dice "view in browser"
        if href.startswith('http') and WEB_RX.search(txt):
            web = href
            break
    if not web:                     # 2) el archivo web de la plataforma
        web = next((h for _, h in anclas if WEB_HREF_RX.search(h)), None)
    if not web and len(asunto) > 15:  # 3) el título de la nota linkeado
        web = next((h for t, h in anclas if h.startswith('http')
                    and re.sub(r'\W+', ' ', t.lower()).strip() == asunto), None)
    links, vistos = [], set()
    for txt, href in anclas:
        if not href.startswith('http') or href in vistos:
            continue
        if len(txt) < 4 or BASURA_RX.search(txt) or BASURA_RX.search(href[:60]):
            continue
        vistos.add(href)
        links.append({'texto': txt[:160], 'url': desenvolver(href)})
        if len(links) >= MAX_LINKS:
            break
    return texto, (desenvolver(web) if web else None), links


def coincide(remitente, patrones):
    remitente = (remitente or '').lower()
    return any(remitente.endswith(p.lower()) if p.startswith('@') else remitente == p.lower()
               for p in patrones)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--desde', help='YYYY-MM-DD (incluido)')
    ap.add_argument('--hasta', help='YYYY-MM-DD (excluido)')
    a = ap.parse_args()

    ahora = dt.datetime.now(ART)
    if a.desde:
        desde = dt.datetime.fromisoformat(a.desde).replace(tzinfo=ART)
    else:
        dias = (ahora.weekday() - 5) % 7 or 7          # sábado anterior
        desde = (ahora - dt.timedelta(days=dias)).replace(hour=0, minute=0, second=0, microsecond=0)
    hasta = dt.datetime.fromisoformat(a.hasta).replace(tzinfo=ART) if a.hasta else ahora

    cfg = fuentes()
    (BASE / 'state' / 'fuentes').mkdir(parents=True, exist_ok=True)
    for viejo in (BASE / 'state' / 'fuentes').glob('*.txt'):
        viejo.unlink()
    (BASE / 'state' / 'completo').mkdir(parents=True, exist_ok=True)
    for viejo in (BASE / 'state' / 'completo').glob('*.txt'):
        viejo.unlink()

    semana = {'desde': desde.isoformat(), 'hasta': hasta.isoformat(),
              'generado': ahora.isoformat(timespec='seconds'), 'fuentes': []}

    for f in cfg:
        froms = ' OR '.join(f'from:{r.lstrip("@")}' for r in f['remitentes'])
        q = f'({froms}) after:{int(desde.timestamp())} before:{int(hasta.timestamp())}'
        ids, token = [], None
        while True:
            params = {'userId': 'me', 'q': q, 'maxResults': 100}
            if token:
                params['pageToken'] = token
            try:
                res = gws_json(['gmail', 'users', 'messages', 'list', '--params', json.dumps(params),
                                '--format', 'json'])
            except RuntimeError as e:
                cortar(f'No pude buscar en Gmail: {e}')
            ids += [m['id'] for m in res.get('messages', [])]
            token = res.get('nextPageToken')
            if not token:
                break

        ediciones = []
        for mid in ids:
            try:
                m = gws_json(['gmail', '+read', '--id', mid, '--headers', '--html', '--format', 'json'])
            except Exception as e:  # un mail roto no frena la semana
                print(f'⚠ {f["slug"]} {mid}: {e}', file=sys.stderr)
                continue
            if not coincide((m.get('from') or {}).get('email'), f['remitentes']):
                continue
            if f.get('excluir_asunto') and re.search(f['excluir_asunto'], m.get('subject') or '', re.I):
                continue                # promos de la propia fuente (renová, oferta, encuesta)
            texto, web, links = extraer(m)
            ediciones.append({
                'message_id': mid,
                'thread_id': m.get('thread_id'),
                'asunto': (m.get('subject') or '').strip(),
                'fecha': m.get('date'),
                'gmail': f'https://mail.google.com/mail/u/0/#all/{m.get("thread_id") or mid}',
                'web': web,
                'minutos': max(1, round(len(texto.split()) / PALABRAS_POR_MIN)),
                'links': links,
                '_texto': texto,
            })
        ediciones.sort(key=lambda e: e['message_id'])   # ids de Gmail crecen con el tiempo

        partes = [f'# {f["nombre"]} ({f["idioma"]}), {len(ediciones)} ediciones esta semana\n']
        for i, e in enumerate(ediciones, 1):
            e['n'] = i
            partes.append(f'\n=== EDICIÓN {i} · {e["fecha"]} · "{e["asunto"]}" · '
                          f'id web: {f["slug"]}:{i}:web · ~{e["minutos"]} min ===\n')
            texto = e.pop('_texto')
            (BASE / 'state' / 'completo' / f'{f["slug"]}-{i}.txt').write_text(texto)
            partes.append(texto[:MAX_TEXTO])
            if e['links']:
                partes.append('\n--- links de esta edición (citar SOLO por id) ---')
                for k, l in enumerate(e['links'], 1):
                    l['id'] = f'{f["slug"]}:{i}:{k}'
                    partes.append(f'[{l["id"]}] {l["texto"]}')
        if ediciones:
            (BASE / 'state' / 'fuentes' / f'{f["slug"]}.txt').write_text('\n'.join(partes))

        semana['fuentes'].append({**{k: f[k] for k in ('slug', 'nombre', 'idioma', 'tipo')},
                                  'ediciones': ediciones})
        print(f'{f["slug"]:10} {len(ediciones):3} ediciones', file=sys.stderr)

    (BASE / 'state' / 'semana.json').write_text(json.dumps(semana, ensure_ascii=False, indent=1))
    total = sum(len(s['ediciones']) for s in semana['fuentes'])
    print(json.dumps({'desde': semana['desde'], 'hasta': semana['hasta'], 'ediciones': total,
                      'fuentes_con_material': [s['slug'] for s in semana['fuentes'] if s['ediciones']],
                      'fuentes_sin_material': [s['slug'] for s in semana['fuentes'] if not s['ediciones']]},
                     ensure_ascii=False))

    # Lecturas destacadas (links que guardaste a mano). Después del unlink de completo/.
    import lecturas
    lecturas.juntar()


if __name__ == '__main__':
    main()
