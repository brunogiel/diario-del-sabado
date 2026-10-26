#!/usr/bin/env python3
"""
Paso 6b [DET]: arma el EPUB del diario para el Kindle / iPad.

Ya no aplana el HTML del mail: arma el libro directo de los datos
(state/diario.json, state/destilado/, state/semana.json, state/completo/), así
controla el orden y el índice.

Orden del libro (sin emojis en títulos, fuentes ordenadas por categoría pero sin subgrupos):
  Portada (imagen) · Índice nativo del Kindle (nav/NCX; el libro abre acá, no hay índice HTML)
  · Números de la semana · Tapa (intro) · Lecturas destacadas (si hay) · Opinión
  · Qué pasó (una parte por sección: intro + resumen de cada hecho)
  · Cómo te afecta · Dónde coinciden · Qué mirar · Para leer completo
  · Los newsletters completos (partes: Noticias / Tech y AI / Negocios e ideas
    → cada fuente con sus destacados → cada edición con su texto entero, sin el boilerplate del
    mail (header, sponsors, pie) y con un separador con la fuente arriba de cada título.
    TLDR sale como titular en caso normal + resumen, sin links)

Cada titular salta al newsletter de donde salió (las URLs del mail se
reescriben como anclas internas). El índice del Kindle es anidado: parte >
fuente > edición.

Solo EPUB: el PDF se sacó (el iPad lee el EPUB mejor).

Uso:
  kindle.py                  # la edición más nueva de ediciones/
  kindle.py 2026-10-10       # una fecha puntual
  kindle.py --con-emoji      # emojis en los títulos (default: sin, no se ven bien en todos los lectores)
Escribe ediciones/kindle/Newsletter semana N de <mes>.epub e imprime el JSON.
Todas las rutas son relativas a DIARIO_HOME (ver comun.py). Necesita pandoc y Pillow.
"""
import datetime as dt
import json
import zipfile
import re
import shutil
import subprocess
import sys
from pathlib import Path

from comun import HOME as BASE, config, secciones

EDICIONES = BASE / 'ediciones'
SALIDA = EDICIONES / 'kindle'
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']

ORDEN_SECCIONES, EMOJI_SECCION = secciones()
ORDEN_TIPO = {'noticias': 0, 'tech-ai': 1, 'negocio': 2, 'ideas': 3}   # solo ordena las fuentes


CSS = """
body { font-family: Georgia, serif; line-height: 1.5; }
h1 { font-size: 1.7em; margin: 0 0 .5em; border-bottom: 2px solid #000; padding-bottom: .15em; }
h2 { font-size: 1.3em; margin: 1.3em 0 .4em; border-bottom: 1px solid #000; }
h3 { font-size: 1.15em; margin: 1.2em 0 .3em; }
h4 { font-size: 1.05em; margin: 1.1em 0 .3em; }
small { display: block; font-size: .75em; text-transform: uppercase; letter-spacing: .08em; margin: 0 0 .3em; }
p { margin: 0 0 .7em; }
a { color: inherit; }
.intro { font-style: italic; margin: 0 0 1em; }
.cifra p { font-size: 1.4em; font-weight: bold; margin: .8em 0 0; }
.tapa p { font-size: 1.5em; font-weight: bold; line-height: 1.2; margin: 0 0 .4em; }
.item { font-weight: bold; margin: 1em 0 .1em; }
hr { border: 0; border-top: 3px double #000; margin: 2.2em 0 .6em; }
.fuente { font-size: .75em; text-transform: uppercase; letter-spacing: .1em; margin: 0 0 .2em; }
"""

# Los Kindle e-ink no tienen fuente de emoji. El iPad sí: los títulos los llevan.
EMOJI_RE = re.compile('[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF'
                      '️‍⚖✡]')


def esc(t) -> str:
    return str(t or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def limpio(t) -> str:
    """Texto que viene de afuera: sin emoji sueltos, escapado."""
    return esc(EMOJI_RE.sub('', str(t or '')))


class Libro:
    def __init__(self, semana, diario, destilado, sin_emoji):
        self.semana, self.diario, self.destilado = semana, diario, destilado
        self.sin_emoji = sin_emoji
        self.nombre = {f['slug']: f['nombre'] for f in semana['fuentes']}
        self.url, self.min, self.ancla = {}, {}, {}
        for f in semana['fuentes']:
            for ed in f['ediciones']:
                a = f'ed-{f["slug"]}-{ed["n"]}'
                web_id = f'{f["slug"]}:{ed["n"]}:web'
                self.url[web_id] = ed['web'] or ed['gmail']
                self.min[web_id] = ed['minutos']
                for u in [ed.get('web'), ed.get('gmail')] + [l['url'] for l in ed['links']]:
                    if u:
                        self.ancla.setdefault(u, a)
                for l in ed['links']:
                    self.url[l['id']] = l['url']

    def emo(self, e: str) -> str:
        return '' if self.sin_emoji or not e else e + ' '

    def link(self, lid):
        """id del destilado -> ancla interna de su edición (o None)."""
        u = self.url.get((lid or '').strip())
        return self.ancla.get(u) if u else None

    def a(self, lid, texto, negrita=False):
        an = self.link(lid)
        t = f'<b>{texto}</b>' if negrita else texto
        return f'<a href="#{an}">{t}</a>' if an else t


def seccion_de_semana(L: Libro):
    """Agrupa lo_que_paso por sección con el mismo orden que el mail."""
    grupos = {}
    for it in L.diario.get('lo_que_paso', []):
        grupos.setdefault((it.get('seccion') or 'Otros').strip(), []).append(it)
    claves = sorted(grupos, key=lambda k: (ORDEN_SECCIONES.index(k) if k in ORDEN_SECCIONES
                                           else len(ORDEN_SECCIONES), list(grupos).index(k)))
    return claves, grupos


def slug_seccion(k: str) -> str:
    return 'sec-' + re.sub(r'[^a-z0-9]+', '-', k.lower().replace('á', 'a').replace('é', 'e')
                           .replace('í', 'i').replace('ó', 'o').replace('ú', 'u')).strip('-')


# --- Limpieza del texto de cada newsletter para el Kindle  ---
# 1) Pie: desde la primera marca de pie en el último 60% del texto, se corta todo.
PIE = re.compile(r'unsubscribe|darte de baja|dar de baja|you received this (e-?mail|newsletter)|'
                 r'you are receiving this|update your preferences|manage your subscriptions?|'
                 r'¿querés cambiar la forma|if you received this newsletter from someone else|'
                 r'you are reading a plain text version|^links:$|love tldr\?|want to advertise in|'
                 r'want to share this edition|wanna partner with us|sponsors who make this newsletter|'
                 r'el apoyo de nuestros lectores|^together with us$|more like this|'
                 r'for more (of our )?newsletters|explore (more|all) (of )?our newsletters|manage (my|your) (e-?mail )?newsletters|'
                 r'connect with us on|find me on x|'
                 r'all rights reserved|privacy policy|what did you think of this (post|edition)|'
                 r'get more out of your subscription|what is included in a subscription|want to sponsor|'
                 r'^introducing [\w .]{2,30}: ', re.I)
# 2) Líneas sueltas de ruido, estén donde estén.
RUIDO = re.compile(r'view (this post )?in (your )?browser|newsletter logo|^view (this post )?(on the web|online)'
                   r'|^view image:|^follow image link:|^caption:\s*$|sign up\s*\|?\s*advertise|view online'
                   r'|^(tldr|share|subscribe|subscribe →|free version|sign up|advertise)$'
                   r'|(was this|if this) (newsletter|e-?mail|post) (was )?forwarded|forward (this|it) to a friend'
                   r'|refer a friend|^together with\b|read online|^\[[^\]]{0,90}\]$|ad-free reading'
                   r'|subscribe to (the times|new york times games)|annual games subscribers'
                   r'|the times relies on subscribers|this is a free preview|get the new york times app'
                   r'|^\s*\[ ?\]\s*$|^\*+$', re.I)
# 3) Bloques de sponsor: desde la marca hasta el próximo separador (o 20 líneas).
SPONSOR = re.compile(r'^#*\s*_?from our sponsors|sponsored by|\(sponsor\)\s*$|^_?sponsor_?$|'
                     r'^(presented|brought to you) by', re.I)
SEPARADOR = re.compile(r'^(?=(?:.*[-=_*—–]){3})[^\w]*$')   # línea de rayas, sin texto
CERO = re.compile('[\u200b-\u200f\u034f\u00ad\u2060\ufeff]')


def _mayus(t: str) -> bool:
    letras = [c for c in t if c.isalpha()]
    return len(letras) >= 6 and sum(c.isupper() for c in letras) / len(letras) > .85


def limpiar_lineas(texto: str, asunto: str = '') -> list:
    """Texto plano de juntar.py -> líneas sin boilerplate de mail (header, sponsor, pie)."""
    lineas = [re.sub(r'\s*\[\d+\]', '', CERO.sub('', l)).strip() for l in texto.splitlines()]
    lineas = [re.sub(r'^[-=_—–]{3,}(?=\w|\*)', '', l) for l in lineas]   # «-----**Good morning**»
    # pie
    desde = len(lineas) * 2 // 5
    for i in range(desde, len(lineas)):
        if len(lineas[i]) <= 200 and PIE.search(lineas[i]):    # una línea larga es texto, no pie
            lineas = lineas[:i]
            break
    out, saltar, contenido = [], 0, False
    titulos = {l.casefold() for l in lineas[:12] if l} | {asunto.strip().casefold()}
    for i, l in enumerate(lineas):
        if saltar:
            saltar -= 1
            if SEPARADOR.fullmatch(l):
                if contenido:
                    saltar = 0
            elif l:
                contenido = True
            continue
        if SPONSOR.search(l):
            saltar, contenido = 20, False
            continue
        if not l or RUIDO.search(l) or SEPARADOR.fullmatch(l):
            continue
        if not out and asunto and l.casefold().strip(' .') in (
                asunto.casefold().strip(' .'), re.sub(r'^@\w+:\s*', '', asunto).casefold().strip(' .')):
            continue                         # el título ya va arriba, en el separador
        # título repetido en mayúsculas (Every): «WHY WE REPLACED…» bajo «Why we replaced…»
        if _mayus(l) and i < 12 and sum(t == l.casefold() for t in titulos) and \
                any(x.casefold() == l.casefold() and not _mayus(x) for x in lineas[:12] + [asunto]):
            continue
        out.append(l)
    return out


def _md(t: str) -> str:
    """Escapa y pasa el markdown que deja juntar.py (**negrita**, _itálica_) a HTML."""
    t = limpio(t)
    t = re.sub(r'\*\*\s*(.+?)\s*\*\*', r'<b>\1</b>', t)
    t = re.sub(r'(?<![\w/])_(\S(?:[^_]*\S)?)_(?!\w)', r'<i>\1</i>', t)
    return t.replace('**', '').replace('<i></i>', '').replace('<b></b>', '')


def texto_a_html(texto: str, asunto: str = '') -> str:
    """Texto plano -> párrafos limpios. '** Título' y '### Título' son subtítulos."""
    out = []
    for linea in limpiar_lineas(texto, asunto):
        if re.match(r'caption:\s*\S', linea, re.I):           # epígrafe de una foto que no está
            out.append(f'<p><i>{_md(linea.split(":", 1)[1].strip())}</i></p>')
            continue
        m = re.match(r'^(\*\*|#{1,6})\s+(.*)$', linea)
        if m:
            t = _md(m.group(2).strip('*_ '))
            if t:
                out.append(f'<p><b>{t}</b></p>')
        else:
            t = _md(linea)
            if re.sub(r'<[^>]+>|\W', '', t):
                out.append(f'<p>{t}</p>')
    return '\n'.join(out)


# --- TLDR: todo son links (no se abren en el Kindle). Cada ítem sale como titular normal + resumen.
TLDR_FIN = re.compile(r'\((\d+ (minute|page) read|sponsor|github repo|website|[a-z ]{3,20})\)$', re.I)


def _caso_normal(titular: str, contexto: str) -> str:
    """«ANTHROPIC S-1 SHOWS…» -> «Anthropic S-1 shows…». Cada palabra toma la forma con la que
    aparece en el resumen a mitad de frase (nombres propios, siglas, HomeView); si no, minúscula."""
    propia, minus = {}, set()
    toks = re.findall(r"[\w$][\w'’&$-]*|[.!?:]", contexto)
    for prev, w in zip(['.'] + toks, toks):
        if not re.match(r'[\w$]', w):
            continue
        w = re.sub(r"['’][sS]$", '', w)
        k = w.casefold()
        if w == w.lower():
            minus.add(k)
        elif prev not in '.!?:' or w.isupper() or not w[1:].islower():
            propia.setdefault(k, w)
    def forma(n):
        if re.fullmatch(r'[A-Z]{1,3}-\d+[A-Z]?', n):
            return n                    # S-1, F-35
        if '-' in n.strip('-'):
            return '-'.join(forma(x) if x else x for x in n.split('-'))
        base, pos = (n[:-2], n[-2:]) if re.search(r"['’][sS]$", n) else (n, '')
        k = base.casefold()
        if k in propia and (k not in minus or not propia[k][1:].islower() and not propia[k].isupper()):
            return propia[k] + pos.lower()
        if re.fullmatch(r'[A-Z]+\d+|\d+[A-Z]{1,3}', base):
            return n                    # códigos (5G, M4)
        return n.lower()
    out = []
    for w in titular.split():
        m = re.match(r"^([^\w$]*)([\w$][\w'’&$-]*?)([^\w$]*)$", w)
        out.append(m.group(1) + forma(m.group(2)) + m.group(3) if m else w.lower())
    t = re.sub(r'([.?!:] )([a-z])', lambda m: m.group(1) + m.group(2).upper(), ' '.join(out))
    return t[:1].upper() + t[1:]


def tldr_a_html(texto: str):
    """Devuelve el HTML de los ítems o None si no se pudo parsear limpio (cae a texto_a_html)."""
    lineas = [re.sub(r'\s*\[\d+\]', '', CERO.sub('', l)).strip() for l in texto.splitlines()]
    ini = next((i for i, l in enumerate(lineas) if re.match(r'^TLDR( [A-Za-z]+)? \d{4}-\d{2}-\d{2}', l)), None)
    if ini is None:
        return None
    fin = next((i for i in range(ini, len(lineas)) if re.search(
        r'^love tldr|^want to advertise|^links:$|^want to work at tldr', lineas[i], re.I)), len(lineas))
    L = lineas[ini + 1:fin]
    items, seccion, i = [], None, 0
    es_emoji = lambda s: s and not re.search(r'[\w]', s)
    while i < len(L):
        l = L[i]
        if not l or es_emoji(l):
            i += 1
            continue
        if _mayus(l) and not TLDR_FIN.search(l) and (i > 0 and (es_emoji(L[i - 1]) or
                                                               (not L[i - 1] and i > 1 and es_emoji(L[i - 2])))):
            seccion = l.title() if len(l) > 4 else l
            i += 1
            continue
        if _mayus(l):
            tit, j = [l], i + 1
            while not TLDR_FIN.search(tit[-1]) and j < len(L) and L[j] and len(tit) < 4:
                tit.append(L[j]); j += 1
            titular = ' '.join(tit)
            resumen = []
            while j < len(L) and not L[j]:
                j += 1                      # el resumen viene después de una línea en blanco
            while j < len(L) and L[j] and not (_mayus(L[j]) and len(resumen) > 0 and TLDR_FIN.search(' '.join(L[j:j + 3]))):
                resumen.append(L[j]); j += 1
            m = TLDR_FIN.search(titular)
            etiqueta = m.group(1).lower() if m else ''
            titular = TLDR_FIN.sub('', titular).strip()
            resumen_t = ' '.join(resumen)
            if m and 'sponsor' not in etiqueta and 'TLDR' not in titular.upper().split() and not re.search(r'\bat tldr\b', titular, re.I):
                items.append((seccion, _caso_normal(titular, resumen_t + ' . ' + ' . '.join(x for x in L if x and not _mayus(x))), etiqueta, resumen_t))
            i = j
            continue
        i += 1      # texto suelto fuera de un ítem (sponsor sin titular, intro): afuera
    if len(items) < 3:
        return None
    out, actual = [], object()
    for sec, tit, et, res in items:
        if sec != actual and sec:
            out.append(f'<p><b><i>{limpio(sec)}</i></b></p>')
        actual = sec
        mins = re.match(r'(\d+) (minute|page)', et or '')
        meta = f' <i>· {mins.group(1)} {"min" if mins.group(2) == "minute" else "pág."}</i>' if mins else ''
        out.append(f'<p><b>{limpio(tit)}</b></p><p>{_md(res)}{meta}</p>')
    return '\n'.join(out)


def partes_libro(L: Libro, rango, n_ed, n_fuentes):
    semana, diario = L.semana, L.diario
    claves, grupos = seccion_de_semana(L)
    con = [f for f in semana['fuentes'] if f['ediciones']]
    con = sorted(con, key=lambda f: ORDEN_TIPO.get(f['tipo'], 9))

    h = []
    # Índice: solo el nativo del Kindle (nav/NCX, lo arma pandoc con los h1-h3). Sin índice HTML.
    lects = L.lecturas

    # --- Números
    nums = []
    for n in diario.get('numeros', []):
        if not n.get('fuente'):
            continue
        fuente = esc(L.nombre.get(n['fuente'], n['fuente']))
        nums.append(f'<div class="cifra"><p>{limpio(n["cifra"])}</p></div><p>{limpio(n.get("que"))} '
                    f'<small>{L.a(n.get("link"), fuente)}</small></p>')
    if nums:
        h.append(f'<h1 id="numeros">{L.emo("🔢")}Números de la semana</h1>' + ''.join(nums))

    # --- Tapa
    tapa = diario.get('tapa') or {}
    h.append('<h1 id="tapa">La tapa</h1>'
             f'<div class="tapa"><p>{limpio(tapa.get("titulo"))}</p></div><p>{limpio(tapa.get("bajada"))}</p>'
             + ''.join('<p>' + re.sub(r'^([^.]{1,22}\.)', r'<b>\1</b>', limpio(x)) + '</p>'
                       for x in tapa.get('panorama', [])) +
             f'<p><small>{n_ed} newsletters de {n_fuentes} fuentes · {rango}</small></p>')

    # --- Lecturas destacadas: los links que guardaste, con el texto entero adentro
    if lects:
        lp = [f'<h1 id="lecturas">{L.emo("⭐")}Lecturas destacadas</h1>',
              '<p><em>Lo que guardaste esta semana para leer acá.</em></p>']
        for x in lects:
            meta = ' · '.join(t for t in (x.get('autor'), x.get('publicado'),
                                          f'~{x["minutos"]} min' if x.get('minutos') else None) if t)
            arch = BASE / 'state' / 'completo' / f'lectura-{x["n"]}.txt'
            cuerpo = texto_a_html(arch.read_text(), x.get('titulo') or '') if arch.exists() else \
                f'<p>(no se pudo bajar el texto: {esc(x.get("url"))})</p>'
            lp.append(f'<h2 id="lectura-{x["n"]}">{limpio(x.get("titulo") or x.get("url"))}</h2>'
                      f'<p><small>{limpio(meta)}</small></p><p><em>{limpio(x.get("resumen"))}</em></p>'
                      f'{cuerpo}<p><small>{esc(x.get("url"))}</small></p>')
        h.append('\n'.join(lp))

    # --- Opinión
    op = diario.get('opinion') or {}
    if op.get('parrafos'):
        h.append(f'<h1 id="opinion">Opinión</h1><p><strong>{limpio(op.get("titulo"))}</strong></p>'
                 + ''.join(f'<p>{limpio(x)}</p>' for x in op['parrafos'])
                 + '<p><small>Opinión de Claude, escrita a partir de tus newsletters. Discutila.</small></p>')

    # --- Qué pasó: una parte por sección (intro + hechos)
    if claves:
        partes = ['<h1 id="paso">Qué pasó</h1>']
        intros = diario.get('secciones_intro') or {}
        for k in claves:
            partes.append(f'<h2 id="{slug_seccion(k)}">{L.emo(EMOJI_SECCION.get(k, "📰"))}{esc(k)}</h2>')
            if intros.get(k):
                partes.append(f'<p><em>{limpio(intros[k])}</em></p>')
            for it in grupos[k]:
                partes.append(
                    f'<p><strong>{L.a(it.get("link"), limpio(it.get("titulo")))}</strong></p>'
                    f'<p>{limpio(it.get("texto"))}</p>'
                    f'<p><small>{limpio(L.nombre.get(it.get("fuente"), it.get("fuente")))}</small></p>')
        h.append('\n'.join(partes))

    # --- Cómo te afecta
    if diario.get('como_te_afecta'):
        h.append(f'<h1 id="afecta">{L.emo("🎯")}Cómo te afecta</h1>' + ''.join(
            f'<p><b>{limpio(x.get("frente"))}.</b> {limpio(x.get("texto"))}</p>'
            for x in diario['como_te_afecta']))

    # --- Dónde coinciden
    co = diario.get('coinciden') or {}
    if co.get('versiones'):
        h.append(f'<h1 id="coinciden">{L.emo("⚖️")}Dónde coinciden y dónde no</h1>'
                 f'<p><strong>{limpio(co.get("tema"))}</strong></p><p>{limpio(co.get("texto"))}</p>'
                 + ''.join(f'<p><b>{limpio(L.nombre.get(v.get("fuente"), v.get("fuente")))}.</b> '
                           f'{L.a(v.get("link"), limpio(v.get("dice")))}</p>' for v in co['versiones']))

    # --- Próximos
    if diario.get('proximos'):
        h.append(f'<h1 id="proximos">{L.emo("📅")}Qué mirar en las próximas semanas</h1>' + ''.join(
            f'<p><b>{limpio(x.get("cuando"))}</b> · {L.a(x.get("link"), limpio(x.get("que")))} '
            f'<small>{limpio(L.nombre.get(x.get("fuente"), x.get("fuente")))}</small></p>'
            for x in diario['proximos']))

    # --- Para leer completo
    if diario.get('leer_completo'):
        items = []
        for x in diario['leer_completo']:
            mins = L.min.get((x.get('link') or '').strip())
            meta = limpio(L.nombre.get(x.get('fuente'), x.get('fuente'))) + (f' · {mins} min' if mins else '')
            items.append(f'<p><strong>{L.a(x.get("link"), limpio(x.get("titulo")))}</strong></p>'
                         f'<p>{limpio(x.get("por_que"))} <small>{meta}</small></p>')
        h.append(f'<h1 id="leer">{L.emo("📖")}Para leer completo</h1>' + ''.join(items))

    # --- Los newsletters completos: parte > fuente > edición
    ap = ['<h1 id="completos">Los newsletters completos</h1>',
          '<p>Cada titular del diario salta a la edición de donde salió. El índice del Kindle '
          'lleva a cada newsletter.</p>']
    for f in con:
        ap.append(f'<h2 id="fuente-{f["slug"]}">{esc(f["nombre"])}</h2>')
        dest = (L.destilado.get(f['slug']) or {}).get('destacados', [])[:3]
        if dest:
            ap.append('<p><small>Lo mejor de la semana</small></p>' + ''.join(
                f'<p>{L.a(d.get("link"), "<b>" + limpio(d.get("titulo")) + "</b>")}. '
                f'{limpio(d.get("linea"))}</p>' for d in dest))
        for ed in f['ediciones']:
            arch = BASE / 'state' / 'completo' / f'{f["slug"]}-{ed["n"]}.txt'
            texto = arch.read_text() if arch.exists() else ''
            cuerpo = ((f['slug'].startswith('tldr') and tldr_a_html(texto)) or texto_a_html(texto, ed['asunto'])
                      ) if texto else '<p>(sin texto guardado)</p>'
            fecha = ' '.join(ed['fecha'].split()[:4])
            # Separador entre posteos: raya + fuente arriba del título, para saber siempre dónde estás
            ap.append(f'<hr/><div class="fuente">{esc(f["nombre"])}</div>'
                      f'<h3 id="ed-{f["slug"]}-{ed["n"]}">{limpio(ed["asunto"])}</h3>'
                      f'<p><small>{limpio(fecha)} · ~{ed["minutos"]} min</small></p>{cuerpo}')
    h.append('\n'.join(ap))
    return h


def abrir_en_indice(epub: Path):
    """El libro abre en el Índice: portada y nav quedan fuera de la lectura lineal
    y la guía marca el Índice como inicio del texto."""
    tmp = epub.with_suffix('.tmp')
    with zipfile.ZipFile(epub) as zin, zipfile.ZipFile(tmp, 'w') as zout:
        zout.writestr(zipfile.ZipInfo('mimetype'), zin.read('mimetype'), zipfile.ZIP_STORED)
        for item in zin.infolist():
            if item.filename == 'mimetype':
                continue
            data = zin.read(item.filename)
            if item.filename == 'EPUB/content.opf':
                t = data.decode('utf-8')
                t = t.replace('<itemref idref="cover_xhtml" />', '<itemref idref="cover_xhtml" linear="no" />')
                # El índice nativo (nav) va en la lectura, justo después de la portada, y el libro abre ahí
                t = re.sub(r'\s*<reference type="toc"[^>]*/>', '', t)
                t = t.replace('</guide>', '  <reference type="toc" title="Índice" href="nav.xhtml" />\n'
                                          '    <reference type="text" title="Índice" href="nav.xhtml" />\n  </guide>')
                data = t.encode('utf-8')
            zout.writestr(item, data, zipfile.ZIP_DEFLATED)
    tmp.replace(epub)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    sin_emoji = '--con-emoji' not in sys.argv
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        return
    hechas = sorted(p.stem for p in EDICIONES.glob('*.html'))
    if not args and not hechas:
        sys.exit('No hay ninguna edición en ediciones/: primero corré armar.py.')
    fecha = args[0] if args else hechas[-1]
    hoy = dt.date.fromisoformat(fecha)
    semana_n = (hoy.day - 1) // 7 + 1
    mes = MESES[hoy.month - 1]
    ordinal = ['primera', 'segunda', 'tercera', 'cuarta', 'quinta'][semana_n - 1]
    titulo = f'Newsletter {ordinal} semana de {mes}'

    semana = json.loads((BASE / 'state' / 'semana.json').read_text())
    diario = json.loads((BASE / 'state' / 'diario.json').read_text())
    destilado = {}
    for p in (BASE / 'state' / 'destilado').glob('*.json'):
        try:
            destilado[p.stem] = json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    desde = dt.datetime.fromisoformat(semana['desde']).date()
    hasta = dt.datetime.fromisoformat(semana['hasta']).date() - dt.timedelta(days=1)
    con = [f for f in semana['fuentes'] if f['ediciones']]
    n_ed = sum(len(f['ediciones']) for f in con)

    L = Libro(semana, diario, destilado, sin_emoji)
    from lecturas import cargar_semana
    L.lecturas = cargar_semana()
    rango = (f'del {desde.day} al {hoy.day} de {mes}' if desde.month == hoy.month
             else f'del {desde.day} de {MESES[desde.month - 1]} al {hoy.day} de {mes}')
    cuerpo = '\n'.join(partes_libro(L, rango, n_ed, len(con)))

    SALIDA.mkdir(exist_ok=True)
    # Portada: diario clásico con la etiqueta «HECHO CON IA PARA <NOMBRE>»
    from portada import portada as portada_a
    nombre = config()['nombre']
    tit = [t[0].upper() + t[1:] for t in
           (x.strip() for x in re.split(r',\s+|\s+y\s+(?=[A-ZÁÉÍÓÚ])', (diario.get('tapa') or {}).get('titulo', ''))) if t][:3]
    cover = SALIDA / 'portada.png'
    portada_a(tit, hoy.isocalendar()[1], f'{hoy.day} de {mes} de {hoy.year}', n_ed, len(con), nombre).save(cover, optimize=True)

    html_f = SALIDA / 'libro.html'
    html_f.write_text(f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
                      f'<title>{esc(titulo)}</title></head><body>{cuerpo}</body></html>',
                      encoding='utf-8')
    css_f = SALIDA / 'epub.css'
    css_f.write_text(CSS, encoding='utf-8')
    epub = SALIDA / f'{titulo}.epub'
    pandoc = shutil.which('pandoc') or next((x for x in ('/opt/homebrew/bin/pandoc', '/usr/local/bin/pandoc')
                                             if Path(x).exists()), None)
    if not pandoc:
        sys.exit('Falta pandoc para armar el EPUB: https://pandoc.org/installing.html')
    subprocess.run([pandoc, str(html_f), '-o', str(epub), '-f', 'html',
                    '--metadata', f'title={titulo}', '--metadata', 'lang=es',
                    '--metadata', f'author=Claude para {nombre}' if nombre else 'author=Claude', '--metadata', 'toc-title=Índice', '--metadata', f'date={fecha}',
                    '--css', str(css_f), '--epub-cover-image', str(cover),
                    '--toc', '--toc-depth=3', '--split-level=1',
                    '--epub-title-page=false'], check=True)
    abrir_en_indice(epub)
    for tmp in (html_f, css_f, cover):
        tmp.unlink()
    print(json.dumps({'epub': str(epub), 'titulo': titulo, 'kb': epub.stat().st_size // 1024},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
