#!/usr/bin/env python3
"""
Capture RBC middle-step outputs from the main extraction pipeline.

For each RBC PDF, saves:
- Camelot parsed output from BankStatementExtractor._extract_with_camelot()
- RBC text parser output from BankStatementExtractor._extract_rbc_text_transactions()
- Final output from test_rbc_chequing_complete.extract_rbc_chequing_statement()
"""

from pathlib import Path
import io
import sys
import pandas as pd

from extract_bank_statements import BankStatementExtractor
from test_rbc_chequing_complete import extract_rbc_chequing_statement

# Keep console UTF-8 safe on Windows so emoji logs don't crash exploration.
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _safe_df(obj):
    if obj is None:
        return pd.DataFrame()
    if isinstance(obj, pd.DataFrame):
        return obj
    try:
        return pd.DataFrame(obj)
    except Exception:
        return pd.DataFrame()


def main(folder="data/rbc"):
    pdfs = sorted(Path(folder).glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {folder}")
        return

    out_root = Path(folder) / "debug_rbc_middle_steps"
    out_root.mkdir(exist_ok=True)

    summary = []

    for pdf in pdfs:
        print(f"\n=== {pdf.name} ===")

        extractor = BankStatementExtractor(str(pdf))

        camelot_df = pd.DataFrame()
        text_df = pd.DataFrame()
        final_df = pd.DataFrame()

        camelot_err = ""
        text_err = ""
        final_err = ""

        try:
            camelot_df = _safe_df(extractor._extract_camelot_tables())  # middle step
        except Exception as exc:
            camelot_err = str(exc)

        try:
            text_df = _safe_df(extractor._extract_rbc_text_transactions())  # middle step
        except Exception as exc:
            text_err = str(exc)

        try:
            final_df, opening, closing, year = extract_rbc_chequing_statement(str(pdf))
            final_df = _safe_df(final_df)
        except Exception as exc:
            final_err = str(exc)
            opening = None
            closing = None
            year = None

        out_xlsx = out_root / f"{pdf.stem}_middle_steps.xlsx"
        with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
            if not camelot_df.empty:
                camelot_df.to_excel(writer, sheet_name="camelot_parsed", index=False)
            else:
                pd.DataFrame([{"note": "empty", "error": camelot_err}]).to_excel(
                    writer, sheet_name="camelot_parsed", index=False
                )

            if not text_df.empty:
                text_df.to_excel(writer, sheet_name="text_parsed", index=False)
            else:
                pd.DataFrame([{"note": "empty", "error": text_err}]).to_excel(
                    writer, sheet_name="text_parsed", index=False
                )

            if not final_df.empty:
                final_df.to_excel(writer, sheet_name="final_rbc_complete", index=False)
            else:
                pd.DataFrame([{"note": "empty", "error": final_err}]).to_excel(
                    writer, sheet_name="final_rbc_complete", index=False
                )

            pd.DataFrame(
                [
                    {
                        "file": pdf.name,
                        "bank_detected": extractor.metadata.get("bank"),
                        "is_credit_card": extractor.metadata.get("is_credit_card"),
                        "opening_balance": opening,
                        "closing_balance": closing,
                        "statement_year": year,
                        "camelot_rows": len(camelot_df),
                        "text_rows": len(text_df),
                        "final_rows": len(final_df),
                        "camelot_error": camelot_err,
                        "text_error": text_err,
                        "final_error": final_err,
                    }
                ]
            ).to_excel(writer, sheet_name="summary", index=False)

        summary.append(
            {
                "file": pdf.name,
                "bank_detected": extractor.metadata.get("bank"),
                "camelot_rows": len(camelot_df),
                "text_rows": len(text_df),
                "final_rows": len(final_df),
                "camelot_error": camelot_err,
                "text_error": text_err,
                "final_error": final_err,
            }
        )
        print(f"saved: {out_xlsx.name}")

    summary_path = out_root / "middle_steps_summary.xlsx"
    pd.DataFrame(summary).to_excel(summary_path, index=False)
    print(f"\nSaved summary: {summary_path}")


if __name__ == "__main__":
    main()
