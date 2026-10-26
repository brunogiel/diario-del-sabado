# Prompt del paso 3: destilar (resumir) una fuente (Haiku, uno por fuente)

Reemplazar `{SLUG}` y `{BASE}` antes de despachar. Un agente por archivo de `state/fuentes/`.

---

Leé el archivo `{BASE}/state/fuentes/{SLUG}.txt`. Trae todas las ediciones de esta semana de un newsletter, con sus links numerados entre corchetes, por ejemplo `[nyt:2:5]`. Cada edición tiene además un id web, por ejemplo `nyt:2:web`.

Tu trabajo: destilar lo importante de la semana de ESTA fuente en un JSON. No escribas nada más.

Reglas:
1. **Los links se citan SOLO por id**, copiado tal cual de los corchetes del archivo o del «id web» de la edición. Nunca escribas una URL. Si no hay un id que corresponda, usá el id web de esa edición.
2. **Escribí en español rioplatense neutro**, frases cortas, parafraseando. No copies oraciones del original.
3. **Cada cifra tiene que estar en el texto del archivo.** No calcules ni redondees cifras nuevas.
4. Ignorá publicidad, sponsors, promos de la propia fuente, ofertas y pedidos de suscripción.
5. Si la fuente cubre la misma historia varios días, juntala en un solo hecho con lo último que se supo.
6. Si algo no aparece, dejá la lista vacía. No inventes para llenar.

Guardá el resultado con la herramienta Write en `{BASE}/state/destilado/{SLUG}.json` con este esquema exacto:

```json
{
  "fuente": "{SLUG}",
  "hechos": [
    {"titulo": "titular corto (máx 12 palabras)", "resumen": "2 frases: qué pasó y por qué importa", "importancia": 1, "link": "id"}
  ],
  "cifras": [
    {"cifra": "3,1%", "que": "qué mide, en una frase", "link": "id"}
  ],
  "proximos": [
    {"cuando": "fecha o día anunciado, tal como lo dice el texto", "que": "qué va a pasar", "link": "id"}
  ],
  "largas": [
    {"titulo": "título de la pieza", "por_que": "por qué vale leerla entera, 1 frase", "link": "id"}
  ],
  "destacados": [
    {"titulo": "titular corto", "linea": "1 frase", "link": "id"}
  ]
}
```

Cantidades: `hechos` de 3 a 6 (`importancia` de 1 a 3, 3 = lo más importante de la semana en el mundo). `cifras` hasta 4. `proximos` hasta 4, solo eventos posteriores a la fecha de la última edición. `largas` hasta 2: ensayos o análisis largos, no notas breves. `destacados` exactamente 3, lo mejor de la fuente para alguien que no la leyó.

Al terminar, contestá solo: `ok {SLUG}` y la cantidad de hechos.
