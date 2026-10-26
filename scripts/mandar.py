#!/usr/bin/env python3
"""
Manda el diario [DET] con `gws gmail +send` y después confirma que quedó en SENT.

El cuerpo va por archivo, no interpolado en un comando: con comillas, $ o
backticks adentro, interpolar rompe el mail en silencio.

Uso:
  mandar.py --to vos@mail.com --subject "Asunto" --body-file ediciones/2026-10-24.html --html --enviar
  mandar.py --to x@kindle.com --subject "Newsletter ..." --body-file cuerpo.txt -a libro.epub --enviar
  Sin --enviar queda en BORRADOR (sirve para la primera prueba).
"""
import argparse
import json
import os
import sys

from comun import gws_json

MAX_ADJUNTO_MB = 15  # Gmail corta a 25 MB y el base64 infla ~33%


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--to', required=True)
    ap.add_argument('--subject', required=True)
    ap.add_argument('--body-file', required=True)
    ap.add_argument('--html', action='store_true')
    ap.add_argument('-a', '--attach', action='append', default=[])
    ap.add_argument('--enviar', action='store_true', help='sin esto queda en borrador')
    a = ap.parse_args()

    cuerpo = open(a.body_file, encoding='utf-8').read()
    for adj in a.attach:
        mb = os.path.getsize(adj) / 1024 / 1024
        if mb > MAX_ADJUNTO_MB:
            sys.exit(f'{os.path.basename(adj)} pesa {mb:.1f} MB: más de {MAX_ADJUNTO_MB} MB no entra en Gmail')

    cmd = ['gmail', '+send', '--to', a.to, '--subject', a.subject, '--body', cuerpo]
    for adj in a.attach:
        cmd += ['-a', adj]
    if a.html:
        cmd += ['--html']
    if not a.enviar:
        cmd += ['--draft']
    try:
        res = gws_json(cmd + ['--format', 'json'])
    except RuntimeError as e:
        sys.exit(f'✗ No se mandó: {e}')
    mid = res.get('message', {}).get('id') or res.get('id', '')
    if not mid:
        sys.exit(f'✗ gws no devolvió un id de mensaje: {json.dumps(res)[:300]}')

    problemas = []
    if a.enviar:
        try:
            m = gws_json(['gmail', 'users', 'messages', 'get', '--params',
                          json.dumps({'userId': 'me', 'id': mid, 'format': 'minimal'}), '--format', 'json'])
            if 'SENT' not in (m.get('labelIds') or []):
                problemas.append('el mensaje no aparece en SENT: el envío no se confirmó')
        except Exception as e:
            problemas.append(f'no pude leer el mensaje de vuelta: {e}')

    print(json.dumps({'estado': 'enviado' if a.enviar else 'borrador', 'message_id': mid,
                      'problemas': problemas}, ensure_ascii=False, indent=1))
    sys.exit(2 if problemas else 0)


if __name__ == '__main__':
    main()
