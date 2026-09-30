# Spring Mutation Lab

Proyecto didactico con Java 21, Spring Boot, Maven, JUnit 5, H2, un perfil de SQL Server y PIT para mutation testing.

La aplicacion expone una API minima de pedidos. La logica de precios incluye:

- descuentos por nivel de cliente;
- beneficio por primera compra;
- cupon `SAVE10`;
- tope de descuento;
- envio standard, express o retiro;
- umbral de envio gratis.

La suite normal parece bastante completa y recorre practicamente toda la politica de precios, ademas del servicio, repositorio y controlador. Sin embargo, varias pruebas solo verifican propiedades generales. PIT deberia mostrar mutantes sobrevivientes que una cobertura de lineas no revela.

## Requisitos

- JDK 21
- Maven 3.6.3 o superior

Verificar:

```bash
java -version
mvn -version
```

## 1. Ejecutar la suite normal

```bash
mvn clean test
```

Durante los tests de Spring se usa H2 en memoria con modo de compatibilidad SQL Server:

```text
jdbc:h2:mem:mutationlab-test;MODE=MSSQLServer
```

## 2. Generar cobertura tradicional

```bash
mvn clean verify
```

Abrir:

```text
target/site/jacoco/index.html
```

JaCoCo esta enfocado en `PricingPolicy`, que es tambien el objetivo de PIT.

## 3. Ejecutar mutation testing

```bash
mvn clean test-compile org.pitest:pitest-maven:mutationCoverage
```

Abrir:

```text
target/pit-reports/index.html
```

PIT cambia temporalmente condiciones, limites, operadores y constantes. Un mutante queda:

- `KILLED` cuando alguna prueba detecta el cambio;
- `SURVIVED` cuando todas las pruebas siguen pasando;
- `NO_COVERAGE` cuando ninguna prueba ejecuta esa linea.

En este laboratorio, los sobrevivientes son intencionales. Conviene buscarlos especialmente en:

- porcentajes exactos de descuento;
- costo exacto de envio standard y express;
- limite exacto para envio gratis;
- combinacion de cupon y tope de descuento;
- diferencias entre "algo de descuento" y "el descuento correcto".

## 4. Mejorar las pruebas

Modificar primero `src/test/java/com/example/mutationlab/pricing/PricingPolicyTest.java` sin mirar la solucion. Repetir PIT luego de cada mejora.

El proyecto tambien trae una suite fuerte opcional en `src/solution-test`. No se ejecuta por defecto.

Para activarla:

```bash
mvn -Psolution-tests clean test
mvn -Psolution-tests clean test-compile org.pitest:pitest-maven:mutationCoverage
```

Esto permite comparar directamente una suite basada en invariantes amplias con otra que expresa resultados y fronteras exactas.

## 5. Ejecutar la aplicacion localmente con H2

El perfil por defecto es `local`:

```bash
mvn spring-boot:run
```

La API queda en:

```text
http://localhost:8080/api/orders
```

La consola H2 queda en:

```text
http://localhost:8080/h2-console
```

Usar:

```text
JDBC URL: jdbc:h2:mem:mutationlab;MODE=MSSQLServer;DATABASE_TO_UPPER=false;DB_CLOSE_DELAY=-1
User: sa
Password: vacio
```

Hay ejemplos listos en `examples/requests.http`.

## 6. Ejecutar hipoteticamente contra SQL Server

Crear primero el esquema de `sql/sqlserver-schema.sql`.

Bash:

```bash
export SPRING_PROFILES_ACTIVE=prod
export DB_URL='jdbc:sqlserver://sql-host:1433;databaseName=mutation_lab;encrypt=true;trustServerCertificate=false'
export DB_USERNAME='mutation_app'
export DB_PASSWORD='replace-me'
mvn spring-boot:run
```

PowerShell:

```powershell
$env:SPRING_PROFILES_ACTIVE = "prod"
$env:DB_URL = "jdbc:sqlserver://sql-host:1433;databaseName=mutation_lab;encrypt=true;trustServerCertificate=false"
$env:DB_USERNAME = "mutation_app"
$env:DB_PASSWORD = "replace-me"
mvn spring-boot:run
```

En `prod`, Hibernate usa `ddl-auto: validate`: no crea ni modifica tablas, solo valida que el esquema esperado exista.

## Importante sobre H2 y SQL Server

`MODE=MSSQLServer` mejora la compatibilidad sintactica, pero H2 no reproduce completamente SQL Server. El laboratorio separa tres niveles:

1. pruebas unitarias de la politica, sin base de datos;
2. pruebas de persistencia y API con H2, rapidas y autocontenidas;
3. una futura prueba de integracion real contra SQL Server para validar dialecto, tipos, indices, aislamiento y comportamiento especifico del motor.

## Estructura principal

```text
src/main/java
  api/       REST y DTOs
  order/     servicio, entidad y repositorio
  pricing/   politica pura que PIT muta
src/test/java
  suite normal, intencionalmente insuficiente frente a algunos mutantes
src/solution-test/java
  suite exacta opcional
src/test/resources
  configuracion H2 de tests
sql/
  DDL de referencia para SQL Server
```

## Flujo sugerido para una demo

1. Ejecutar `mvn clean test`: todo verde.
2. Mostrar JaCoCo: la politica aparece ampliamente cubierta.
3. Ejecutar PIT y revisar los `SURVIVED`.
4. Elegir un mutante, por ejemplo `>=` cambiado por `>` o `700` cambiado por `701`.
5. Agregar una prueba que exprese el comportamiento de negocio exacto.
6. Repetir PIT y comprobar que el mutante muere.
7. Activar `solution-tests` para comparar con una especificacion mas fuerte.
