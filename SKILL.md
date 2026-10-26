---
name: diario-del-sabado
description: >
  Cada sábado lee todos los newsletters de la semana del usuario (estén en la bandeja o archivados) y
  le manda por mail «El diario del sábado»: un HTML con lo que pasó por sección, una nota de opinión,
  cómo lo afecta, números, dónde las fuentes no coinciden, qué mirar la semana que viene, qué leer
  completo y los destacados de cada fuente. Opcional: el mismo diario como libro EPUB al Kindle.
  La primera vez corre un kickoff que escanea el Gmail, detecta los newsletters que ya recibe y
  ofrece sumar los sugeridos del autor. Usalo con «armame el diario», «el diario del sábado»,
  «qué dijeron mis newsletters esta semana», «configurá el diario», «cambiá mis newsletters»,
  «guardá este link para el diario».
---

# El diario del sábado

Lee los newsletters de la semana y arma un diario personal. Solo **lee** mails: no marca, no
archiva, no desuscribe.

- `SKILL` = la carpeta de este archivo (código).
- `DIARIO_HOME` = tus datos, por defecto `~/.diario-del-sabado/` (ver `scripts/comun.py`).
  Todas las rutas de `state/`, `ediciones/`, `config.json`, `fuentes.json` y `perfil.md` son relativas a `DIARIO_HOME`.
- **Al arrancar, fijá las dos rutas en cada comando de Bash** (no quedan exportadas entre llamadas):
  `SKILL="<ruta absoluta de esta carpeta>"; DIARIO_HOME="${DIARIO_HOME:-$HOME/.diario-del-sabado}"`.
- `[DET]` = lo hace un script, siempre igual. `[LATENT]` = lo hace el modelo, con criterio.

## Antes de nada: ¿hay kickoff?

Si **no existe** `DIARIO_HOME/config.json`, o el usuario pide «configurá el diario» / «cambiá mis
newsletters» / «volvé a escanear», leer [`kickoff.md`](kickoff.md) y seguirlo. No correr el diario
sin configuración.

Si el usuario pide **«guardá este link para el diario»**: `python3 "$SKILL/scripts/lecturas.py" agregar URL`
y listo. El sábado sale en «Lecturas destacadas».

## Archivos

| Archivo | Para qué |
|---|---|
| `DIARIO_HOME/fuentes.json` | Qué newsletters entran. Sumar una = sumar un objeto. `"activa": false` la apaga sin borrarla |
| `DIARIO_HOME/config.json` | Nombre, mail de destino, Kindle, zona horaria, secciones y áreas del panorama |
| `DIARIO_HOME/perfil.md` | Lo que «Cómo te afecta» necesita saber del lector |
| `DIARIO_HOME/state/lecturas.json` | Cola de links que el usuario guardó a mano en la semana |
| `SKILL/prompts/destilar.md` | El prompt del paso 3 (un Haiku por fuente) |
| `SKILL/scripts/juntar.py` | Paso 2 [DET]: Gmail → `state/semana.json` + `state/fuentes/<slug>.txt` + `state/completo/<slug>-<n>.txt` |
| `SKILL/scripts/armar.py` | Paso 5 [DET]: JSON → `ediciones/YYYY-MM-DD.html` + verificación de links |
| `SKILL/scripts/kindle.py` | Paso 6b [DET]: arma el EPUB desde los datos → `ediciones/kindle/<título>.epub` |
| `SKILL/scripts/mandar.py` | Pasos 6 y 6b [DET]: manda con `gws` y confirma que quedó en SENT |
| `SKILL/scripts/escanear.py` | Kickoff [DET]: detecta los newsletters que ya te llegan |

## Flujo

Corre **sábados** (sugerido 9:30). Cubre del sábado anterior 00:00 a la hora de la corrida.

1. **[DET] Chequear doble envío.** Si la fecha de hoy ya está en `state/enviados.txt`, cortar y loggear `ya_enviado`.

2. **[DET] Juntar.** `python3 "$SKILL/scripts/juntar.py"`. Imprime un JSON con ediciones por fuente.
   - Al final corre solo `lecturas.py juntar`. Una página que no baja sale igual con título y link.
   - Si `ediciones` = 0: algo anda mal con `gws` o con Gmail. No mandar un diario vacío: mandar un mail corto al usuario avisando y cortar.
   - Si `gws` tira `invalid_grant`: el token venció. El usuario corre `gws auth login`. Avisar y cortar.

3. **[LATENT · Haiku] Destilar por fuente.** Borrar `state/destilado/*.json` viejos. Para cada archivo de `state/fuentes/`, lanzar **un subagente Haiku** (`Agent`, `model: haiku`, todos en el mismo mensaje, en paralelo) con este prompt:
   > Leé `{SKILL}/prompts/destilar.md` y seguí sus instrucciones al pie de la letra con SLUG={slug} y BASE="{DIARIO_HOME absoluto}". Solo leés ese archivo de fuente y escribís el JSON de salida; no toques nada más.

   Al volver, validar que cada `state/destilado/<slug>.json` exista y sea JSON válido. Si uno falta, relanzar ese solo una vez. Si vuelve a fallar, seguir sin esa fuente y anotarlo.

4. **[LATENT · este hilo] Redactar.** Leer todos los `state/destilado/*.json`, `perfil.md` y `config.json`. Escribir `state/diario.json` con el esquema del docstring de `scripts/armar.py`:
   - **tapa**: una **mezcla de áreas**, no solo el tema más grande. `titulo` junta 2-3 cosas de áreas distintas, `bajada` nombra 5-6 y `panorama` es una lista de 4 párrafos cortos que empiezan con cada área de `config.panorama` en una palabra («Mundo.», «AI y ciencia.»). Es lo primero que se lee: tiene que dar el panorama completo.
   - **secciones_intro**: `{sección: 2 frases}`. Abre cada sección con qué tienen en común sus hechos y qué pesa más. Una sola noticia = 1 frase corta.
   - **lo_que_paso**: 12 a 20 hechos **agrupados por sección** (campo `seccion`), usando los nombres de `config.secciones` en ese orden. Solo las que tengan material (2 a 5 hechos cada una). Si un tema fuerte no entra, se crea una sección nueva con nombre corto (va al final). Priorizar `importancia` 3 y lo que aparece en más de una fuente. 2 frases cada uno.
   - **opinion**: 250 a 350 palabras sobre el tema más fuerte. Una tesis clara, con disidencia si hace falta. No es un resumen: es un argumento. Tono de columnista.
   - **como_te_afecta**: 3-4 puntos según `perfil.md`. Concreto: qué cambia para el lector en cada frente. Sin consejos de inversión.
   - **numeros**: 4 a 6 cifras **copiadas** del campo `cifras` de los destilados, cada una con `fuente` y `link`.
   - **coinciden**: un tema que dos o más fuentes cuentan distinto. Si ninguna se pisa, un tema que solo una fuente vio.
   - **proximos**: lo que viene en el mundo (nunca la agenda personal), de los `proximos` de los destilados, ordenado por fecha.
   - **leer_completo**: 3 piezas de los `largas`. Preferir ids `:web` (dan los minutos de lectura).
   - **Links**: solo ids que aparezcan en los destilados. Nunca una URL.
   - Idioma de `config.idioma` (default español), frases cortas.
   - **Verificar antes de escribir**: todo hecho que va a la tapa, la opinión o los números se chequea contra `state/fuentes/<slug>.txt`. Haiku a veces deforma hechos (ver Gotchas).

5. **[DET] Armar y verificar.** `python3 "$SKILL/scripts/armar.py"`. Si sale con código 1, hay ids inexistentes en `state/verificacion.json`: corregirlos en `diario.json` con un id real del destilado y volver a correr. Máximo 2 vueltas; si persisten, el ítem sale sin link (armar.py ya lo hace) y se anota.

6. **[DET] Mandar.**
   ```bash
   python3 "$SKILL/scripts/mandar.py" \
     --to "<config.email>" \
     --subject "El diario del sábado · DD/MM: <titular de tapa, corto>" \
     --body-file "$DIARIO_HOME/ediciones/YYYY-MM-DD.html" \
     --html --enviar
   ```
   Sin `--enviar` queda en borrador (así corre la prueba del kickoff). Si `problemas` no viene vacío, anotarlo.
   **Solo si salió con `--enviar`**: agregar una línea `YYYY-MM-DD` a `state/enviados.txt` (un borrador no cuenta: si no, bloquearía el envío real de ese día).
   Recién con el mail enviado OK: `python3 "$SKILL/scripts/lecturas.py" consumir` (si el mail falló, no correrlo: las lecturas quedan para el sábado siguiente).

6b. **[DET] Kindle (solo si `config.kindle` tiene una dirección).** `python3 "$SKILL/scripts/kindle.py"` arma el EPUB e imprime el título exacto. Después:
   ```bash
   echo "<título>." > "$DIARIO_HOME/state/kindle-body.txt"
   python3 "$SKILL/scripts/mandar.py" --to "<config.kindle>" --subject "<título>" \
     --body-file "$DIARIO_HOME/state/kindle-body.txt" -a "$DIARIO_HOME/ediciones/kindle/<título>.epub" --enviar
   ```
   Si el Kindle falla, el diario por mail ya salió: anotarlo y seguir.

7. **[DET] Loggear.** Escribir `state/last_run.json` y sumar una línea a `state/runs.jsonl`:
   `{fecha, pasos[{nombre, ok, detalle}], ediciones, fuentes, fuentes_sin_material, links_usados, ids_inexistentes, message_id, timing_s}`.

## Formato

El mail y el libro llevan el mismo contenido, en este orden:

| # | Parte | Mail (HTML) | Libro (EPUB) |
|---|---|---|---|
| 1 | Índice | línea «En este número» | el índice nativo del lector; el libro abre ahí |
| 1b | Lecturas destacadas (si hay) | caja «Lo que guardaste» | capítulo con el texto entero |
| 2 | Tapa | titular + bajada + 4 párrafos de panorama | igual, va después de los números |
| 3 | Números de la semana | grilla de cifras con fuente y link | igual, va primero |
| 4 | Opinión | 250-350 palabras | igual |
| 5 | Qué pasó | una parte por sección, con intro de 2 frases | igual |
| 6 | Cómo te afecta | 3-4 puntos por frente | igual |
| 7 | Dónde coinciden y dónde no | tema + versiones por fuente | igual |
| 8 | Qué mirar en las próximas semanas | fechas del mundo | igual |
| 9 | Para leer completo | 3 piezas con minutos | igual |
| 10 | Por fuente | destacados + versiones web | los newsletters enteros, sin boilerplate |

Reglas: un solo link por hecho (el titular). El libro va sin emojis en los títulos (`kindle.py --con-emoji` los pone). Título del libro: «Newsletter {primera…quinta} semana de {mes}».

## Success metrics

- 0 ids inventados en el mail final (`verificacion.json`).
- Cada fuente con ediciones aparece en «Por fuente».
- Cada número tiene fuente y link.
- La opinión toma posición y tiene entre 250 y 350 palabras.
- «Cómo te afecta» nombra un frente real de `perfil.md` en cada punto.

## Gotchas

- **Muchos newsletters se archivan solos.** `juntar.py` busca por remitente sin filtro de carpeta. No agregar `in:inbox`.
- **Algunos (NYT) mandan un text/plain de 2 líneas.** `juntar.py` usa el texto del HTML cuando es más largo.
- **El mail no puede pasar los ~100 KB** o Gmail lo corta. `juntar.py` desenvuelve los links de tracking y `armar.py` avisa arriba de 98 KB: si pasa, recortar destacados de «Por fuente».
- **Hay newsletters sin link de «ver en el navegador»** (ej: Cenital). Sus ediciones linkean al hilo de Gmail, marcado «(Gmail)».
- **Un medio puede mandar promos desde el mismo remitente.** Se filtran con `excluir_asunto` (regex) en `fuentes.json`.
- **Haiku no cita textual:** el diario parafrasea. Las cifras sí se copian, y el prompt exige que estén en el texto.
- **Haiku deforma hechos, no solo el texto:** puede atribuirle a una persona lo que dijo otra, o meter un dato que la fuente no trae. Por eso el paso 4 verifica contra `state/fuentes/<slug>.txt` todo lo que va a tapa, opinión y números. Los ids de link del destilado también se chequean.
- **Kindle:** el mail que manda tiene que estar aprobado en Amazon. El asunto NO lleva «Convert». Si Amazon rechaza, llega un mail de Amazon a tu Gmail.
- **Pandoc descarta `class` en `<p>`.** Los estilos del EPUB van en `<div class>` o en `<strong>`/`<em>`.
- **Pandoc no sabe abrir el libro en el índice.** `kindle.py` reescribe el zip: portada `linear="no"`, nav en la lectura y la guía apunta a `nav.xhtml`. El `mimetype` va primero y sin comprimir.
- **Boilerplate de los mails:** `kindle.py` lo saca con `PIE`, `RUIDO` y `SPONSOR`. Si aparece ruido nuevo de una fuente, se suma ahí.
- **TLDR es todo links.** `tldr_a_html` arma cada ítem como titular + resumen; si no logra parsear 3 ítems, cae al texto limpio común.
- **Un Kindle de tinta no dibuja emoji.** Por eso el libro va sin emojis en los títulos.
