# Kickoff: armar tu diario la primera vez

Corre una sola vez, cuando no existe `~/.diario-del-sabado/config.json`. También a pedido:
«configurá el diario», «cambiá mis newsletters», «volvé a escanear mi mail».

Termina con tres archivos en `DIARIO_HOME` (por defecto `~/.diario-del-sabado/`): `config.json`,
`fuentes.json` y `perfil.md`. Nada de esto vive en la carpeta del skill.

`SKILL` = la carpeta donde está este archivo. Los scripts se corren como `python3 "$SKILL/scripts/<x>.py"`.

## Qué se lee y qué no (decíselo al usuario antes de escanear)

- El escaneo lee **solo encabezados** de los mails de los últimos 30 días que traen link para
  desuscribirse: remitente, asunto, categoría de Gmail, tamaño. No abre el cuerpo.
- No marca, no archiva, no borra, no desuscribe. Nunca.
- El resultado queda en tu máquina (`state/escaneo.json`). Lo único que sale es el diario que
  te mandás a vos mismo, desde tu propia cuenta.

## Flujo

### 1. [DET] Chequear el entorno

Correr cada chequeo. Si uno falla, parar, decir el comando exacto para arreglarlo y esperar.

| Chequeo | Comando | Si falla |
|---|---|---|
| Python 3.9+ | `python3 --version` | instalar Python 3 |
| `gws` instalado | `gws --version` | `npm install -g @googleworkspace/cli` |
| `gws` con Gmail | `gws gmail users getProfile --params '{"userId":"me"}' --format json` | el usuario corre `gws auth setup` (una vez, necesita `gcloud`) y `gws auth login -s gmail`. Abre el navegador: **lo hace el usuario, no vos**. Ver «Conectar Gmail» en el README |
| Pillow | `python3 -c "import PIL"` | `python3 -m pip install --user Pillow` (o en un venv) |
| pandoc (solo si quiere Kindle) | `pandoc --version` | macOS: `brew install pandoc`. Linux: `sudo apt install pandoc` |

Guardar el `emailAddress` del perfil: es el default de a dónde llega el diario.

### 2. [DET] Escanear

```bash
python3 "$SKILL/scripts/escanear.py"
```

Tarda ~1 minuto cada 500 mails. Si salen menos de 3 candidatos, repetir con `--dias 60`.

### 3. [LATENT] Separar newsletters de ruido

Leer `state/escaneo.json`. Cada candidato trae `cantidad`, `asuntos`, `categoria_gmail`,
`plataforma`, `kb_promedio`, `sugerido` y `ya_en_fuentes`.

Un **newsletter** es un mail editorial que se lee: un autor o un medio que cuenta algo, con
periodicidad. Señales a favor: plataforma (Substack, beehiiv, Mailchimp, Kit, Ghost), asuntos
que son titulares, `kb_promedio` alto, un remitente tipo `newsletter@` o el nombre de una persona.

Queda **afuera**:
- notificaciones de producto (GitHub, LinkedIn, Google, Slack, Supabase, bancos, aerolíneas);
- promos y ventas (`categoria_gmail` = promotions con asuntos de oferta, «% off», webinars);
- avisos transaccionales (facturas, envíos, cuentas, «action required»);
- digests de redes sociales.

Si dudás, va adentro marcado con `?`: el usuario decide, vos no.

Juntar remitentes: si varios mails de un **dominio propio** (`dominio_compartido` = false) son
del mismo medio, van como **una** fuente con remitente `@dominio`. En dominios compartidos
(substack.com, beehiiv.com, gmail.com) cada mail exacto es una fuente distinta. Si un medio
manda promos desde el mismo remitente, proponer un `excluir_asunto` (regex) que las saque.

Para cada newsletter proponer: `slug` (minúsculas, sin espacios), `nombre`, `tipo`
(`noticias` | `tech-ai` | `negocio` | `ideas`), `idioma` (`es` | `en` | otro), `remitentes`.

### 4. Mostrar y elegir

Mostrar una tabla numerada, ordenada por cantidad:

| # | Newsletter | Remitente | En 30 días | Tipo |
|---|---|---|---|---|

Abajo, en una línea: «Dejé afuera N que parecen notificaciones o promos: X, Y, Z…». Preguntar:
«¿Van todos? Decime los números que saco, o alguno de los de afuera que querés sumar».

### 5. Los sugeridos del autor (opcional)

`$SKILL/sugeridos.json` trae los 10 newsletters que lee el autor del skill. **Son opcionales.**
Preguntar con un selector (AskUserQuestion):

- **No, solo los míos** (default si no contesta)
- **Sí, todos los que me faltan**
- **Quiero elegir**

Si elige, mostrar la lista con `que_es` y si ya le llega (`te_llega` en `escaneo.json`).
Los elegidos entran a `fuentes.json` con los remitentes de `sugeridos.json`.

Para los que **no le llegan todavía**: darle el link `suscribirse` de cada uno. La suscripción la
hace el usuario: no completes formularios con su mail. Hasta que se suscriba, la fuente sale
vacía y el diario lo dice al pie.

### 6. El perfil

Preguntar, de a una o todas juntas, en chat:

1. ¿Cómo te llamo? (va en la portada: «HECHO CON IA PARA …»)
2. ¿Dónde vivís?
3. ¿A qué te dedicás y qué estás armando ahora?
4. ¿Qué temas te importan más? (tu industria, tu país, AI, familia…)
5. ¿Hay una meta que ordene tu año? (opcional)

Con las respuestas, completar `$SKILL/plantillas/perfil.md` y guardarlo como `DIARIO_HOME/perfil.md`.
Mostrarlo y pedir OK. Sin datos de salud ni nada sensible.

### 7. Secciones y entrega

Proponer y confirmar en un solo mensaje:

- **Secciones** de «Qué pasó», en orden, con un emoji cada una. Arrancar por el país del usuario
  si hay noticias de ahí (ej: `🇦🇷 Argentina`), después `🌍 Internacional`, `🤖 AI`,
  `🔬 Tecnología y ciencia`, `💼 Negocios`, `⚽ Cultura y deportes`. Ajustar al perfil.
- **Panorama de tapa**: las 4 áreas por las que arranca cada párrafo de la tapa, que es el resumen de arriba de todo (ej: Mundo, Argentina, AI y ciencia, Negocios).
- **A dónde llega**: el mail del perfil de Gmail, salvo que diga otro.
- **Kindle** (opcional): la dirección `@kindle.com`. Avisarle que tiene que aprobar su mail en
  Amazon → Contenido y dispositivos → Preferencias → Configuración de documentos personales.
- **Zona horaria**: la del sistema (`readlink /etc/localtime`).

### 8. [DET] Escribir la configuración

`DIARIO_HOME/config.json`:

```json
{
  "nombre": "Ana",
  "email": "ana@gmail.com",
  "kindle": null,
  "zona": "America/Argentina/Buenos_Aires",
  "idioma": "es",
  "secciones": [{"nombre": "Argentina", "emoji": "🇦🇷"}, {"nombre": "Internacional", "emoji": "🌍"}],
  "panorama": ["Mundo", "Argentina", "AI y ciencia", "Negocios"]
}
```

`DIARIO_HOME/fuentes.json`: `{"fuentes": [{slug, nombre, tipo, idioma, remitentes, excluir_asunto?}]}`.
Cada slug es único. Si ya existía un `fuentes.json`, mostrar qué cambia y pedir OK antes de pisarlo.

### 9. Primera prueba

Ofrecer correr el diario ahora con los últimos 7 días, **en borrador**:

1. Paso 2 de `SKILL.md` con `juntar.py --desde <hoy menos 7 días, YYYY-MM-DD>` (sin `--desde`
   arranca el sábado anterior, y un martes cubriría solo 3 días).
2. Pasos 3 a 5 como un sábado normal.
3. Paso 6 **sin `--enviar`**: queda en Borradores de Gmail. No se anota en `enviados.txt`.

El usuario lo mira antes del primer sábado.

### 10. Programarlo

Ofrecer dejarlo programado los sábados a las 9:30 en su zona horaria:

- **Claude Code desktop**: con la herramienta de tareas programadas, si está disponible
  (prompt: «Corré el skill diario-del-sabado»). Si no, explicarle cómo crear la tarea desde la app.
- **Terminal (cron)**: la Mac tiene que estar prendida a esa hora. La línea completa, con el PATH
  donde están `gws`, `python3` y `pandoc`, y los permisos que usa el skill (Bash, Read, Write y
  subagentes):
  ```
  PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin
  30 9 * * 6 cd ~ && claude -p "Corré el skill diario-del-sabado" --allowedTools "Bash(python3:*)" "Bash(gws:*)" "Bash(echo:*)" Read Write Edit Agent >> ~/.diario-del-sabado/cron.log 2>&1
  ```
  La primera línea va sola, arriba en el `crontab -e`: fija el PATH para todas las tareas.
  Ajustar el PATH si `gws` vino por nvm (`dirname $(which gws)`).

No programar nada sin el OK del usuario.
