# Chemistry archive (retired 2026-08-07)

Single tree for everything not part of the active build. Nothing here is imported
by `clean_chemistry.py` or `build_dashboard.py`. Reversible — moved, not deleted.

- **`validation-tools-2026-07/`** — one-off audit/validation scripts from the
  2026-06/07 taxonomy rounds: `audit_categories.py`, `audit_findings.py`,
  `build_classification_review.py`. Their rulings are baked into `categories.py` /
  `category_corrections.csv`. To run again: from `chemistry/`, they import `categories`/
  `sectors` from `scripts/`, so use `PYTHONPATH=scripts ../microbiology/.venv/bin/python archive/validation-tools-2026-07/<script>.py`.
- **`reports-validation-2026-07/`** — their outputs: 4× `category_location_validation_*.xlsx`
  (~4 MB of validation versions), `category_audit_2026-07-01.{md,xlsx}`,
  `classification_review_2026-07-01.{md,xlsx}`, `classification_review_csv/`,
  `AUDIT_FINDINGS.md`, `chemistry_filter_audit.md`, and the stale
  `chemistry_dashboard.zip`.
- **`misc/`** — stray root reference files, not pipeline inputs: two `.xltx`
  templates (البهارات spices, الحبوب grains) + `Water-analysis-specifications-copy.xlsx`.

The build is verified reproducible without any of these — `clean_chemistry.py
--section all` regenerates all 14 parquets byte-identical.
