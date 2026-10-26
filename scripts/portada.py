#!/usr/bin/env python3
"""
La portada del libro [DET]: diario clásico (papel crema, Didot, filetes) con la etiqueta
roja «HECHO CON IA PARA <NOMBRE>» y los 3 titulares de la tapa. La importa kindle.py.

Usa las fuentes de macOS (Didot, Avenir Next Condensed). En otro sistema cae a DejaVu
y, si tampoco está, a la fuente por defecto de Pillow: la portada sale igual, más simple.

Uso suelto (para mirarla): portada.py [YYYY-MM-DD] → ediciones/kindle/portada-prueba.png
"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1600, 2400
PAPEL, TINTA, ROJO, GRIS = (250, 246, 236), (22, 22, 22), (156, 43, 31), (100, 96, 90)
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']

# (archivo, índice dentro del .ttc) por estilo. Se usa el primero que exista.
SERIF = {0: [('/System/Library/Fonts/Supplemental/Didot.ttc', 0), ('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf', 0)],
         1: [('/System/Library/Fonts/Supplemental/Didot.ttc', 1), ('/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf', 0)],
         2: [('/System/Library/Fonts/Supplemental/Didot.ttc', 2), ('/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf', 0)]}
SANS = {2: [('/System/Library/Fonts/Avenir Next Condensed.ttc', 2), ('/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf', 0)],
        8: [('/System/Library/Fonts/Avenir Next Condensed.ttc', 8), ('/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf', 0)]}


def F(familia, size, estilo=0):
    for path, idx in familia.get(estilo, familia[min(familia)]):
        if Path(path).exists():
            return ImageFont.truetype(path, size, index=idx)
    return ImageFont.load_default(size)


def ancho(d, t, f):
    return d.textlength(t, font=f)


def centrado(d, t, y, f, c):
    d.text(((W - ancho(d, t, f)) / 2, y), t, font=f, fill=c)


def envolver(d, t, f, w):
    out, cur = [], ''
    for p in t.split():
        if ancho(d, (cur + ' ' + p).strip(), f) <= w:
            cur = (cur + ' ' + p).strip()
        else:
            out.append(cur)
            cur = p
    return out + [cur]


def rombo(d, cx, cy, r, c):
    d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=c)


def ajustar(d, t, familia, estilo, w, size):
    while size > 20 and ancho(d, t, F(familia, size, estilo)) > w:
        size -= 4
    return F(familia, size, estilo)


def masthead(d):
    """Filetes, masthead en dos renglones, filete doble."""
    d.rectangle([70, 70, W - 70, 86], fill=TINTA)
    d.rectangle([70, 100, W - 70, 106], fill=TINTA)
    f = ajustar(d, 'del Sábado', SERIF, 2, W - 240, 330)
    centrado(d, 'El Diario', 190, f, TINTA)
    centrado(d, 'del Sábado', 520, f, TINTA)
    d.rectangle([70, 930, W - 70, 936], fill=TINTA)
    d.rectangle([70, 948, W - 70, 954], fill=TINTA)


def cierre(d, tit, nro, fecha_txt, n_ed, n_f, y):
    for t in tit:
        d.rectangle([110, y + 22, 150, y + 62], fill=ROJO)
        f = F(SERIF, 90, 0)
        for l in envolver(d, t, f, W - 190 - 110):
            d.text((190, y), l, font=f, fill=TINTA)
            y += 104
        y += 30
    d.rectangle([70, H - 330, W - 70, H - 324], fill=TINTA)
    centrado(d, f'N.º {nro}  ·  {fecha_txt}', H - 290, F(SERIF, 60, 1), TINTA)
    centrado(d, f'{n_ed} newsletters · {n_f} fuentes · 1 libro', H - 205, F(SANS, 60, 2), ROJO)
    centrado(d, 'Armado por Claude cada sábado', H - 120, F(SERIF, 48, 1), GRIS)


def portada(tit, nro, fecha_txt, n_ed, n_f, nombre=''):
    """Sello rojo «HECHO CON IA PARA <NOMBRE>» + bajada. Sin nombre: «HECHO CON IA PARA VOS»."""
    im = Image.new('RGB', (W, H), PAPEL)
    d = ImageDraw.Draw(im)
    masthead(d)
    txt = f'HECHO CON IA PARA {(nombre or "vos").split()[0].upper()}'
    f = ajustar(d, txt, SANS, 8, W - 400, 62)
    w = ancho(d, txt, f) + 150
    x0 = (W - w) / 2
    d.rounded_rectangle([x0, 1000, x0 + w, 1112], radius=14, fill=ROJO)
    rombo(d, x0 + 52, 1056, 14, PAPEL)
    rombo(d, x0 + w - 52, 1056, 14, PAPEL)
    d.text((x0 + 75, 1019), txt, font=f, fill=PAPEL)
    f2 = F(SERIF, 66, 1)
    y = 1160
    for l in ['Lo que pasó en tus newsletters,', 'resumido y opinado por Claude']:
        centrado(d, l, y, f2, TINTA)
        y += 82
    cierre(d, tit, nro, fecha_txt, n_ed, n_f, y + 90)
    return im


def main():
    from comun import HOME, config
    eds = HOME / 'ediciones'
    hoy = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else \
        dt.date.fromisoformat(sorted(p.stem for p in eds.glob('*.html'))[-1])
    diario = json.loads((HOME / 'state' / 'diario.json').read_text())
    semana = json.loads((HOME / 'state' / 'semana.json').read_text())
    n_ed = sum(len(f['ediciones']) for f in semana['fuentes'])
    n_f = sum(1 for f in semana['fuentes'] if f['ediciones'])
    titulo = (diario.get('tapa') or {}).get('titulo', '')
    tit = [t[0].upper() + t[1:] for t in
           (x.strip() for x in re.split(r',\s+|\s+y\s+(?=[A-ZÁÉÍÓÚ])', titulo)) if t][:3]
    fecha_txt = f'{hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}'
    (eds / 'kindle').mkdir(parents=True, exist_ok=True)
    salida = eds / 'kindle' / 'portada-prueba.png'
    portada(tit, hoy.isocalendar()[1], fecha_txt, n_ed, n_f, config()['nombre']).save(salida, optimize=True)
    print(json.dumps({'portada': str(salida), 'titulares': tit}, ensure_ascii=False))


if __name__ == '__main__':
    main()
