# Rights Validation Report

## Statuses

| Status | Meaning | Usable |
|---|---|---|
| CLEARED | Cleared for production use | Yes (+ license-derived restrictions) |
| RESTRICTED | Usable within restrictions | Yes (attribution-required, non-commercial, editorial-only, geo-*) |
| UNKNOWN | Rights unknown | Flagged (`needs_review`); **excluded from REALITY_ONLY**, allowed elsewhere |
| BLOCKED | Prohibited (`prohibited/do-not-use/embargoed` markers or explicit) | **Never, in any mode** |

## Rules (`rights_validation.validator`)

- Classification is a pure function of `(rights_status, license)`.
- `validate_batch` separates usable/blocked; blocked items are reported, never silently dropped.
- Mode gate `is_usable`: BLOCKED→False always; UNKNOWN→False only under REALITY_ONLY.

## Test evidence

- `test_rights_blocked_assets_excluded` — BLOCKED unusable in every mode.
- `test_rights_unknown_flagged_and_excluded_from_reality_only` — UNKNOWN flagged, mode-split.
- `test_rights_batch_blocks_violations` — 1 usable / 1 blocked out of 2; violator named in report.
- Mode tests confirm blocked pulse sources never reach any timeline.
