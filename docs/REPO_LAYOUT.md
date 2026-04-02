# Repository layout

Organized so the **root stays minimal** and scripts still work from the project folder.

**Moving data files (PDF, Excel, IIF, CSV) into `data/` or `archive/` does not affect extractors or tests.** Extractors import only Python modules from the project root (`standardized_bank_extractors`, `test_*_complete`). Run tests from the project root, e.g. `python tests/test_standardized_extractors.py`.

## Root (main scripts & code)

| Item | Purpose |
|------|--------|
| `process_to_excel.py` | PDF → combined Excel (run this first) |
| `excel_to_iif.py` | Excel → QuickBooks IIF |
| `update_iif_account_names.py` | Map account names + set types from Accounts.TXT |
| `remove_duplicate_transfers.py` | Strip duplicate transfers between bank and card IIFs |
| `standardized_bank_extractors.py` | Routes PDFs to the right bank/card extractor |
| `extract_bank_statements.py` | Fallback PDF extractor (used by generic extractor) |
| `scripts/pdf_to_quickbooks.py` | AI account prediction pipeline |
| `streamlit_app.py` | Web UI (Bookeepifier; adds `scripts/` to path for that import) |
| `scripts/batch_predict*.py`, `scripts/create_accounts_iif.py`, `scripts/compare_credit_card_excels.py` | Optional / batch helpers |
| `extractors/` | Per-bank PDF extractors (BMO, TD, Scotia, etc.) |
| `tools/` | Utilities (e.g. `analyze_statement.py`) |
| `notebooks/` | Jupyter notebooks |
| `README.md`, `requirements.txt`, `.gitignore` | Project root |

## config/

QuickBooks-related config. Scripts look here if files aren’t in the project root.

| File | Purpose |
|------|--------|
| `account_names_map.csv` | Statement account name → QB account name |
| `Accounts.TXT` | QB Chart of Accounts export (for ACCNT types) |
| `Accounts - 980.TXT` | Optional company-specific chart (e.g. 980) |

You can keep copies in **root** instead; `update_iif_account_names.py` checks root first, then `config/`.

## docs/

Documentation and reference.

| Item | Purpose |
|------|--------|
| `HOW_IT_WORKS.md` | Pipeline overview |
| `BANK_FORMAT_PIPELINE.md`, `CREDIT_CARD_MODEL_EXPECTATIONS.md` | Format and model notes |
| `DEPLOYMENT.md`, `ADDING_NEW_BANK_GUIDE.md`, `SCOTIA_VISA_FINDINGS.md` | Deployment and bank-specific notes |
| `IIF_Import_Kit/` | QuickBooks IIF reference (examples + header help) |

## tests/

Test runners and batch verification. **Run from project root**, e.g.:

```bash
python tests/test_all_scotia_visa.py
python tests/test_standardized_extractors.py
python tests/run_all_bmo_verify_balances.py
```

The `test_*_complete.py` files stay in **root** because extractors import them.

## data/

Input and generated data (root is kept clear of these):

| Subfolder | Use |
|-----------|-----|
| `data/pdfs/` | Statement PDFs (or use any folder when running `process_to_excel.py "path/to/folder"`) |
| `data/excel/` | Combined/source Excel files |
| `data/iif/` | Optional: extra IIF exports |

Scripts do not assume paths inside `data/`; you pass paths as arguments. `.gitignore` ignores `data/` so these files are not committed.

## archive/

Old or one-off outputs (safe to delete to free space):

- `archive/iif/` — Error IIFs from QuickBooks, timestamped combined IIFs
- `archive/excel/` — Old combined Excels
- `archive/pdfs/` — Old statement PDFs if you move them here
- `archive/csv/` — Reports like `compare_duplicates_report.csv`

Only the two “current” IIFs stay in root: `BMO_Business_Che_7779_mapped.iif` and `BMO_Credit_Card_2589_mapped_no_xfer.iif` (or your chosen names).

`.gitignore` excludes `data/`, generated patterns like `*_combined_*.xlsx`, and optional error IIF patterns.
