# 1. Verificar que el stack sigue corriendo                                                                                                                                
  docker compose ps
                                                                                                                                                                             
  # 2. Si el stack no está arriba, levantarlo
  docker compose up -d

  # 3. Ver el estado actual de Redis (diagnóstico)
  docker compose exec redis redis-cli LLEN dropbox_tasks
  docker compose exec redis redis-cli SCARD visited_folders

  # 4. Borrar el VISITED_SET del run anterior
  #    (sin esto, carpetas ya vistas antes quedarían bloqueadas)
  docker compose exec redis redis-cli DEL visited_folders

  # 5. Sembrar la raíz "/" — contenedor de un solo uso que termina solo
  MODE=PRODUCER docker compose run --rm worker python -m app.main_local

  # 6. Confirmar que la tarea entró a la cola (debe devolver 1)
  docker compose exec redis redis-cli LLEN dropbox_tasks

  ---
  Qué hace cada paso

  ┌──────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ Paso │                                                    Por qué                                                     │
  ├──────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 3    │ Confirmar que la cola está vacía y cuántos paths tenía el VISITED_SET anterior                                 │
  ├──────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 4    │ Sin esto, carpetas que ya pasaron por el run anterior quedan bloqueadas aunque sus vecinas nunca se exploraron │
  ├──────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 5    │ Es el paso que faltó la vez pasada — siembra "/" en Redis para que los workers arranquen desde la raíz         │
  ├──────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 6    │ Verificar que funcionó antes de dejar solos a los workers                                                      │
  └──────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  Una vez que el paso 6 devuelva 1, los 12 workers ya existentes tomarán la tarea automáticamente y harán el fan-out desde la raíz. El UPSERT en la DB es idempotente, así
  que re-indexar carpetas ya vistas no rompe nada — simplemente las actualiza.
