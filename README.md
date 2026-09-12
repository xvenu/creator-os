# Creator-OS

Autonomous media network. Each product is a **finished, self-contained pulse**
living in its own subdirectory. Pulses share conventions, never code paths.

```
creator-os/
  music-pulse/      ✅ finished product (v0.6.0) — intelligence brain
  shared/           ✅ event_bus, orchestrator, knowledge (used by all pulses)
  football-pulse/   ✅ Zoza client pulse — intelligence → packages → factory
  zoza-factory/     ✅ autonomous production factory (v0.1.0) — Pulse decides WHAT, Zoza decides HOW
```

External systems coordinated (not moved, configured by path):
- Zoza Video Factory (`~/Zoza_anime`, via `ZOZA_DIR`) — production layer;
  MusicPulse dispatches through its own `idea_engine`, tracks jobs/*.json.

## Pulse contract (must hold for every pulse)

1. **Relocatable**: no absolute paths. All file references (templates, `.env`,
   sqlite fallback, compose volumes) are relative to the pulse root.
2. **Self-contained**: own `requirements.txt`, `Dockerfile`, `docker-compose.yml`,
   `migrations/`, `tests/`, `.env.example`.
3. **Independently buildable**: `cd <pulse> && pip install -r requirements.txt &&
   pytest` must pass without the parent project.
4. **Additive phases**: new phases extend, never rewrite, prior functionality.

## Work on a pulse

```bash
cd music-pulse
cp .env.example .env
pip install -r requirements.txt
pytest
uvicorn app.main:app --reload
```

## Add a new pulse (e.g. football-pulse)

```bash
cp -r music-pulse football-pulse   # then rename domain modules, or scaffold fresh
```

Keep the module/plugin/audit/test conventions so the network stays operable.
