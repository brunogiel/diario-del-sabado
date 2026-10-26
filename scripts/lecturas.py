#!/usr/bin/env python3
"""
Lecturas destacadas del diario del sábado: los links que guardás a mano en la semana.

La cola es state/lecturas.json (lista "lecturas"; cada una: url, titulo, autor,
publicado, agregado, resumen, consumido = null | "YYYY-MM-DD").

Uso:
  lecturas.py agregar URL [--titulo T] [--autor A] [--resumen R]   # guarda un link para el sábado
  lecturas.py juntar     # paso 2b [DET]: baja el texto de las pendientes →
                         #   state/lecturas_semana.json + state/completo/lectura-<n>.txt
  lecturas.py consumir   # después de mandar el diario: marca consumidas las que salieron
  lecturas.py consumir --fecha 2026-10-17

Si una página no baja, la lectura igual sale (título, autor, resumen y link) y
queda anotado 'error'. Nunca falla la corrida: el diario no depende de esto.
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

from comun import HOME as BASE

COLA = BASE / 'state' / 'lecturas.json'
SEMANA = BASE / 'state' / 'lecturas_semana.json'
PALABRAS_POR_MIN = 230


def a_texto(crudo: str) -> str:
    m = re.search(r'<article[^>]*>(.*?)</article>', crudo, re.S | re.I) or \
        re.search(r'<main[^>]*>(.*?)</main>', crudo, re.S | re.I)
    t = m.group(1) if m else crudo
    t = re.sub(r'<(script|style|head|nav|footer|header|svg)[^>]*>.*?</\1>', ' ', t, flags=re.S | re.I)
    t = re.sub(r'<h[1-6][^>]*>', '\n** ', t, flags=re.I)        # subtítulo (kindle.py lo pone en negrita)
    t = re.sub(r'<(br|/p|/div|/li|/h\d|/blockquote|/pre)[^>]*>', '\n', t, flags=re.I)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', t))
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n\s*\n+', '\n\n', t)
    return '\n'.join(l.strip() for l in t.splitlines()).strip()


def bajar(url: str) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (diario del sabado)'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode(r.headers.get_content_charset() or 'utf-8', 'replace')


def cola():
    return json.loads(COLA.read_text()) if COLA.exists() else {'lecturas': []}


def juntar():
    pend = [x for x in cola()['lecturas'] if not x.get('consumido')]
    (BASE / 'state' / 'completo').mkdir(parents=True, exist_ok=True)
    salida = []
    for n, x in enumerate(pend, 1):
        it = {k: x.get(k) for k in ('url', 'titulo', 'autor', 'publicado', 'agregado', 'resumen')}
        it['n'] = n
        try:
            texto = a_texto(bajar(x['url']))
            (BASE / 'state' / 'completo' / f'lectura-{n}.txt').write_text(texto)
            it['minutos'] = max(1, round(len(texto.split()) / PALABRAS_POR_MIN))
        except Exception as e:  # una página caída no frena el diario
            it['error'] = str(e)[:200]
        salida.append(it)
    SEMANA.write_text(json.dumps({'lecturas': salida}, ensure_ascii=False, indent=1))
    print(json.dumps({'lecturas': len(salida), 'errores': [i['url'] for i in salida if i.get('error')]},
                     ensure_ascii=False))


def consumir(fecha: str):
    if not SEMANA.exists():
        print(json.dumps({'consumidas': 0}))
        return
    salieron = {x['url'] for x in json.loads(SEMANA.read_text())['lecturas']}
    c = cola()
    n = 0
    for x in c['lecturas']:
        if x['url'] in salieron and not x.get('consumido'):
            x['consumido'] = fecha
            n += 1
    COLA.write_text(json.dumps(c, ensure_ascii=False, indent=1))
    print(json.dumps({'consumidas': n, 'fecha': fecha}))


def agregar(url: str, titulo=None, autor=None, resumen=None):
    c = cola()
    if any(x['url'] == url and not x.get('consumido') for x in c['lecturas']):
        print(json.dumps({'agregada': False, 'motivo': 'ya estaba en la cola'}, ensure_ascii=False))
        return
    if not titulo:
        try:
            m = re.search(r'<title[^>]*>(.*?)</title>', bajar(url), re.S | re.I)
            titulo = html.unescape(m.group(1)).strip() if m else None
        except Exception:
            pass
    c['lecturas'].append({'url': url, 'titulo': titulo or url, 'autor': autor, 'publicado': None,
                          'agregado': dt.date.today().isoformat(), 'resumen': resumen, 'consumido': None})
    COLA.parent.mkdir(parents=True, exist_ok=True)
    COLA.write_text(json.dumps(c, ensure_ascii=False, indent=1))
    print(json.dumps({'agregada': True, 'titulo': titulo or url,
                      'pendientes': sum(1 for x in c['lecturas'] if not x.get('consumido'))}, ensure_ascii=False))


def cargar_semana():
    """Para armar.py y kindle.py: las lecturas de esta corrida ([] si no hay)."""
    try:
        return json.loads(SEMANA.read_text())['lecturas']
    except Exception:
        return []


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('accion', choices=['agregar', 'juntar', 'consumir'])
    ap.add_argument('url', nargs='?')
    ap.add_argument('--titulo')
    ap.add_argument('--autor')
    ap.add_argument('--resumen')
    ap.add_argument('--fecha', default=dt.date.today().isoformat())
    a = ap.parse_args()
    if a.accion == 'agregar':
        if not a.url:
            ap.error('agregar necesita la URL')
        agregar(a.url, a.titulo, a.autor, a.resumen)
    else:
        juntar() if a.accion == 'juntar' else consumir(a.fecha)
