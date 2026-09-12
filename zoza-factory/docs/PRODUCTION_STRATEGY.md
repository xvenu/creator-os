# Production Strategy Report

How the factory decides HOW for each request (`production_strategy.plan`,
orchestrated by `reality_production_director.decide`).

## Inputs

Contract V2 request + candidates (pulse `sources` + `evidence` normalized
with trust scoring, evidence +0.1 and `evidence_backed`, verified +0.2 —
plus factory catalog rows) + `reality_min_trust` (default 0.6, env
`REALITY_MIN_TRUST`; evidence-backed assets bypass the floor).

## Pipeline

1. **Rights gate** (`rights_validation.validate_batch`, mode-aware).
2. **Trust floor** (evidence-backed exempt).
3. **Hierarchy order** real_footage → real_photo → licensed → public_domain → ai_generated, trust desc.
4. **Mode filter** (ONLY/AI-disallowed strip AI; CREATIVE ranks AI first).
5. **AI fallback** only if empty AND allowed (single placeholder, flagged `ai_fallback_injected`).
6. **Voice match** (explicit profile wins; else keyword+audience scoring; documentary fallback).
7. **Timeline build** (word-weighted scenes normalized to exact `length_seconds`).
8. **Plan**: `{strategy, reality_ratio, ai_ratio, asset_sources, estimated_runtime}` + explanation + per-dimension strategies.

## Strategy names

`reality-only` · `ai-creative` · `reality-first-full-reality` ·
`reality-first-mixed` · `hybrid-full-reality` · `hybrid-mix` · `ai-fallback`.

`estimated_runtime = 5.0 + scenes × (2.0 + 3.0 × ai_ratio)` seconds
(deterministic estimate: AI scenes cost ~2x; not a promise).

## Worked example (test `req-e2e-music`, REALITY_FIRST, 60s)

Sources: official photo (0.9, RESTRICTED) + concert footage (0.85, CLEARED);
evidence: Grammy record (0.8+0.1 verified, public-domain, CLEARED) + 4 seed
catalog rows. All clear the rights gate → hierarchy puts concert footage
first → voice `documentary` (explicit) → timeline 60.0s exact →
strategy `reality-first-full-reality`, reality_ratio 1.0.
