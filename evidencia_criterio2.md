# Evidencia de ejecución real – Criterio 2

## Escenario 1: Conversación sin herramientas

- Consulta: Hola, ¿cómo estás? ¿En qué podés ayudarme?
- Resultado: el agente respondió directamente al usuario.
- Herramientas ejecutadas: ninguna (`herramientas_utilizadas = {}`).
- Ejecución exitosa: `exito = True`.

## Escenario 2: Uso de dos herramientas en un mismo turno

- Consulta: Consultá el estado del pedido 101 y registrá un reclamo porque llegó con el embalaje dañado.
- Primera herramienta: `consultar_estado_envio`.
- Segunda herramienta: `registrar_reclamo`.
- Resultado del pedido: estado `EN_CAMINO`.
- Resultado del reclamo: ID `1`, estado `ABIERTO`.
- Herramientas utilizadas: ambas.
- Ejecución exitosa: `exito = True`.

## Escenario 3: Consulta de estado de envío

- Endpoint: POST /consultar
- Thread ID: criterio2-evidencia-101
- Consulta: ¿Dónde está mi pedido 101?
- Herramienta ejecutada: consultar_estado_envio
- Parámetro: nro_pedido = 101
- Resultado de la herramienta: estado = EN_CAMINO
- Resultado final: consulta exitosa (exito = True).

La ejecución fue verificada mediante LangSmith. Por las políticas
de privacidad configuradas, los inputs y outputs se mantienen ocultos
en la traza. Los parámetros y el resultado operativo se verificaron
mediante el registro local sanitizado.