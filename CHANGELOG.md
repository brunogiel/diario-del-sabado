# Changelog

## 1.0.1 · 2026-10-26

Arreglos que salieron de una revisión de privacidad, instalación desde cero y legibilidad.

- Los errores de Gmail ya no pasan callados: si `gws` responde un error (permiso vencido, API caída), el diario corta con el mensaje real en vez de decir «0 ediciones».
- Un `config.json` o `fuentes.json` incompleto da un mensaje claro en vez de un traceback. La zona horaria por defecto es la de tu máquina.
- La prueba en borrador del kickoff ya no bloquea el envío real de ese día, y cubre de verdad los últimos 7 días.
- El mail al Kindle ya no depende de `$TMPDIR` (que en cron suele estar vacío).
- La línea de `cron` del kickoff trae el PATH y los permisos completos.
- `install.sh` chequea Python 3.9+ y distingue «sin permiso» de «gws no respondió». `tests/smoke.py` avisa si falta Pillow.
- README: «En 3 pasos», cómo conectar Gmail (pantalla de consentimiento, `-s gmail`), privacidad más precisa, qué pasa en Linux.
- El filtro de pie de los newsletters ya no nombra fuentes puntuales.

## 1.0.0 · 2026-10-26

- Primera versión pública.
- Kickoff: escanea los encabezados de tu Gmail, detecta los newsletters que ya recibís y ofrece sumar los sugeridos del autor (opcional).
- Diario del sábado por mail (HTML) y, opcional, libro EPUB al Kindle.
- Tus datos viven en `~/.diario-del-sabado/`, fuera del repo.
- Prueba de humo sin Gmail: `tests/smoke.py`.
