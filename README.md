# El diario del sábado

Un skill para [Claude Code](https://claude.com/claude-code) que lee todos los newsletters que te
llegaron en la semana y te arma un diario personal para el sábado a la mañana.

Te llega por mail, y si querés también como libro al Kindle. Trae:

- **Tapa**: el resumen de la semana en cuatro párrafos, uno por área.
- **Qué pasó**, por sección (tu país, internacional, AI, negocios…), con una intro por sección.
- **Una nota de opinión** sobre el tema más fuerte. Toma posición, no resume.
- **Cómo te afecta**: lo que cambia para tu trabajo, tu país o tu familia, según tu perfil.
- **Números de la semana**, cada uno con su fuente.
- **Dónde las fuentes no coinciden**, qué mirar la semana que viene y qué leer completo.
- **Por fuente**: los destacados de cada newsletter, con link a la versión web.

Todo link sale de un mail real: el modelo cita un id y un script lo cambia por la URL. Un id
que no existe no se publica. Eso no garantiza que cada link corresponda a su hecho: por eso el
skill chequea contra el texto original lo que va a la tapa, la opinión y los números.

*English: a Claude Code skill that reads your week of newsletters from Gmail and emails you a
Saturday digest, with an optional Kindle EPUB. The first run scans your inbox to find the
newsletters you already get. Requires Python 3.9+ and the `gws` CLI. Docs, prompts and the
digest are in Spanish by default (`"idioma"` in `config.json` changes the digest's language).*

## En 3 pasos

1. Instalá: `git clone` + `./install.sh` (ver [Instalación](#instalación)).
2. En Claude Code decí **«configurá el diario»**: escanea tu Gmail y elegís tus newsletters.
3. El sábado te llega el diario. O pedilo cuando quieras: **«armame el diario»**.

## Cómo arranca: el kickoff

La primera vez, el skill **escanea tu Gmail** y te muestra los newsletters que ya recibís.
Elegís cuáles entran.

Después te pregunta si querés sumar **los newsletters que lee el autor**. Es opcional: podés
quedarte solo con los tuyos.

| Tipo | Newsletters sugeridos |
|---|---|
| Noticias | NYT The Morning, International Intrigue, Cenital (periodismo argentino) |
| Tech y AI | Every, TLDR, Ben's Bites, AI Secret, Ruben Hassid |
| Negocios | Lenny's Newsletter |
| Ideas | Farnam Street |

Si elegís uno que no recibís, te da el link para suscribirte. La suscripción la hacés vos.

Al final te hace cinco preguntas para armar tu perfil: qué hacés, dónde vivís, qué temas te
importan. Con eso se escribe «Cómo te afecta».

## Privacidad

- **Solo lee tu bandeja.** No marca, no archiva, no borra y no desuscribe. Lo único que escribe
  en Gmail es el diario que te mandás a vos (y un borrador en la prueba del kickoff).
- **El escaneo lee encabezados**: remitente, asunto y categoría de Gmail. No abre los cuerpos.
  La búsqueda que elige qué mails mirar («unsubscribe», «darte de baja») la hace Gmail.
- **Tus datos quedan en tu máquina**, en `~/.diario-del-sabado/`, fuera de la carpeta del skill.
  El repo nunca ve tu mail ni tu perfil.
- **Lo que lee el modelo:** los asuntos del escaneo y el texto de los newsletters de la semana.
  Es el mismo modelo que ya usás en Claude Code; no pasa por ningún otro servicio.
- **Los links que guardás** con «guardá este link» se bajan desde tu máquina para meterlos en el libro.
- **Los permisos de Gmail** son los que le des a `gws` al hacer login. El skill necesita leer y
  mandar mail, así que el modo de solo lectura de `gws` no alcanza.

## Requisitos

- [Claude Code](https://claude.com/claude-code), con subagentes habilitados (el skill resume
  cada fuente con un modelo chico, Haiku, en paralelo).
- Python 3.9 o más nuevo, con [Pillow](https://pypi.org/project/pillow/):
  ```bash
  python3 -m pip install --user Pillow
  ```
  Si tu Python es de Homebrew y `pip` se niega (error «externally-managed-environment»), usá un venv.
- [`gws`](https://github.com/googleworkspace/cli), la CLI de Google Workspace, conectada a tu Gmail
  (ver abajo).
- [pandoc](https://pandoc.org/installing.html), solo si querés el libro para el Kindle.

Probado en macOS. En Linux anda igual; la portada del libro usa la tipografía DejaVu en vez de Didot.

### Conectar Gmail

```bash
npm install -g @googleworkspace/cli
```
```bash
gws auth setup
```
```bash
gws auth login -s gmail
```

- `gws auth setup` se corre una vez. Crea un proyecto de Google Cloud y necesita
  [`gcloud`](https://cloud.google.com/sdk/docs/install). En el camino te pide armar la «pantalla
  de consentimiento» de OAuth: elegí tipo **Externo** y sumate como **usuario de prueba** con tu Gmail.
- `gws auth login -s gmail` abre el navegador y pide permiso solo para Gmail.
- Si un día el diario no sale y dice `invalid_grant`, el permiso venció: volvé a correr `gws auth login -s gmail`.

## Instalación

```bash
git clone https://github.com/brunogiel/diario-del-sabado.git
```
```bash
cd diario-del-sabado && ./install.sh
```

`install.sh` enlaza el skill en `~/.claude/skills/diario-del-sabado` y chequea los requisitos.
Para actualizar, `git pull` en la carpeta.

Después abrí Claude Code y decí **«configurá el diario»**. Arranca el kickoff.

## Uso

| Decís | Pasa |
|---|---|
| «configurá el diario» | el kickoff: escaneo, elección de fuentes, perfil, entrega |
| «armame el diario» | corre el diario de esta semana y te lo manda |
| «guardá este link para el diario: URL» | el link sale el sábado en «Lecturas destacadas» |
| «cambiá mis newsletters» | vuelve a escanear y te deja sumar o sacar fuentes |

Para que llegue solo cada sábado, el kickoff te ofrece programarlo: con las tareas programadas
de Claude Code desktop o con `cron`. En los dos casos la computadora tiene que estar prendida a
esa hora, y la tarea necesita permisos para correr `python3` y `gws` sin preguntarte. El
kickoff te da la línea completa.

## Cómo funciona

```
Gmail ──► juntar.py ──► un Haiku por fuente ──► redacción ──► armar.py ──► mandar.py ──► tu mail
          (texto + links    (resume hechos,       (tapa,        (HTML +       (gws)
           con id estable)   cifras, próximos)     opinión…)     chequeo de ids)
                                                                   └──► kindle.py ──► tu Kindle
```

- Los pasos marcados `[DET]` en `SKILL.md` son scripts: hacen siempre lo mismo (juntar, armar,
  verificar, mandar).
- Los pasos `[LATENT]` los hace el modelo, con criterio: resumir cada fuente y redactar el diario.
- Costo: un Haiku por fuente más una redacción con tu modelo principal. No está medido en
  dólares; depende de cuántas fuentes y ediciones tengas.

## Probar sin Gmail

```bash
python3 tests/smoke.py
```

Arma una semana inventada en una carpeta temporal y genera el HTML y el EPUB. Confirma que un
id inventado no llega al diario.

## Estructura

```
SKILL.md          el flujo de cada sábado
kickoff.md        la primera vez: escaneo, fuentes, perfil, entrega
sugeridos.json    los newsletters sugeridos (opcionales)
prompts/          el prompt que resume cada fuente
plantillas/       la plantilla del perfil del lector
scripts/          juntar, armar, kindle, portada, mandar, escanear, lecturas
tests/            prueba de humo sin Gmail
```

## Licencia

MIT. Ver [LICENSE](LICENSE).
