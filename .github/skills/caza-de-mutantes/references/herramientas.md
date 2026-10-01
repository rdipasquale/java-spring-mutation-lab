# PIT, mutmut y Stryker: lo que hay que saber de cada uno

Las tres hacen lo mismo conceptualmente y se comportan muy distinto. De las
tres, Stryker es la que mejor salida produce y mutmut la más frágil.

## Java — PIT

La más madura. Formato de reporte estable desde hace años.

**Instalación.** No requiere instalar nada global: se invoca como plugin de
Maven. Igual conviene declararlo en el `pom.xml` para fijar la versión.

```bash
mvn org.pitest:pitest-maven:mutationCoverage
```

**La trampa número uno: JUnit 5.** PIT sin `pitest-junit5-plugin` no
detecta ningún test de JUnit 5. No falla — corre, termina, y reporta todos
los mutantes como `SURVIVED`. Si ves un score de 0% o cercano, revisá esto
antes que nada.

```xml
<plugin>
  <groupId>org.pitest</groupId>
  <artifactId>pitest-maven</artifactId>
  <version>1.15.8</version>
  <dependencies>
    <dependency>
      <groupId>org.pitest</groupId>
      <artifactId>pitest-junit5-plugin</artifactId>
      <version>1.2.1</version>
    </dependency>
  </dependencies>
</plugin>
```

**Acotar.** `-DtargetClasses=com.empresa.modulo.*` acepta globs sobre
nombres de clase, no rutas de archivo. El script traduce los archivos del
diff a nombres de clase asumiendo el layout estándar `src/main/java`; si el
proyecto usa otro layout, hay que ajustar a mano. PIT también tiene
análisis incremental con `-DhistoryInputFile`/`-DhistoryOutputFile`, útil
en CI.

**Multi-módulo.** `mvn` corre el reactor entero. Para un módulo solo,
agregar `-pl <modulo> -am`.

**Operadores.** El set default es conservador. `-Dfeatures=+STRONGER`
activa mutadores más agresivos; vale la pena solo si el score con los
defaults ya es alto.

**Reporte.** `target/pit-reports/mutations.xml`. Con
`-DtimestampedReports=false` queda en una ruta fija, que es lo que el
script espera.

## .NET — Stryker

La mejor salida de las tres: emite JSON en el esquema estándar
*mutation-testing-elements*, lo que hace el parseo trivial y estable.

**Instalación.**

```bash
dotnet tool install -g dotnet-stryker
# mejor, para reproducibilidad en equipo:
dotnet new tool-manifest && dotnet tool install dotnet-stryker
```

**Acotar.** Soporte nativo de diff: `--since:main` muta solo lo que cambió.
Es la mejor implementación de las tres.

**Configuración.** `stryker-config.json` en la raíz del proyecto de test.
Vale la pena para excluir código generado:

```json
{
  "stryker-config": {
    "mutate": ["!**/Migrations/**", "!**/*.Designer.cs"],
    "thresholds": { "high": 80, "low": 60, "break": 0 }
  }
}
```

Dejá `break` en 0 mientras estés explorando: no querés que la corrida falle
por umbral mientras estás entendiendo el terreno.

**Trampa.** Con varios proyectos de test en la solución, Stryker puede
necesitar `--test-project` explícito. Y si el proyecto no compila en
configuración Release, falla con un error poco claro.

**Reporte.** `StrykerOutput/<timestamp>/reports/mutation-report.json`. El
script toma el más reciente.

## Python — mutmut

La más frágil de las tres, y conviene saberlo de antemano.

**El problema.** mutmut no tiene salida machine-readable estable, y 3.x
cambió bastante respecto de 2.x: la forma de materializar mutantes, el CLI
y el formato de `mutmut results`. El parser contempla ambos, pero es el
punto más probable de rotura.

**Instalación.** `pip install mutmut`

**Configuración.** Sin `[tool.mutmut]`, adivina qué mutar y suele incluir
los propios tests y scripts sueltos, lo que arruina el resultado.

```toml
[tool.mutmut]
paths_to_mutate = ["src/"]
tests_dir = "tests/"
```

**Virtualenv.** En el worktree no hay venv, porque no está trackeado. O lo
pasás con `--carry .venv`, o recreás el entorno adentro. Es la diferencia
más molesta contra Java y .NET, donde los caches de dependencias se
comparten.

**La alternativa: cosmic-ray.** Si mutmut da problemas, vale la pena
cambiar. Es más lento, pero persiste todo en SQLite y su salida es
genuinamente machine-readable, que para un flujo automatizado compensa de
sobra la diferencia de velocidad.

```bash
pip install cosmic-ray
cosmic-ray init config.toml session.sqlite
cosmic-ray exec config.toml session.sqlite
cr-report session.sqlite
```

Hoy el script no lo soporta; agregar un parser de cosmic-ray es el primer
lugar donde extender esto si el camino de Python se vuelve doloroso.

## Costo comparado

Muy a grandes rasgos, el tiempo es *cantidad de mutantes × tiempo de la
suite*, con descuentos importantes cuando la herramienta sabe qué tests
tocan cada mutante.

- **PIT** es el más rápido: usa cobertura para correr solo los tests
  relevantes a cada mutante.
- **Stryker** también filtra por cobertura y va bien.
- **mutmut** es el más lento y el que más se beneficia de acotar por diff.

En los tres, el timeout por mutante importa: si es muy bajo, mutantes vivos
se reportan como `TIMEOUT` y el score sale inflado. El script lo calcula
como `tiempo_base × 1.5 + 10s`, a partir de la medición real de
`salud-de-suite`.
