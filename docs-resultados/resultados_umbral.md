# Calibración del umbral de aceptación — EcoLogix (Entrega 2, C.2)

Generado por `python calibrar_umbral.py` sobre la colección ChromaDB
`ecologix` (coseno, embeddings locales). Se mide el **mejor** puntaje de
cada consulta, sin aplicar ningún umbral, y se cuenta qué pasaría con
cada corte.

## Consultas que EcoLogix sí puede responder (18)

| Consulta | Mejor documento | Similitud |
|---|---|---:|
| me llegó todo roto el pedido, me devuelven la plata? | `doc-012` | 0.3317 |
| me llegaron unos paquetes rotos, quiero reclamar | `doc-012` | 0.4095 |
| necesito unos pots | `doc-019` | 0.4110 |
| tengo un pedido en curso, como va? | `doc-016` | 0.4238 |
| necesito algo para takeaway | `doc-004` | 0.4275 |
| ¿Los envases del desengrasante se pueden devolver para recargar? | `doc-002` | 0.4354 |
| ¿Hacen envíos a mi zona o tengo que retirar por el depósito? | `doc-011` | 0.4414 |
| che, tenés pajitas de papel? de a cuántas vienen? | `doc-004` | 0.4491 |
| Necesito sorbetes para mi kiosco, que esten disponibles en stock | `doc-004` | 0.4631 |
| hay algo para servir café para llevar? | `doc-002` | 0.4759 |
| Se rompieron varios envases de cartón en la entrega, quiero reclamar | `doc-012` | 0.5377 |
| ¿Las tapas vienen incluidas en la caja de vasos? | `doc-002` | 0.5407 |
| ¿En qué estados puede estar un ticket de reclamo por entrega? | `doc-012` | 0.5791 |
| ¿Cuál es el mínimo de compra para un pedido chico? | `doc-007` | 0.5814 |
| Necesito packaging para mandar comida caliente a domicilio, que no se rompa ni se moje | `doc-005` | 0.6202 |
| ¿Cuántas unidades trae la caja de bolsas compostables? | `doc-001` | 0.7049 |
| Quiero encargar dos cajas de bolsas compostables para mi súper | `doc-001` | 0.7265 |
| Tenés vasos biodegradables para una cafetería | `doc-019` | 0.8266 |

## Consultas que EcoLogix no puede responder (8)

| Consulta | Mejor documento | Similitud |
|---|---|---:|
| ¿Quién ganó el último mundial de fútbol? | `doc-010` | 0.1238 |
| ¿Tienen zapatillas deportivas? | `doc-004` | 0.1756 |
| ¿Cómo está el clima hoy en Buenos Aires? | `doc-006` | 0.1816 |
| busco contratos de alquiler | `doc-012` | 0.3475 |
| Venden celulares o accesorios de telefonia? | `doc-017` | 0.3735 |
| venden notebooks y laptops | `doc-017` | 0.3839 |
| ¿Venden servilletas de papel reciclado? | `doc-013` | 0.5397 |
| ¿Cuánto cuesta una caja de vasos de bagazo de 12 oz? | `doc-002` | 0.6131 |

## Qué pasa con cada umbral

| Umbral | Consultas válidas rechazadas | Consultas fuera de catálogo aceptadas |
|---|---|---|
| 0.35 | 1 de 18 | 4 de 8 |
| 0.38 | 1 de 18 | 3 de 8 |
| 0.40 (actual) | 1 de 18 | 2 de 8 |
| 0.42 | 3 de 18 | 2 de 8 |
| 0.45 | 8 de 18 | 2 de 8 |

## Lectura

- **Los dos grupos se solapan por los dos extremos.** Una consulta válida
  informal ("me devuelven la plata", 0.3317) queda por debajo
  de varias fuera de catálogo, y dos fuera de catálogo "vecinas" del
  dominio superan cualquier corte razonable.
- **Dejando de lado esos dos casos hay un hueco.** Las fuera de catálogo
  que no se parecen a un producto llegan como máximo a 0.3839 y las
  consultas válidas, sin contar la informal, parten de 0.4095. El punto
  medio del hueco es 0.40, que es el umbral definido
  (**0.4**).
- **El margen es chico.** Del lado de las consultas válidas es de
  0.0095. Es un valor ajustado a este corpus, modelo y
  conjunto de consultas, no una frontera general; hay que repetir esta
  calibración si cambia alguno de los tres.
- **Las vecinas no se resuelven con el umbral.** Preguntar por
  servilletas o por el precio de un producto que sí existe se parece al
  corpus aunque la respuesta no esté: la similitud mide cercanía de
  tema, no si el dato existe. Ese resto lo cubren el filtro de negocio
  dentro del `where` (por ejemplo `tipo=producto` según la intención) y,
  en la Entrega 3, las reglas del prompt con la frase de escape.
