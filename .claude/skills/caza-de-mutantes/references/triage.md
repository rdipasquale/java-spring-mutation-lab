# Triage de mutantes sobrevivientes

Esta es la parte que decide si la skill sirve o es ruido. Un mutante que
sobrevive **no** es "un test que falta". Es una pregunta: *¿por qué nadie
se dio cuenta de que cambié esto?* Hay cinco respuestas posibles y solo
dos terminan en un test nuevo.

## El error que hay que evitar

La tentación es escribir el test que mata al mutante:

```python
# mutante: `if pct > 50` -> `if pct >= 50`
def test_descuento_pct_50():
    assert descuento(100, 50) == 50   # mata el mutante
```

Esto sube el score y no enseña nada. Está escrito mirando la mutación, no
el dominio. Dentro de seis meses nadie va a saber por qué existe, y a la
primera refactorización lo borran.

**La prueba de fuego**: si no podés explicar el test propuesto como una
afirmación sobre el negocio, sin mencionar la mutación, el test está mal.
"El descuento nunca puede superar el 50%, ni siquiera en el borde exacto"
sí pasa la prueba. "La línea 4 usa `>` y no `>=`" no.

## Las cinco categorías

Clasificá cada sobreviviente en una sola. La categoría determina la acción;
no la elijas mirando cuál da más trabajo.

### `equivalente` — no cambia el comportamiento observable

El mutante es semánticamente idéntico al original. No existe ningún test
que pueda matarlo, porque no hay nada que distinguir.

Señales típicas: cambios en el orden de evaluación de operaciones
conmutativas, límites de estructuras que ya están acotadas por otra
condición, optimizaciones (`x * 2` → `x + x`), mutaciones en `equals`/
`hashCode` que no alteran el contrato, cambios en el mensaje de una
excepción que nadie inspecciona.

**Acción**: registrar en el ledger con la explicación de *por qué* es
equivalente. No escribir ningún test. La nota importa: es lo que evita que
el próximo que corra la herramienta pierda media hora en lo mismo.

Cuidado: "no se me ocurre cómo matarlo" no es lo mismo que "es
equivalente". Determinar equivalencia es indecidible en el caso general,
así que la nota tiene que ser un argumento, no una rendición.

### `codigo-muerto` — la rama no debería existir

El mutante sobrevive porque el código que mutó es inalcanzable: una guarda
defensiva que ningún camino real ejecuta, un `default` en un switch
exhaustivo, un chequeo de null sobre algo que nunca es null.

**Acción**: proponer *borrar el código*, no agregar un test. Agregar un
test acá es peor que no hacer nada: congela código muerto y obliga a
mantenerlo para siempre.

Excepción legítima: programación defensiva deliberada en un límite de
sistema (entrada externa, deserialización, API pública). Ahí la guarda sí
debe existir, y entonces la categoría correcta es `hueco-real` — hay que
testear que la guarda hace lo que promete.

### `sin-asercion` — se ejecuta y nadie chequea

El código mutado **sí** está cubierto: hay tests que lo atraviesan. Pero
ninguno afirma nada sobre su efecto. Es el hallazgo más valioso de todos,
porque es exactamente lo que la cobertura de líneas te oculta: 100% de
cobertura y 0% de verificación.

Señales: el mutante está en una función que aparece en varios tests, pero
`killing_tests` está vacío. Suele pasar con efectos secundarios (algo que
se escribe en un log, un campo que se setea, un evento que se publica) y
con valores de retorno que el test ignora.

**Acción**: fortalecer un test que **ya existe**, no crear uno nuevo. Casi
siempre es agregar la aserción que faltaba sobre un resultado que el test
ya tenía a mano. Es el cambio más barato y el de mejor relación
valor/esfuerzo.

### `hueco-real` — falta un caso de comportamiento

Hay una condición, un borde o un invariante del dominio que ningún test
ejercita. Acá sí corresponde un test nuevo.

**Acción**: escribir el test al nivel de la conducta, siguiendo la guía de
la sección siguiente.

### `fuera-de-alcance` — no vale la pena

Logging, métricas, `toString`, código generado, glue de configuración,
mapeos triviales. Testear esto tiene costo de mantenimiento y valor cero.

**Acción**: suprimir con nota. Si una categoría entera aparece seguido
(por ejemplo, todo lo que está en `*/generated/*`), conviene excluirla en
la configuración de la herramienta en vez de triarla mutante por mutante.

## Agrupar antes de recomendar

Ocho mutantes sobrevivientes en la misma función casi nunca son ocho
huecos. Son un escenario faltante que se manifiesta ocho veces. Antes de
proponer nada, agrupá por `symbol` y preguntate qué caso del dominio
explicaría a todo el grupo de una.

Un grupo grande en una función también es señal de otra cosa: que la
función hace demasiado. Si diez mutantes distintos sobreviven en el mismo
método, la recomendación honesta puede ser "esto pide separarse en dos",
no "faltan diez tests".

## Cómo se escribe un test que enriquece

Ordenados de mejor a peor, elegí el más alto que aplique:

**1. Invariante o propiedad.** La afirmación más fuerte: vale para todas
las entradas, no para una. Usá Hypothesis (Python), jqwik (Java) o
FsCheck/CsCheck (.NET).

```python
@given(monto=st.decimals(0, 10000), pct=st.integers(0, 100))
def test_el_descuento_nunca_supera_la_mitad(monto, pct):
    # regla de negocio: por más que pidan 80%, el tope es 50%
    assert descuento(monto, pct) >= monto / 2
```

Esto mata de un saque todos los mutantes del tope, y además mata los que
todavía no existen.

**2. Tabla de casos borde.** Cuando la propiedad no se puede expresar,
enumerá los bordes del dominio con su justificación de negocio: el cero,
el límite exacto, el límite ± 1, el vacío, el máximo.

**3. Contrato de la excepción.** Si la guarda debe existir, testeá que
lanza lo que promete, con el tipo correcto y en la condición correcta.

**4. Verificación del efecto.** Para `sin-asercion` sobre efectos:
afirmar que el efecto ocurrió con los datos correctos, no solo que la
función no explotó.

## El formato de la propuesta

Para cada grupo, producí:

- **Qué se rompe sin esto**: el comportamiento real que hoy nadie protege,
  en lenguaje de dominio. Una frase.
- **Categoría** y por qué esa y no otra.
- **Acción**: test nuevo / fortalecer `NombreDelTestExistente` / borrar
  código / suprimir.
- **El test**, escrito en el estilo y framework que ya usa el repo. Mirá
  los tests vecinos antes de escribir: si el proyecto usa AAA con
  comentarios, seguí eso; si usa fixtures, usá fixtures.
- **Mutantes que debería matar**: las huellas, para poder verificar.

Y una cosa que se omite seguido: si la conclusión honesta es que no hay
nada que valga la pena testear, decilo. Un reporte que dice "de 14
sobrevivientes, 11 son equivalentes o fuera de alcance, y los 3 que
importan son este caso borde" vale mucho más que 14 tests generados.

## Verificar, siempre

Una propuesta sin verificar es una alucinación con formato. Después de
aplicar los tests:

1. La suite completa sigue en verde (el test nuevo no rompió nada).
2. Los mutantes objetivo efectivamente mueren — re-correr la herramienta
   acotada a esas huellas.
3. Si no mueren, el test no sirve: decilo y volvé al triage. No lo dejes
   pasar porque "igual suma cobertura".
