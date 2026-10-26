#!/usr/bin/env python3
"""
Kickoff, paso 1 [DET]: escanea tu Gmail y lista los newsletters que ya te llegan.

Busca los mails de los últimos N días que traen un link para desuscribirse (bandeja y
archivados, sin los tuyos), lee SOLO los encabezados (remitente, asunto, List-Unsubscribe,
List-Id, categoría de Gmail, tamaño) y los agrupa por remitente. No baja cuerpos, no marca,
no archiva, no desuscribe. El resultado queda en tu máquina: DIARIO_HOME/state/escaneo.json.

El modelo después separa newsletters de contenido de promos y avisos transaccionales:
este script solo junta las señales.

Uso:
  escanear.py                 # últimos 30 días
  escanear.py --dias 60 --max 800

Salida (stdout, JSON corto): cuántos mails leyó, candidatos y qué sugeridos te llegan.
"""
import argparse
import collections
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from email.utils import parseaddr

from comun import HOME, SKILL, gws_json

QUERY = ('-from:me (unsubscribe OR desuscribir OR desuscribirte OR "darte de baja" OR "darse de baja" '
         'OR "cancelar suscripción" OR "view in browser" OR "ver en el navegador")')
PLATAFORMAS = {'substack': 'Substack', 'beehiiv': 'beehiiv', 'mailchimp': 'Mailchimp', 'mcsv.net': 'Mailchimp',
               'list-manage': 'Mailchimp', 'convertkit': 'Kit', 'kit.com': 'Kit', 'ghost': 'Ghost',
               'buttondown': 'Buttondown', 'mailerlite': 'MailerLite', 'sendgrid': 'SendGrid',
               'campaign-archive': 'Mailchimp'}
# Dominios compartidos por muchos autores: ahí se agrupa por mail exacto, nunca por dominio.
COMPARTIDOS = ('substack.com', 'beehiiv.com', 'gmail.com', 'ghost.io', 'mail.beehiiv.com', 'convertkit.com')


def coincide(remitente, patrones):
    remitente = (remitente or '').lower()
    return any(remitente.endswith(p.lower()) if p.startswith('@') else remitente == p.lower()
               for p in patrones)


def listar(dias, tope):
    ids, token = [], None
    while len(ids) < tope:
        params = {'userId': 'me', 'q': f'newer_than:{dias}d {QUERY}', 'maxResults': min(500, tope - len(ids))}
        if token:
            params['pageToken'] = token
        try:
            res = gws_json(['gmail', 'users', 'messages', 'list', '--params', json.dumps(params), '--format', 'json'])
        except RuntimeError as e:
            sys.exit(f'✗ No pude buscar en Gmail: {e}')
        ids += [m['id'] for m in res.get('messages', [])]
        token = res.get('nextPageToken')
        if not token:
            break
    return ids


def encabezados(mid):
    try:
        m = gws_json(['gmail', 'users', 'messages', 'get', '--params', json.dumps({
            'userId': 'me', 'id': mid, 'format': 'metadata',
            'metadataHeaders': ['From', 'Subject', 'List-Unsubscribe', 'List-Id']}), '--format', 'json'])
    except Exception as e:
        return {'error': str(e)[:120]}
    h = {x['name'].lower(): x['value'] for x in m.get('payload', {}).get('headers', [])}
    nombre, email = parseaddr(h.get('from', ''))
    return {'email': email.lower(), 'nombre': nombre, 'asunto': h.get('subject', ''),
            'unsub': h.get('list-unsubscribe', ''), 'list_id': h.get('list-id', ''),
            'labels': m.get('labelIds') or [], 'kb': (m.get('sizeEstimate') or 0) // 1024,
            'fecha': int(m.get('internalDate') or 0)}


def plataforma(*textos):
    t = ' '.join(textos).lower()
    return next((v for k, v in PLATAFORMAS.items() if k in t), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dias', type=int, default=30)
    ap.add_argument('--max', type=int, default=600)
    a = ap.parse_args()

    ids = listar(a.dias, a.max)
    with ThreadPoolExecutor(8) as ex:
        mails = [m for m in ex.map(encabezados, ids) if m.get('email')]

    sugeridos = json.loads((SKILL / 'sugeridos.json').read_text())['fuentes']
    actuales = []
    if (HOME / 'fuentes.json').exists():
        actuales = json.loads((HOME / 'fuentes.json').read_text())['fuentes']

    grupos = collections.defaultdict(list)
    for m in mails:
        grupos[m['email']].append(m)

    candidatos = []
    for email, ms in grupos.items():
        ms.sort(key=lambda m: m['fecha'], reverse=True)
        dominio = email.split('@')[-1]
        cats = collections.Counter(l for m in ms for l in m['labels'] if l.startswith('CATEGORY_'))
        sug = next((s['slug'] for s in sugeridos if coincide(email, s['remitentes'])), None)
        if len(ms) < 2 and not sug:
            continue
        candidatos.append({
            'email': email,
            'nombre': ms[0]['nombre'] or email,
            'dominio': dominio,
            'dominio_compartido': any(dominio == d or dominio.endswith('.' + d) for d in COMPARTIDOS),
            'cantidad': len(ms),
            'por_semana': round(len(ms) / (a.dias / 7), 1),
            'asuntos': [m['asunto'][:90] for m in ms[:4]],
            'list_unsubscribe': any(m['unsub'] for m in ms),
            'list_id': ms[0]['list_id'][:80],
            'categoria_gmail': (cats.most_common(1)[0][0].replace('CATEGORY_', '').lower() if cats else None),
            'kb_promedio': round(sum(m['kb'] for m in ms) / len(ms)),
            'plataforma': plataforma(email, ms[0]['list_id'], ms[0]['unsub'][:200]),
            'sugerido': sug,
            'ya_en_fuentes': any(coincide(email, f.get('remitentes', [])) for f in actuales),
        })
    candidatos.sort(key=lambda c: (-c['cantidad'], c['email']))

    llegan = {c['sugerido'] for c in candidatos if c['sugerido']}
    resumen_sug = [{'slug': s['slug'], 'nombre': s['nombre'], 'te_llega': s['slug'] in llegan,
                    'suscribirse': s.get('suscribirse')} for s in sugeridos]

    (HOME / 'state').mkdir(parents=True, exist_ok=True)
    salida = HOME / 'state' / 'escaneo.json'
    salida.write_text(json.dumps({'dias': a.dias, 'mails_leidos': len(mails), 'candidatos': candidatos,
                                  'sugeridos': resumen_sug}, ensure_ascii=False, indent=1))
    print(json.dumps({'archivo': str(salida), 'dias': a.dias, 'mails_leidos': len(mails),
                      'tope_alcanzado': len(ids) >= a.max, 'candidatos': len(candidatos),
                      'sugeridos_que_te_llegan': sorted(llegan)}, ensure_ascii=False))
    if not mails:
        print('⚠ No leí ningún mail: revisá que `gws auth login` esté hecho con tu cuenta de Gmail.', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
