---
name: salud-de-suite
description: Verifica que la suite de pruebas unitarias de un proyecto Python, Java o .NET sea confiable antes de sacar conclusiones de ella. Detecta el stack y el build tool, corre la suite varias veces, encuentra tests intermitentes (flaky), mide el tiempo base y calcula el timeout apropiado para mutation testing. Usala siempre que el usuario pida correr las pruebas, preguntar si los tests andan bien, evaluar o auditar la calidad de una suite, investigar tests que fallan a veces sí y a veces no, o antes de cualquier análisis que dependa de que los tests sean confiables (cobertura, mutation testing, métricas de calidad). También es el paso previo obligatorio de la skill caza-de-mutantes.
---

# Salud de la suite

Antes de sacar cualquier conclusión de una suite de tests hay que saber si
la suite miente. "Los tests pasan" no alcanza: una suite con tests
intermitentes produce métricas que parecen datos y son ruido, y una suite
donde el 30% está ignorado da una falsa sensación de cobertura.

Esta skill responde cuatro preguntas: ¿pasa en verde?, ¿es determinística?,
¿cuánto tarda?, ¿cuánto de ella está realmente activo?

## Cuándo parar y no seguir

Si el veredicto es `no-apta`, informá los bloqueos y **no** sigas con
análisis que dependan de la suite. Es preferible decir "no puedo confiar en
estos tests todavía, y este es el motivo" que producir un número lindo
sobre una base podrida. Si el usuario insiste, aclará qué queda invalidado.

## Flujo

### 1. Detectar el stack

```bash
python3 scripts/detect_stack.py --root <ruta>
```

Devuelve lenguaje, build tool, comando de test, dónde quedan los reportes
y si es multi-módulo. Mostrale al usuario qué detectaste antes de correr
nada pesado: si el proyecto es raro, es acá donde se ve.

Si `detected` es `false`, o si detectó un stack que no es el que el usuario
esperaba, preguntá en vez de adivinar. Un monorepo con tres lenguajes
necesita que el usuario diga cuál le interesa.

### 2. Medir

```bash
python3 scripts/suite_health.py --root <ruta> --runs 2 --out health.json
```

Dos corridas es el mínimo para detectar intermitencia. Si el usuario
sospecha de flakiness, subí a `--runs 5`; si la suite es lenta y solo
necesitás el veredicto y el tiempo base, `--runs 1` alcanza (pero entonces
decí explícitamente que la intermitencia no se evaluó).

Guardá siempre con `--out`: ese JSON es lo que consume `caza-de-mutantes`.

### 3. Reportar

Contale al usuario, en prosa y en este orden:

1. **Veredicto**: apta o no apta, y por qué en una frase.
2. **Bloqueos**, si hay. Para tests intermitentes, nombralos y mostrá la
   secuencia de resultados — un test que da `passed, failed` es una cosa y
   uno que da `passed, skipped` es otra (el segundo suele ser una condición
   de entorno, no una race).
3. **Tiempo base** y qué implica. Si la suite tarda más de 5 minutos,
   avisá que mutation testing full no es viable y que hay que acotar.
4. **Advertencias**: tests ignorados, variación grande entre corridas.

No vuelques el JSON crudo salvo que lo pidan.

## Interpretar lo que sale

**Intermitencia.** Es el hallazgo más importante y el que más se subestima.
Un test que a veces pasa y a veces no es peor que un test que falta,
porque entrena al equipo a ignorar el rojo. Las causas habituales: tiempo
real (`now()`, sleeps, timeouts), orden de ejecución (estado compartido
entre tests), concurrencia, dependencias de red o filesystem, e iteración
sobre estructuras sin orden garantizado.

Si detectás intermitencia, ofrecé investigar la causa — pero no la
adivines. Mirá el test.

**Tests ignorados.** Un `@Ignore`/`@Skip`/`[Ignore]` es un test que alguien
apagó y nadie prendió. Si superan el 10%, vale la pena preguntarse desde
cuándo están así.

**Suite vacía o sin reporte.** Si `total_tests` es 0 pero la suite "pasa",
casi seguro el runner no encontró los tests. Revisá la convención de
nombres antes de declarar victoria.

**Variación de tiempo grande.** Si una corrida tarda el doble que la otra,
hay algo no determinístico incluso si los resultados coinciden. Afecta
directamente el timeout de mutación.

## Notas por stack

**Java.** Maven y Gradle. En multi-módulo, `mvn test` corre todo el
reactor; si el usuario quiere un módulo solo, hay que agregar `-pl`. El
script lee `TEST-*.xml` de surefire, así que si el proyecto usa failsafe
(tests de integración), esos no se cuentan — y está bien, porque el alcance
acá es unitario.

**Python.** El comando se elige según lo que declare el proyecto: poetry,
uv, pipenv o pip directo. El reporte se fuerza con `--junit-xml`, así que
funciona sin configuración previa. Si el proyecto usa `unittest` puro,
pytest lo corre igual.

**.NET.** Usa `dotnet test` con logger `trx`. Detecta los proyectos de test
por sus `PackageReference` (xunit, NUnit, MSTest), que es más confiable que
el nombre del directorio.

## Encadenar con mutation testing

Cuando el usuario quiera evaluar la calidad de la suite (no solo si pasa),
el `health.json` es la entrada de la skill `caza-de-mutantes`. Decirlo
como oferta, no ejecutarlo de una: mutation testing es caro y conviene que
el usuario sepa en qué se mete.
