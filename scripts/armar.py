#!/usr/bin/env python3
"""
Pasos 4 y 5 del diario del sábado [DET]: arma el HTML y lo verifica.

Lee:
  state/semana.json          (de juntar.py: ediciones, links con id, versión web)
  state/destilado/<slug>.json (paso 2, un subagente por fuente)
  state/diario.json          (paso 3, la redacción)
  state/lecturas_semana.json (lecturas.py: links que guardaste a mano, sección «Lecturas destacadas»)

Escribe:
  ediciones/YYYY-MM-DD.html  (estilos inline: es el cuerpo del mail tal cual)
  state/verificacion.json    (lo que encontró el chequeo)

Los textos citan links por id (`nyt:2:5`, `every:1:web`). Este script los
resuelve contra semana.json. Un id que no existe NO se publica: el ítem sale
sin link y queda anotado en verificacion.json. Sale con código 1 si hubo
ids inventados, para que la corrida lo reporte.

Esquema de state/diario.json:
{
  "tapa": {"titulo": "...", "bajada": "...", "panorama": ["Mundo. ...", "AI y ciencia. ...", "Negocios. ...", "Ideas. ..."]},
  "secciones_intro": {"Internacional": "2 frases: qué tiene en común la sección esta semana y qué pesa más"},
  "lo_que_paso": [{"seccion": "Internacional", "titulo": "...", "texto": "...", "fuente": "nyt", "link": "nyt:2:5"}],
  "opinion": {"titulo": "...", "parrafos": ["...", "..."]},
  "como_te_afecta": [{"frente": "Trabajo", "texto": "..."}],
  "numeros": [{"cifra": "3,1%", "que": "...", "fuente": "cenital", "link": "cenital:2:4"}],
  "coinciden": {"tema": "...", "texto": "...",
                "versiones": [{"fuente": "nyt", "dice": "...", "link": "nyt:3:1"}]},
  "proximos": [{"cuando": "mar 14/10", "que": "...", "fuente": "intrigue", "link": "intrigue:2:3"}],
  "leer_completo": [{"titulo": "...", "por_que": "...", "fuente": "every", "link": "every:3:web"}]
}
Los destacados por fuente salen de state/destilado/<slug>.json (campo "destacados").

Uso: armar.py [--fecha YYYY-MM-DD]
Todas las rutas son relativas a DIARIO_HOME (ver comun.py).
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

from comun import HOME as BASE, secciones

MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

# Paleta: diario sobrio. Tinta, papel, un rojo de acento.
TINTA, GRIS, LINEA, PAPEL, ACENTO, SUAVE = '#1b1b1b', '#5f5f5f', '#e4dfd5', '#fbf9f4', '#9c2b1f', '#f3eee4'
# Orden y emoji de las secciones de noticias: salen de config.json. Una sección nueva va al final con 📰.
ORDEN_SECCIONES, EMOJI_SECCION = secciones()
EMOJI = {**EMOJI_SECCION,
         'Cómo te afecta': '🎯', 'Opinión': '✍️', 'Números de la semana': '🔢', 'Dónde coinciden y dónde no': '⚖️',
         'Qué mirar en las próximas semanas': '📅', 'Para leer completo': '📖', 'Por fuente': '📬', 'Lecturas destacadas': '⭐'}


def con_emoji(titulo):
    if titulo and not titulo[0].isalnum() and titulo[0] not in '¿¡«"':
        return titulo                     # la redacción ya le puso uno
    return f'{EMOJI.get(titulo, "📰")} {titulo}'


SERIF = "Georgia,'Times New Roman',serif"
SANS = "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"


def e(t):
    return html.escape(str(t or ''), quote=True)


class Links:
    """Resuelve ids a URLs y anota los que no existen."""

    def __init__(self, semana):
        self.url, self.min, self.malos, self.usados = {}, {}, [], set()
        for f in semana['fuentes']:
            for ed in f['ediciones']:
                web_id = f'{f["slug"]}:{ed["n"]}:web'
                self.url[web_id] = ed['web'] or ed['gmail']
                self.min[web_id] = ed['minutos']
                for l in ed['links']:
                    self.url[l['id']] = l['url']

    def __call__(self, lid, donde):
        if not lid:
            return None
        u = self.url.get(lid.strip())
        if u is None:
            self.malos.append({'id': lid, 'donde': donde})
        else:
            self.usados.add(lid)
        return u


def a(url, texto, color=ACENTO):
    if not url:
        return e(texto)
    return (f'<a href="{e(url)}" style="color:{color};text-decoration:none;'
            f'border-bottom:1px solid {LINEA};">{e(texto)}</a>')


def seccion(titulo, cuerpo, kicker=None):
    k = (f'<div style="font:600 11px/1 {SANS};letter-spacing:.14em;text-transform:uppercase;'
         f'color:{ACENTO};margin:0 0 6px;">{e(kicker)}</div>') if kicker else ''
    return (f'<tr><td style="padding:28px 28px 4px;">{k}'
            f'<h2 style="font:700 22px/1.25 {SERIF};color:{TINTA};margin:0 0 14px;'
            f'padding-bottom:8px;border-bottom:2px solid {TINTA};">{e(con_emoji(titulo))}</h2>'
            f'{cuerpo}</td></tr>')


def p(texto, size=16, color=TINTA, margen='0 0 12px', fam=SANS):
    return f'<p style="font:400 {size}px/1.6 {fam};color:{color};margin:{margen};">{texto}</p>'


def fecha_larga(d):
    return f'{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fecha', help='fecha de la edición YYYY-MM-DD (default: hoy)')
    args = ap.parse_args()

    semana = json.loads((BASE / 'state' / 'semana.json').read_text())
    diario = json.loads((BASE / 'state' / 'diario.json').read_text())
    destilado = {}
    for f in (BASE / 'state' / 'destilado').glob('*.json'):
        try:
            destilado[f.stem] = json.loads(f.read_text())
        except json.JSONDecodeError:
            print(f'⚠ destilado ilegible: {f.name}', file=sys.stderr)

    L = Links(semana)
    nombre = {f['slug']: f['nombre'] for f in semana['fuentes']}
    hoy = dt.date.fromisoformat(args.fecha) if args.fecha else dt.date.today()
    desde = dt.datetime.fromisoformat(semana['desde']).date()
    hasta = dt.datetime.fromisoformat(semana['hasta']).date() - dt.timedelta(days=1)
    con = [f for f in semana['fuentes'] if f['ediciones']]
    sin = [f for f in semana['fuentes'] if not f['ediciones']]
    n_ed = sum(len(f['ediciones']) for f in con)
    vacias = []

    def fuente_tag(slug):
        return f'<span style="font:600 11px/1 {SANS};letter-spacing:.06em;text-transform:uppercase;color:{GRIS};">{e(nombre.get(slug, slug))}</span>'

    filas = []
    filas_sec, filas_op, filas_nums = [], [], []   # se acomodan después de la tapa: números, opinión, secciones

    # 1. Tapa
    tapa = diario.get('tapa', {})
    filas.append(
        f'<tr><td style="padding:30px 28px 22px;border-bottom:1px solid {LINEA};text-align:center;">'
        f'<div style="font:600 11px/1 {SANS};letter-spacing:.2em;text-transform:uppercase;color:{GRIS};">'
        f'{e(fecha_larga(hoy))} · semana del {desde.day}/{desde.month} al {hasta.day}/{hasta.month}</div>'
        f'<div style="font:700 40px/1.05 {SERIF};color:{TINTA};margin:12px 0 4px;letter-spacing:-.5px;">El diario del sábado</div>'
        f'<div style="font:400 13px/1.4 {SANS};color:{GRIS};">{n_ed} newsletters de {len(con)} fuentes que te llegaron esta semana</div>'
        f'</td></tr>')
    idx_tras_tapa = len(filas) + (1 if tapa.get('titulo') else 0)
    if tapa.get('titulo'):
        filas.append(
            f'<tr><td style="padding:26px 28px 8px;">'
            f'<div style="font:700 30px/1.15 {SERIF};color:{TINTA};margin:0 0 10px;">{e(tapa["titulo"])}</div>'
            + p(e(tapa.get('bajada', '')), 18, GRIS, '0 0 14px', SERIF)
            + ''.join(p(e(x), 15, TINTA, '0 0 10px') for x in tapa.get('panorama', [])) + '</td></tr>')

    # 1b. Lecturas destacadas: los links que guardaste a mano (state/lecturas_semana.json).
    # Van arriba de todo, en caja resaltada. No pasan por Links(): la URL la pusiste vos, no el modelo.
    from lecturas import cargar_semana
    filas_lect = []
    lects = cargar_semana()
    if lects:
        items = []
        for x in lects:
            meta = ' · '.join(t for t in (x.get('autor'), x.get('publicado'),
                                          f'{x["minutos"]} min' if x.get('minutos') else None) if t)
            items.append(f'<div style="margin:0 0 14px;">'
                         f'<div style="font:700 18px/1.3 {SERIF};margin:0 0 4px;">{a(x.get("url"), x.get("titulo") or x.get("url"), TINTA)}</div>'
                         + p(e(x.get('resumen')), 15, TINTA, '0 0 4px')
                         + f'<div style="font:400 12px/1.4 {SANS};color:{GRIS};">{e(meta)}</div></div>')
        filas_lect.append(f'<tr><td style="padding:22px 28px 0;"><div style="background:#fff7e0;padding:18px 20px 6px;'
                          f'border:2px solid {ACENTO};">'
                          f'<div style="font:600 11px/1 {SANS};letter-spacing:.14em;text-transform:uppercase;color:{ACENTO};margin:0 0 6px;">Lo que guardaste</div>'
                          f'<div style="font:700 22px/1.25 {SERIF};color:{TINTA};margin:0 0 12px;">{e(con_emoji("Lecturas destacadas"))}</div>'
                          + ''.join(items) + '</div></td></tr>')
    else:
        vacias.append('lecturas')

    # 2. Lo que pasó, agrupado por sección temática (las secciones las elige la redacción)
    grupos = {}
    for i, it in enumerate(diario.get('lo_que_paso', []), 1):
        url = L(it.get('link'), f'lo_que_paso[{i}]')
        grupos.setdefault((it.get('seccion') or 'Otros').strip(), []).append(
            f'<div style="margin:0 0 18px;">{fuente_tag(it.get("fuente"))}'
            f'<div style="font:700 18px/1.3 {SERIF};color:{TINTA};margin:4px 0 4px;">{a(url, it["titulo"], TINTA)}</div>'
            + p(e(it.get('texto')), 15, TINTA, '0') + '</div>')
    secciones = sorted(grupos, key=lambda k: (ORDEN_SECCIONES.index(k) if k in ORDEN_SECCIONES
                                              else len(ORDEN_SECCIONES), list(grupos).index(k)))
    if secciones:
        intros = diario.get('secciones_intro') or {}
        for k in secciones:
            intro = (p(e(intros[k]), 16, TINTA, '0 0 16px', SERIF).replace('color:', 'font-style:italic;color:', 1)
                     if intros.get(k) else '')
            filas_sec.append(seccion(k, intro + ''.join(grupos[k]), 'La semana'))
    else:
        vacias.append('lo_que_paso')

    # 3. Opinión
    op = diario.get('opinion') or {}
    if op.get('parrafos'):
        cuerpo = (f'<div style="font:italic 700 20px/1.3 {SERIF};color:{TINTA};margin:0 0 12px;">{e(op.get("titulo"))}</div>'
                  + ''.join(p(e(x), 17, TINTA, '0 0 14px', SERIF) for x in op['parrafos'])
                  + p('Opinión de Claude, escrita a partir de tus newsletters. Discutila.', 12, GRIS, '4px 0 0'))
        filas_op.append(f'<tr><td style="padding:8px 28px 0;"><div style="background:{SUAVE};padding:22px 22px 10px;'
                     f'border-left:4px solid {ACENTO};">'
                     f'<div style="font:600 11px/1 {SANS};letter-spacing:.14em;text-transform:uppercase;color:{ACENTO};margin:0 0 8px;">✍️ Opinión</div>'
                     f'{cuerpo}</div></td></tr>')
    else:
        vacias.append('opinion')

    # 4. Cómo te afecta
    items = [f'<tr><td valign="top" style="padding:0 12px 14px 0;white-space:nowrap;font:700 12px/1.6 {SANS};'
             f'color:{ACENTO};text-transform:uppercase;letter-spacing:.06em;">{e(x.get("frente"))}</td>'
             f'<td valign="top" style="padding:0 0 14px;font:400 15px/1.55 {SANS};color:{TINTA};">{e(x.get("texto"))}</td></tr>'
             for x in diario.get('como_te_afecta', [])]
    if items:
        filas.append(seccion('Cómo te afecta', f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%">{"".join(items)}</table>', 'Para vos'))
    else:
        vacias.append('como_te_afecta')

    # 5. Números de la semana
    nums = []
    for i, n in enumerate(diario.get('numeros', []), 1):
        if not n.get('fuente'):
            L.malos.append({'id': '(sin fuente)', 'donde': f'numeros[{i}]'})
            continue
        url = L(n.get('link'), f'numeros[{i}]')
        nums.append(
            f'<td valign="top" width="50%" style="padding:0 8px 16px 0;">'
            f'<div style="font:700 28px/1.1 {SERIF};color:{ACENTO};">{e(n["cifra"])}</div>'
            f'<div style="font:400 14px/1.45 {SANS};color:{TINTA};margin:4px 0 2px;">{e(n.get("que"))}</div>'
            f'<div style="font:400 12px/1.4 {SANS};color:{GRIS};">{a(url, nombre.get(n["fuente"], n["fuente"]), GRIS)}</div></td>')
    if nums:
        grid = ''.join('<tr>' + ''.join(nums[k:k + 2]) + '</tr>' for k in range(0, len(nums), 2))
        filas_nums.append(seccion('Números de la semana', f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%">{grid}</table>'))
    else:
        vacias.append('numeros')
    # Índice del número (mismo orden que el EPUB del Kindle): lista las partes que existen
    partes = ([] if 'lecturas' in vacias else ['Lecturas destacadas'])
    partes += ([] if 'numeros' in vacias else ['Números de la semana'])
    partes += ([] if 'opinion' in vacias else ['Opinión']) + list(secciones if 'lo_que_paso' not in vacias else [])
    partes += [t for t, k in (('Cómo te afecta', 'como_te_afecta'), ('Dónde coinciden y dónde no', 'coinciden'),
                              ('Qué mirar en las próximas semanas', 'proximos'), ('Para leer completo', 'leer_completo')) if k not in vacias]
    partes.append('Por fuente')
    fila_indice = (f'<tr><td style="padding:14px 28px 0;font:400 13px/1.6 {SANS};color:{GRIS};">'
                   f'<b style="color:{TINTA};">En este número:</b> {e(" · ".join(con_emoji(t) for t in partes))}</td></tr>')
    # orden canónico (igual al EPUB): tapa, índice, números, opinión, qué pasó por sección, cómo te afecta, ...
    filas[idx_tras_tapa:idx_tras_tapa] = [fila_indice] + filas_lect + filas_nums + filas_op + filas_sec

    # 6. Dónde coinciden y dónde no
    co = diario.get('coinciden') or {}
    if co.get('versiones'):
        vs = []
        for i, v in enumerate(co['versiones'], 1):
            url = L(v.get('link'), f'coinciden[{i}]')
            vs.append(f'<div style="border-left:3px solid {LINEA};padding:2px 0 2px 12px;margin:0 0 12px;">'
                      f'{fuente_tag(v.get("fuente"))}'
                      + p(e(v.get('dice')), 15, TINTA, '4px 0 2px') + (p(a(url, 'leer →'), 13, GRIS, '0') if url else '')
                      + '</div>')
        filas.append(seccion('Dónde coinciden y dónde no',
                             f'<div style="font:700 17px/1.3 {SERIF};color:{TINTA};margin:0 0 8px;">{e(co.get("tema"))}</div>'
                             + p(e(co.get('texto')), 15) + ''.join(vs)))
    else:
        vacias.append('coinciden')

    # 7. Qué mirar en las próximas semanas (solo el mundo: la agenda personal no va acá)
    items = []
    for i, x in enumerate(diario.get('proximos', []), 1):
        url = L(x.get('link'), f'proximos[{i}]')
        items.append(f'<tr><td valign="top" style="padding:0 14px 12px 0;white-space:nowrap;font:700 14px/1.5 {SERIF};color:{ACENTO};">{e(x.get("cuando"))}</td>'
                     f'<td valign="top" style="padding:0 0 12px;font:400 15px/1.5 {SANS};color:{TINTA};">{a(url, x.get("que"), TINTA)} '
                     f'<span style="color:{GRIS};font-size:12px;">· {e(nombre.get(x.get("fuente"), x.get("fuente")))}</span></td></tr>')
    if items:
        filas.append(seccion('Qué mirar en las próximas semanas', f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%">{"".join(items)}</table>'))
    else:
        vacias.append('proximos')

    # 8. Para leer completo
    items = []
    for i, x in enumerate(diario.get('leer_completo', []), 1):
        url = L(x.get('link'), f'leer_completo[{i}]')
        mins = L.min.get((x.get('link') or '').strip())
        meta = nombre.get(x.get('fuente'), x.get('fuente')) + (f' · {mins} min' if mins else '')
        items.append(f'<div style="margin:0 0 16px;padding:14px 16px;border:1px solid {LINEA};background:#fff;">'
                     f'<div style="font:700 17px/1.3 {SERIF};margin:0 0 4px;">{a(url, x.get("titulo"), TINTA)}</div>'
                     + p(e(x.get('por_que')), 14, TINTA, '0 0 6px')
                     + f'<div style="font:400 12px/1 {SANS};color:{GRIS};">{e(meta)}</div></div>')
    if items:
        filas.append(seccion('Para leer completo', ''.join(items), 'Si tenés un rato'))
    else:
        vacias.append('leer_completo')

    # 9. Por fuente: ediciones con su versión web + destacados del destilado
    bloques = []
    orden = {'noticias': 0, 'tech-ai': 1, 'negocio': 2, 'ideas': 3}
    for f in sorted(con, key=lambda f: orden.get(f['tipo'], 9)):
        eds = ' · '.join(
            a(ed['web'] or ed['gmail'], f'{ed["asunto"][:70]}' + ('' if ed['web'] else ' (Gmail)'), GRIS)
            for ed in f['ediciones'])
        dest = []
        for i, d in enumerate((destilado.get(f['slug']) or {}).get('destacados', [])[:3], 1):
            url = L(d.get('link'), f'destacados.{f["slug"]}[{i}]')
            dest.append(f'<li style="margin:0 0 6px;font:400 14px/1.5 {SANS};color:{TINTA};">'
                        f'<b>{a(url, d.get("titulo"), TINTA)}</b>. {e(d.get("linea"))}</li>')
        bloques.append(
            f'<div style="margin:0 0 20px;padding:0 0 14px;border-bottom:1px solid {LINEA};">'
            f'<div style="font:700 16px/1.3 {SERIF};color:{TINTA};margin:0 0 6px;">{e(f["nombre"])} '
            f'<span style="font:400 12px {SANS};color:{GRIS};">· {len(f["ediciones"])} ediciones</span></div>'
            + (f'<ul style="margin:0 0 8px;padding-left:18px;">{"".join(dest)}</ul>' if dest else '')
            + f'<div style="font:400 12px/1.6 {SANS};color:{GRIS};">Versiones web: {eds}</div></div>')
    if bloques:
        filas.append(seccion('Por fuente', ''.join(bloques), 'Todo lo que llegó'))

    # 10. Pie
    pie = f'Fuentes leídas: {", ".join(f["nombre"] for f in con)}.'
    if sin:
        pie += f' Sin ediciones esta semana: {", ".join(f["nombre"] for f in sin)}.'
    filas.append(f'<tr><td style="padding:22px 28px 30px;border-top:1px solid {LINEA};">'
                 + p(e(pie), 12, GRIS, '0 0 6px')
                 + p(f'El diario del sábado · {hoy.isoformat()} · lo arma Claude con tus newsletters de la semana.', 12, GRIS, '0')
                 + '</td></tr>')

    cuerpo = (f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
              f'<meta name="viewport" content="width=device-width,initial-scale=1">'
              f'<meta name="color-scheme" content="light only">'
              f'<title>El diario del sábado · {hoy.isoformat()}</title></head>'
              f'<body style="margin:0;padding:0;background:{SUAVE};">'
              f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:{SUAVE};">'
              f'<tr><td align="center" style="padding:16px 8px;">'
              f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%" '
              f'style="max-width:640px;background:{PAPEL};border:1px solid {LINEA};">'
              + ''.join(filas) + '</table></td></tr></table></body></html>')

    (BASE / 'ediciones').mkdir(exist_ok=True)
    salida = BASE / 'ediciones' / f'{hoy.isoformat()}.html'
    salida.write_text(cuerpo)
    verif = {'archivo': str(salida.relative_to(BASE)), 'ediciones_leidas': n_ed,
             'fuentes_con_material': len(con), 'links_usados': len(L.usados),
             'ids_inexistentes': L.malos, 'secciones_vacias_omitidas': vacias,
             'bytes': len(cuerpo.encode())}
    (BASE / 'state' / 'verificacion.json').write_text(json.dumps(verif, ensure_ascii=False, indent=1))
    if verif['bytes'] > 98000:  # Gmail corta el mail arriba de ~102 KB y esconde el final
        verif['aviso'] = 'pesa más de 98 KB: Gmail puede recortarlo. Sacar ítems de «Por fuente».'
    print(json.dumps(verif, ensure_ascii=False))
    sys.exit(1 if L.malos else 0)


if __name__ == '__main__':
    main()
