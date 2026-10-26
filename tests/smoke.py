#!/usr/bin/env python3
"""
Prueba de humo sin Gmail: arma una semana inventada en una carpeta temporal y corre
armar.py y kindle.py contra ella. Sirve para ver que el diario se arma en tu máquina
antes de conectar nada.

Uso: python3 tests/smoke.py [--guardar CARPETA]   # con --guardar deja el HTML y el EPUB ahí
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

SEMANA = {
    'desde': '2026-10-17T00:00:00-03:00', 'hasta': '2026-10-24T09:30:00-03:00', 'generado': '2026-10-24T09:30:00-03:00',
    'fuentes': [
        {'slug': 'mundo', 'nombre': 'Diario Mundo', 'idioma': 'es', 'tipo': 'noticias', 'ediciones': [
            {'n': 1, 'message_id': 'a1', 'thread_id': 'a1', 'asunto': 'La cumbre del clima cierra sin acuerdo',
             'fecha': 'Mon, 19 Oct 2026 07:00:00 +0000', 'gmail': 'https://mail.google.com/mail/u/0/#all/a1',
             'web': 'https://example.com/mundo/1', 'minutos': 6,
             'links': [{'texto': 'La cumbre, en detalle', 'url': 'https://example.com/mundo/cumbre', 'id': 'mundo:1:1'}]}]},
        {'slug': 'techie', 'nombre': 'Techie Weekly', 'idioma': 'en', 'tipo': 'tech-ai', 'ediciones': [
            {'n': 1, 'message_id': 'b1', 'thread_id': 'b1', 'asunto': 'A new open model tops the charts',
             'fecha': 'Wed, 21 Oct 2026 12:00:00 +0000', 'gmail': 'https://mail.google.com/mail/u/0/#all/b1',
             'web': None, 'minutos': 4,
             'links': [{'texto': 'Benchmark results', 'url': 'https://example.com/tech/bench', 'id': 'techie:1:1'}]}]},
        {'slug': 'vacio', 'nombre': 'Newsletter Callado', 'idioma': 'en', 'tipo': 'ideas', 'ediciones': []},
    ]}

DESTILADO = {
    'mundo': {'fuente': 'mundo', 'hechos': [{'titulo': 'Cumbre sin acuerdo', 'resumen': 'Cerró sin metas nuevas. Pesa en 2027.', 'importancia': 3, 'link': 'mundo:1:1'}],
              'cifras': [{'cifra': '1,5 °C', 'que': 'el tope que nadie quiso firmar', 'link': 'mundo:1:1'}],
              'proximos': [{'cuando': 'mar 3/11', 'que': 'vuelve la negociación', 'link': 'mundo:1:web'}],
              'largas': [{'titulo': 'La cumbre, en detalle', 'por_que': 'explica quién frenó', 'link': 'mundo:1:web'}],
              'destacados': [{'titulo': 'Cumbre sin acuerdo', 'linea': 'Cerró sin metas.', 'link': 'mundo:1:1'}] * 3},
    'techie': {'fuente': 'techie', 'hechos': [{'titulo': 'Un modelo abierto lidera', 'resumen': 'Supera a los cerrados en dos pruebas. Baja precios.', 'importancia': 2, 'link': 'techie:1:1'}],
               'cifras': [{'cifra': '92%', 'que': 'el puntaje en la prueba principal', 'link': 'techie:1:1'}],
               'proximos': [], 'largas': [],
               'destacados': [{'titulo': 'Modelo abierto', 'linea': 'Lidera dos pruebas.', 'link': 'techie:1:1'}] * 3},
}

DIARIO = {
    'tapa': {'titulo': 'La cumbre se cae, un modelo abierto sube y el mundo mira', 'bajada': 'Clima, AI y precios.',
             'panorama': ['Mundo. La cumbre cerró sin acuerdo.', 'AI y ciencia. Un modelo abierto lidera.',
                          'Negocios. Bajan los precios de API.', 'Ideas. Semana tranquila.']},
    'secciones_intro': {'Internacional': 'Una semana de frenos.', 'AI': 'Lo abierto empuja.'},
    'lo_que_paso': [
        {'seccion': 'Internacional', 'titulo': 'La cumbre del clima cierra sin acuerdo', 'texto': 'No hubo metas nuevas. Vuelve en noviembre.', 'fuente': 'mundo', 'link': 'mundo:1:1'},
        {'seccion': 'AI', 'titulo': 'Un modelo abierto lidera dos pruebas', 'texto': 'Supera a los cerrados. Baja precios.', 'fuente': 'techie', 'link': 'techie:1:1'},
        {'seccion': 'AI', 'titulo': 'Un id inventado no se publica', 'texto': 'Este link no existe.', 'fuente': 'techie', 'link': 'techie:9:9'},
    ],
    'opinion': {'titulo': 'Lo abierto gana por precio', 'parrafos': ['Párrafo uno.', 'Párrafo dos.']},
    'como_te_afecta': [{'frente': 'Trabajo', 'texto': 'Tus costos de API pueden bajar.'}],
    'numeros': [{'cifra': '92%', 'que': 'puntaje del modelo abierto', 'fuente': 'techie', 'link': 'techie:1:1'}],
    'coinciden': {'tema': 'La cumbre', 'texto': 'Solo una fuente la cubrió.', 'versiones': [{'fuente': 'mundo', 'dice': 'Fracasó.', 'link': 'mundo:1:1'}]},
    'proximos': [{'cuando': 'mar 3/11', 'que': 'vuelve la negociación', 'fuente': 'mundo', 'link': 'mundo:1:web'}],
    'leer_completo': [{'titulo': 'La cumbre, en detalle', 'por_que': 'explica quién frenó', 'fuente': 'mundo', 'link': 'mundo:1:web'}],
}


def correr(script, home, *args):
    r = subprocess.run([sys.executable, str(RAIZ / 'scripts' / script), *args], capture_output=True, text=True,
                       env={**os.environ, 'DIARIO_HOME': str(home)})
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def main():
    try:
        import PIL  # noqa: F401  (kindle.py arma la portada con Pillow)
    except ImportError:
        sys.exit('✗ Falta Pillow: python3 -m pip install --user Pillow (o en un venv) y volvé a correr.')
    guardar = Path(sys.argv[sys.argv.index('--guardar') + 1]) if '--guardar' in sys.argv else None
    fallas = []
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        (home / 'state' / 'destilado').mkdir(parents=True)
        (home / 'state' / 'completo').mkdir(parents=True)
        (home / 'config.json').write_text(json.dumps({'nombre': 'Ana', 'secciones': [
            {'nombre': 'Internacional', 'emoji': '🌍'}, {'nombre': 'AI', 'emoji': '🤖'}]}))
        (home / 'state' / 'semana.json').write_text(json.dumps(SEMANA))
        (home / 'state' / 'diario.json').write_text(json.dumps(DIARIO))
        for slug, d in DESTILADO.items():
            (home / 'state' / 'destilado' / f'{slug}.json').write_text(json.dumps(d))
        (home / 'state' / 'completo' / 'mundo-1.txt').write_text('La cumbre terminó sin acuerdo.\n\nOtro párrafo.')
        (home / 'state' / 'completo' / 'techie-1.txt').write_text('A new open model tops two benchmarks.')

        code, out, err = correr('armar.py', home, '--fecha', '2026-10-24')
        verif = json.loads(out) if out.startswith('{') else {}
        html = (home / 'ediciones' / '2026-10-24.html')
        if code != 1 or [x['id'] for x in verif.get('ids_inexistentes', [])] != ['techie:9:9']:
            fallas.append(f'armar.py debía cazar el id inventado y salir con 1: code={code} {out} {err[-300:]}')
        if not html.exists() or 'Diario Mundo' not in html.read_text() or 'example.com/mundo/cumbre' not in html.read_text():
            fallas.append('el HTML no trae la fuente o el link real')
        if html.exists() and 'techie:9:9' in html.read_text():
            fallas.append('el id inventado llegó al HTML')

        if shutil.which('pandoc'):
            code, out, err = correr('kindle.py', home, '2026-10-24')
            if code != 0:
                fallas.append(f'kindle.py falló: {err[-400:]}')
            else:
                epub = Path(json.loads(out)['epub'])
                with zipfile.ZipFile(epub) as z:
                    if z.namelist()[0] != 'mimetype':
                        fallas.append('el EPUB no arranca con mimetype')
                    if 'linear="no"' not in z.read('EPUB/content.opf').decode():
                        fallas.append('la portada no quedó fuera de la lectura')
                if guardar:
                    guardar.mkdir(parents=True, exist_ok=True)
                    shutil.copy(epub, guardar)
        else:
            print('· pandoc no está: salteo el EPUB')
        if guardar and html.exists():
            guardar.mkdir(parents=True, exist_ok=True)
            shutil.copy(html, guardar)

    if fallas:
        print('❌ ' + '\n❌ '.join(fallas))
        sys.exit(1)
    print('✅ el diario se arma: HTML sin ids inventados' + (' + EPUB' if shutil.which('pandoc') else ''))


if __name__ == '__main__':
    main()
