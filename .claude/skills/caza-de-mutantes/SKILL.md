---
name: caza-de-mutantes
description: Evalúa la calidad real de una suite de pruebas unitarias con mutation testing en Python (mutmut), Java (PIT) o .NET (Stryker), y propone tests que enriquezcan el testing en vez de tests que solo suban el score. Corre en un git worktree aislado, verifica dependencias, acota el alcance por diff para que no cueste horas, lleva un registro persistente del triage entre corridas y verifica que los tests propuestos efectivamente maten a los mutantes. Usala cuando el usuario pregunte qué tan buenos son sus tests, si los tests realmente prueban algo, quiera medir la calidad más allá de la cobertura, mencione mutation testing, mutantes, PIT, mutmut, Stryker o cosmic-ray, o sospeche que tiene alta cobertura pero tests débiles.
---

# Caza de mutantes

La cobertura te dice qué líneas se ejecutaron. No te dice si a alguien le
importó lo que hacían. Mutation testing rompe el código a propósito y
pregunta si algún test se da cuenta: cada rotura que sobrevive es un lugar
donde podés cambiar el comportamiento y la suite sigue en verde.

El objetivo de esta skill **no es subir el score**. Es encontrar los pocos
lugares donde falta una prueba que valga la pena, y decir con franqueza
cuáles no valen la pena. Un reporte que concluye "de 14 sobrevivientes, 11
son irrelevantes y estos 3 importan" es mejor resultado que 14 tests
generados.

## Las dos reglas que no se negocian

**No mutar sobre una suite que no es confiable.** Un mutante "muerto" por
un test intermitente es ruido. Correr `salud-de-suite` primero es
obligatorio, no una cortesía.

**Parar antes de escribir tests.** El triage es donde entra el criterio
humano. Presentá el análisis y esperá. No escribas tests por iniciativa
propia aunque tengas todo claro.

## Flujo

### 1. Gate de salud

Si no hay un `health.json` de esta sesión, corré la skill `salud-de-suite`.
Si el veredicto es `no-apta`, parás acá y explicás por qué. No hay vuelta
de rosca: sin suite confiable, todo lo que sigue es inventar.

### 2. Dependencias

```bash
python3 scripts/mutate.py check --health health.json
```

Si falta algo, mostrá las instrucciones exactas que devuelve el script y
**preguntá antes de instalar**. Instalar herramientas sin permiso en el
entorno de alguien es mala educación.

El caso que más muerde: un proyecto Java con JUnit 5 sin
`pitest-junit5-plugin` corre sin errores y reporta todos los mutantes como
sobrevivientes, porque PIT no encuentra ningún test. Si ves un score
sospechosamente catastrófico, es esto.

Detalle por herramienta en `references/herramientas.md`.

### 3. Alcance

```bash
python3 scripts/mutate.py scope --health health.json --base origin/main
```

**El alcance por diff es el default y no es una limitación, es lo que hace
la skill usable.** Mutation testing full sobre un repo mediano son horas;
si la primera corrida tarda dos horas, nadie la corre una segunda vez.

Usá alcance completo solo si el usuario lo pide explícitamente, y avisale
el costo estimado (tiempo base de la suite × cantidad de mutantes, que
suele ser cientos). Eso es material de CI nocturno, no de una conversación.

### 4. Cazar

```bash
python3 scripts/mutate.py run --health health.json --base origin/main --out run.json
```

Crea un worktree efímero, corre la herramienta y limpia siempre, incluso si
la corrida explota. El worktree evita que los artefactos
(`mutants/`, `StrykerOutput/`, `target/pit-reports/`) te ensucien el árbol
y que una corrida larga te bloquee el repo.

**El worktree no lleva archivos untracked.** Si el proyecto necesita un
`.env`, un `appsettings.local.json` o un virtualenv, pasalos con `--carry`
(repetible). En Python es lo habitual; en Java y .NET los caches
(`~/.m2`, NuGet) se comparten y suele no hacer falta.

Avisá al usuario que esto puede tardar, con un número concreto salido del
tiempo base. Nunca lo dejes esperando sin saber.

### 5. Normalizar

```bash
python3 scripts/normalize.py --tool <pit|mutmut|stryker> \
  --input <raw_report_dir> --repo-root <repo> --out mutants.json
```

Unifica las tres salidas y le da a cada mutante una huella estable al
refactor: si identificás mutantes por archivo+línea, el primer formateo
automático te invalida todo el historial. La huella se calcula sobre
archivo, símbolo contenedor, operador y posición relativa dentro del
símbolo, así que mover una función no la cambia.

Mirá los dos scores que devuelve. `mutation_score` es el clásico, sobre
mutantes cubiertos, y se infla solo. `mutation_score_covered` incluye el
código sin cobertura y es el que hay que reportar: un proyecto puede tener
95% de score clásico y la mitad del código sin tocar.

### 6. Diferenciar contra el historial

```bash
python3 scripts/ledger.py diff --report mutants.json
```

Separa la corrida en nuevos / ya triados / suprimidos / resueltos. **Enfocá
el reporte en los nuevos.** Volver a mostrar los 40 sobrevivientes que el
usuario ya descartó como equivalentes es la forma más rápida de que
abandone la herramienta.

Los `resueltos` son mutantes que antes sobrevivían y ahora mueren: alguien
escribió el test. Mencionalos, es la única señal de progreso real que
produce esto.

### 7. Triage — parar acá

Leé `references/triage.md` **antes** de analizar nada. Contiene la
taxonomía de cinco categorías y la guía de cómo se escribe un test
semántico en vez de una aserción pegada al mutante. Es la parte de la
skill que hace la diferencia entre algo útil y un generador de relleno.

Agrupá por símbolo antes de proponer: ocho sobrevivientes en la misma
función suelen ser un escenario faltante, no ocho tests.

Presentá el análisis y esperá la decisión del usuario. Para cada grupo:
qué comportamiento real queda desprotegido, en qué categoría cae y por
qué, qué acción corresponde (test nuevo, fortalecer uno existente, borrar
código, suprimir).

### 8. Registrar y aplicar

Con las decisiones confirmadas:

```bash
python3 scripts/ledger.py record --report mutants.json --triage triage.json
```

El ledger (`.mutation-ledger.json`) conviene commitearlo: el triage es
conocimiento del equipo, no estado local. La categoría `equivalente` sin
una explicación de *por qué* es equivalente no sirve — obligate a
escribirla.

Recién ahí escribí los tests aprobados, en el estilo del repo. Mirá los
tests vecinos antes: si usan fixtures, usá fixtures; si usan AAA con
comentarios, seguí eso.

### 9. Verificar

Una propuesta sin verificar es una alucinación con formato.

1. La suite completa sigue en verde.
2. Los mutantes objetivo efectivamente mueren — volvé a correr acotado.
3. Si no mueren, decilo y volvé al triage. No lo dejes pasar porque "igual
   suma cobertura".

## Reportar

En prosa, no volcando JSON. El orden que funciona:

1. **Qué tan buena es la suite**, en una frase, con el score sobre código
   cubierto y qué significa.
2. **Lo que importa**: los huecos reales, agrupados, en lenguaje de
   dominio. Esto es el reporte.
3. **Lo que no importa y por qué**: equivalentes y fuera de alcance,
   contados, no listados uno por uno.
4. **Progreso**, si hay ledger previo: qué se resolvió desde la última vez.
5. **Costo**: cuánto tardó y qué alcance se usó, para que el número se
   pueda interpretar.

Si el score es malo, no lo suavices; si es bueno, no infles el hallazgo.
Y si la conclusión honesta es que no hay nada que valga la pena testear,
esa es la respuesta.
