# Guia del laboratorio de mutation testing

## Objetivo

Demostrar que ejecutar todas las lineas no equivale a verificar correctamente el comportamiento. La pregunta no es solo "la prueba paso por esta rama", sino "la prueba fallaria si la rama hiciera algo incorrecto".

## Punto de partida

Ejecutar:

```bash
mvn clean verify
mvn clean test-compile org.pitest:pitest-maven:mutationCoverage
```

Comparar:

- cobertura de lineas y ramas en `target/site/jacoco/index.html`;
- cobertura de mutaciones en `target/pit-reports/index.html`.

## Desafios

### Desafio 1: precios exactos de envio

La suite normal comprueba que un envio pago sea mayor que cero. Eso no diferencia entre 700, 701 o 1500 centavos.

Agregar pruebas que documenten el precio exacto de:

- standard;
- express;
- pickup.

### Desafio 2: frontera de envio gratis

Probar ambos lados de la frontera:

- neto exactamente igual a 10000 centavos;
- neto igual a 9999 centavos.

Una sola prueba muy por encima del limite no detecta `>=` cambiado por `>`.

### Desafio 3: porcentajes de descuento

"El descuento es positivo" no prueba que PREMIUM sea 10 por ciento, VIP 15 por ciento ni primera compra 5 puntos adicionales.

Expresar los importes exactos con subtotales faciles de calcular.

### Desafio 4: cupon y tope

Probar:

- monto exacto del cupon;
- codigo sin importar mayusculas/minusculas;
- codigo desconocido;
- escenario donde la suma supera el tope;
- valor exacto del tope.

### Desafio 5: validez en los bordes

No basta con probar un numero muy negativo. Probar los valores inmediatamente alrededor de la regla:

- 0 debe fallar;
- 1 debe ser valido.

## Criterio para una buena prueba

Una prueba fuerte suele tener estas caracteristicas:

- nombre que expresa una regla de negocio;
- datos elegidos alrededor de limites;
- resultado observable exacto;
- una falla clara cuando la regla cambia;
- poca dependencia de detalles internos del algoritmo.

Evitar copiar el mismo algoritmo productivo dentro del test. Preferir ejemplos concretos y tablas de decision.

## Suite de referencia

La respuesta esta en `src/solution-test/java`. Activarla solo despues del ejercicio:

```bash
mvn -Psolution-tests clean test-compile org.pitest:pitest-maven:mutationCoverage
```

No todos los sobrevivientes restantes son necesariamente defectos. Puede haber mutaciones equivalentes: cambios de bytecode que no alteran el comportamiento observable. Deben analizarse, no perseguirse ciegamente solo para llegar a 100 por ciento.
