# Metricas de Analisis - ChessAnalyzerQML

Resumen de todo lo que calcula el programa para analizar partidas de ajedrez y detectar uso de motor.

---

## 1. Perdida de Centipeones (ACPL)

**Que es:** Cada vez que un jugador hace una jugada, el motor (Stockfish) calcula cual era la mejor jugada posible. La diferencia entre lo que jugaste y lo mejor se mide en **centipeones** (1 peon = 100 centipeones).

**Como se calcula:**

```
cp_loss = eval_antes - eval_despues   (minimo 0, maximo 1500)
ACPL   = suma de todos los cp_loss / numero de jugadas
```

**Que significa:**
- ACPL bajo (20-40) = juegas muy bien, cerca del motor
- ACPL medio (60-100) = jugador promedio
- ACPL alto (100+) = muchos errores

**Variante robusta (Robust ACPL):** Usa la **mediana** en vez del promedio y limita las perdidas a 300cp. Esto evita que un error catastrofico distorsione todo el resultado.

---

## 2. Tasa de Blunders (Errores Graves)

**Que es:** Porcentaje de jugadas donde perdiste mas de 100 centipeones.

```
tasa_blunders = jugadas_con_cp_loss_>_100 / total_jugadas
```

**Que significa:**
- <5% = casi nunca te equivocas gravemente (sospechoso si es constante)
- 10-15% = normal
- >20% = muchos errores graves

---

## 3. Coincidencia con el Motor (Match Rates)

**Que es:** Que porcentaje de tus jugadas coincide con las mejores jugadas del motor.

| Metrica | Que mide |
|---------|----------|
| Top-1 | % de jugadas que son LA mejor jugada |
| Top-2 | % de jugadas entre las 2 mejores |
| Top-3 | % de jugadas entre las 3 mejores |
| Top-4 | % de jugadas entre las 4 mejores |
| Top-5 | % de jugadas entre las 5 mejores |

**Match Rate Final** (aproxima la precision de Chess.com):
```
final_match = 0.05 * Top3 + 0.15 * Top4 + 0.80 * Top5
```

---

## 4. Jugadas de Precision

**Que es:** Jugadas donde acertaste la mejor jugada del motor en posiciones complicadas (20+ jugadas legales).

Un numero alto de jugadas de precision indica comprension tactica profunda... o uso de motor.

---

## 5. Analisis por Fases de la Partida

La partida se divide en tres fases:

| Fase | Definicion |
|------|-----------|
| **Apertura** | Primeras 15 jugadas |
| **Medio juego** | Jugada 16+ con mas de 12 piezas en el tablero |
| **Final** | Cualquier momento con 12 o menos piezas |

Para cada fase se calcula: ACPL, tasa de blunders, match rates.

**Transiciones entre fases:**
```
apertura_a_medio = acpl_medio - acpl_apertura
medio_a_final    = acpl_final - acpl_medio
```

- **Positivo** = juegas peor conforme avanza la partida (normal, humano)
- **Negativo** = mejoras conforme avanza (sospechoso, patron de motor)
- **Salto >50cp** = "colapso" (te derrumbas en una fase)

**Consistencia por fase:** Se mide la desviacion estandar del cp_loss en cada fase. Si en el medio juego eres mucho mas consistente que en la apertura (caida de varianza >20cp), es sospechoso porque parece que "enciendes el motor".

---

## 6. Analisis Psicologico

### Tilt (Descontrol)
Despues de un blunder (>100cp), se miran las 5 jugadas siguientes. Si 3+ consecutivas pierden >50cp, el jugador esta en **tilt**.

### Recuperacion
```
tasa_recuperacion = recuperaciones_exitosas / total_blunders
```
Una recuperacion es exitosa si el ACPL de las 5 jugadas siguientes es menor al 120% del ACPL general.

### Degradacion bajo Presion
Compara como juegas cuando te queda poco tiempo vs cuando tienes tiempo normal:

```
degradacion = ((acpl_bajo_presion - acpl_normal) / acpl_normal) * 100
```

- **Positivo** = juegas peor con poco tiempo (normal, humano)
- **Negativo** = juegas MEJOR con poco tiempo (sospechoso)

Los umbrales de presion dependen del control de tiempo:
- Bullet (<1min): 10 segundos
- Blitz (2-5min): 20 segundos
- Rapidas (10-60min): 60 segundos
- Clasicas: 120 segundos

### Perfiles Psicologicos

El programa clasifica al jugador en uno de estos perfiles:

| Perfil | Significado |
|--------|------------|
| ENGINE_LIKE | Sin tilt, >95% recuperacion, <5% degradacion. Sospechoso. |
| RESILIENT_CLOSER | Buena recuperacion, buen cierre |
| RESILIENT_SHAKY | Buena recuperacion, mal cierre |
| FRAGILE_CLOSER | Mala recuperacion, buen cierre |
| FRAGILE_CRUMBLER | Mala recuperacion, mal cierre |
| PRESSURE_FIGHTER | Maneja bien la presion |
| PRESSURE_VULNERABLE | Se desmorona bajo presion |
| NORMAL_HUMAN | Patrones normales |

---

## 7. Gestion del Tiempo

### Metricas Basicas
- **Tiempo medio por jugada**
- **Desviacion estandar del tiempo**
- **Jugadas rapidas** (<2 segundos)
- **Jugadas lentas** (>30 segundos)

### Correlacion Tiempo-Complejidad

Los humanos tardan mas en posiciones complicadas. El programa compara:

```
ratio = tiempo_medio_en_posiciones_complejas / tiempo_medio_en_posiciones_simples
```

| Ratio | Interpretacion | Puntuacion Anomalia |
|-------|---------------|-------------------|
| >1.5 | Normal (piensas mas en posiciones dificiles) | 0 |
| 1.0-1.5 | Algo raro | 20 |
| <1.0 | Sospechoso (mismo tiempo en todo) | Hasta 100 |

La **complejidad** de una posicion se calcula segun el numero de jugadas legales:
- <5 jugadas = simple (10)
- 5-20 jugadas = moderada (20-50)
- 20-40 jugadas = compleja (50-80)
- 40+ jugadas = muy compleja (80-100)

### Calidad Post-Pausa

Si un jugador hace una pausa larga (>30 segundos) y despues juega significativamente mejor, puede indicar que consulto un motor:

```
mejora = calidad_normal - calidad_post_pausa
```

Positivo = juegas mejor despues de la pausa (sospechoso).

---

## 8. Rachas de Precision (Precision Bursts)

**Que es:** Secuencias de 3+ jugadas consecutivas donde pierdes 10cp o menos en cada una.

| Metrica | Que mide |
|---------|----------|
| burst_count | Numero de rachas |
| longest_burst | Jugadas en la racha mas larga |
| precision_rate | % de jugadas con <10cp de perdida |

Muchas rachas de precision = patron sospechoso de juego perfecto.

---

## 9. Puntuacion de Sospecha (0-200)

Este es el indicador principal. Combina **13 senales** en una sola puntuacion:

### Niveles de Riesgo

| Puntuacion | Nivel | Significado |
|-----------|-------|------------|
| 0-60 | BAJO | Jugador limpio |
| 60-90 | MODERADO | En el limite, monitorear |
| 90-120 | ALTO | Sospechoso, investigar |
| 120-200 | MUY ALTO | Muy probable uso de motor |

### Las 13 Senales (suman puntos)

| # | Senal | Puntos Max | Que detecta |
|---|-------|-----------|------------|
| 1 | Consistencia tiempo-complejidad | 40 | Tiempo constante en toda posicion |
| 2 | Estabilidad entre fases | 30 | No empeorar al avanzar la partida |
| 3 | Resiliencia | 20 | Nunca colapsar |
| 4 | Consistencia en medio juego | 10 | Estabilidad mecanica |
| 5 | Precision antinatural (Robust ACPL) | 40 | ACPL muy bajo (<12-25cp) |
| 6 | Consistencia antinatural (Match Rate) | 20 | Match rate >45-55% |
| 7 | Baja tasa de blunders | 15 | Casi nunca equivocarse |
| 8 | Alto Top-2 match rate | 10 | >80-90% en top 2 |
| 9 | Degradacion bajo presion | 15 | Mejorar bajo presion |
| 10 | Baja tasa de tilt | 10 | Nunca descontrolarse |
| 11 | Mejora apertura-medio juego | 15 | "Enciende el motor" |
| 12 | Caida de varianza | 15 | "Se vuelve mecanico" |
| 13 | Mejora post-pausa | 20 | Consulta durante pausas |

**Maximo teorico:** 260 puntos (pero las penalizaciones lo bajan).

### Penalizaciones (restan puntos)

| Penalizacion | Puntos Max | Por que |
|-------------|-----------|--------|
| Alta tasa de colapso (>30%) | -30 | Patron humano debil, no tramposo |
| Degradacion bajo presion (>+10cp) | -20 | Debilidad humana |
| Alta tasa de blunders (>15%) | -15 | Patron humano |

---

## 10. Analisis Temporal (Multiples Partidas)

Cuando se analizan muchas partidas seguidas, se buscan patrones en ventanas de **20 partidas**:

### Pendiente de ELO
```
pendiente = (elo_final - elo_inicial) / 20
```
- 2-5 pts/partida = subida normal
- >10 pts/partida = sospechoso (subida imposible)

### Rachas de Victorias
- >85% de victorias en 20 partidas = sospechoso
- Incluso jugadores fuertes pierden 20-30% por varianza

### Deteccion de Explosiones de Rendimiento
Se activa cuando 2+ de estas senales coinciden en la misma ventana:
1. Pendiente ELO >= 8 pts/partida
2. Win rate >= 80%
3. ACPL <= 15cp
4. Blunder rate < 5%

---

## 11. Parametros del Motor

| Parametro | Valor |
|-----------|-------|
| Motor | Stockfish |
| Profundidad | 12-14 (por defecto 12) |
| MultiPV | 5 (analiza las 5 mejores variantes) |
| Libro de aperturas | Polyglot (si no hay, salta las primeras 10 jugadas) |
| Valor mate | +/-10000 cp (excluido del ACPL) |

### Valores de Piezas (en centipeones)

| Pieza | Valor |
|-------|-------|
| Peon | 100 |
| Caballo | 320 |
| Alfil | 330 |
| Torre | 500 |
| Dama | 900 |
| Rey | 0 |

---

## Resumen Visual

```
Partida PGN
    |
    v
Motor Stockfish (profundidad 12, 5 variantes)
    |
    v
Metricas por Jugada: cp_loss, rank, jugadas legales, tiempo
    |
    +---> ACPL, Robust ACPL, Blunders
    +---> Match Rates (Top 1-5), Match Final
    +---> Analisis por Fases (apertura/medio/final)
    +---> Perfil Psicologico (tilt, recuperacion, presion)
    +---> Gestion del Tiempo (correlacion, pausas)
    +---> Rachas de Precision
    |
    v
13 Senales de Sospecha + Penalizaciones
    |
    v
PUNTUACION FINAL (0-200)
    |
    v
Veredicto: BAJO / MODERADO / ALTO / MUY ALTO
```
