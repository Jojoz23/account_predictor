#!/usr/bin/env python3
"""
RBC routing/extraction diagnostics.

Purpose:
- Verify whether RBC chequing PDFs are detected by RBCChequingExtractor
- Compare specialized extractor vs GenericExtractor transaction counts
- Show which files would fail if routed strictly to specialized extractor
"""

from pathlib import Path
import traceback
import pandas as pd
import pdfplumber

from test_rbc_chequing_complete import extract_rbc_chequing_statement
from extract_bank_statements import BankStatementExtractor


def detect_rbc_chequing_like_current(pdf_path: str) -> bool:
    """
    Mirror current logic in extractors/rbc_chequing_extractor.py detect_bank().
    Kept local to avoid extractor import cycles in standalone diagnostics.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            if not first_page_text:
                return False

            first_page_text_lower = first_page_text.lower()

            if "toronto-dominion" in first_page_text_lower or "td bank" in first_page_text_lower:
                return False

            has_rbc = "royal bank" in first_page_text_lower or "rbc" in first_page_text_lower
            has_chequing = "chequing" in first_page_text_lower or "business account" in first_page_text_lower
            has_account_activity = "account activity" in first_page_text_lower

            has_transaction_headers = (
                "date" in first_page_text_lower
                and ("description" in first_page_text_lower or "debits" in first_page_text_lower)
                and ("balance" in first_page_text_lower or "credits" in first_page_text_lower)
            )

            is_not_credit_card = (
                "credit card" not in first_page_text_lower and "mastercard" not in first_page_text_lower
            )

            return has_rbc and (has_chequing or has_account_activity) and has_transaction_headers and is_not_credit_card
    except Exception:
        return False


def run_rbc_routing_diagnostics(pdf_folder: str = "data/rbc") -> pd.DataFrame:
    folder = Path(pdf_folder)
    pdf_files = sorted(folder.glob("*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in: {folder}")
        return pd.DataFrame()

    rows = []
    print("=" * 90)
    print("RBC ROUTING DIAGNOSTICS")
    print("=" * 90)
    print(f"Folder: {folder}")
    print(f"PDF count: {len(pdf_files)}")
    print("")

    for idx, pdf in enumerate(pdf_files, start=1):
        print(f"[{idx}/{len(pdf_files)}] {pdf.name}")

        detect_ok = False
        rbc_success = False
        generic_success = False
        rbc_rows = 0
        generic_rows = 0
        rbc_error = ""
        generic_error = ""

        try:
            detect_ok = bool(detect_rbc_chequing_like_current(str(pdf)))
        except Exception as exc:
            rbc_error = f"detect_bank error: {exc}"

        try:
            rbc_df, _, _, _ = extract_rbc_chequing_statement(str(pdf))
            rbc_success = bool(rbc_df is not None and not rbc_df.empty)
            rbc_rows = len(rbc_df) if rbc_df is not None else 0
            if not rbc_success:
                rbc_error = "No rows extracted"
        except Exception as exc:
            rbc_error = f"extract error: {exc}"

        try:
            generic_extractor = BankStatementExtractor(str(pdf))
            generic_df = generic_extractor.extract()
            generic_success = bool(generic_df is not None and not generic_df.empty)
            generic_rows = len(generic_df) if generic_df is not None else 0
            if not generic_success:
                generic_error = "No rows extracted"
        except Exception as exc:
            generic_error = f"extract error: {exc}"

        preferred = "RBCChequingExtractor" if rbc_success else ("GenericExtractor" if generic_success else "FAILED")

        print(
            f"  detect={detect_ok} | "
            f"rbc: success={rbc_success}, rows={rbc_rows} | "
            f"generic: success={generic_success}, rows={generic_rows} | "
            f"preferred={preferred}"
        )
        if rbc_error:
            print(f"  rbc_error: {rbc_error}")
        if generic_error:
            print(f"  generic_error: {generic_error}")

        rows.append(
            {
                "file": pdf.name,
                "rbc_detect_bank": detect_ok,
                "rbc_success": rbc_success,
                "rbc_rows": rbc_rows,
                "rbc_error": rbc_error,
                "generic_success": generic_success,
                "generic_rows": generic_rows,
                "generic_error": generic_error,
                "preferred_extractor": preferred,
            }
        )
        print("")

    df = pd.DataFrame(rows)

    print("=" * 90)
    print("SUMMARY")
    print("=" * 90)
    print(f"Detected by RBC extractor: {int(df['rbc_detect_bank'].sum())}/{len(df)}")
    print(f"RBC extractor successful:  {int(df['rbc_success'].sum())}/{len(df)}")
    print(f"Generic successful:        {int(df['generic_success'].sum())}/{len(df)}")
    print(f"Preferred RBC extractor:   {int((df['preferred_extractor'] == 'RBCChequingExtractor').sum())}/{len(df)}")
    print(f"Preferred Generic:         {int((df['preferred_extractor'] == 'GenericExtractor').sum())}/{len(df)}")
    print(f"Failed both:               {int((df['preferred_extractor'] == 'FAILED').sum())}/{len(df)}")

    out_path = folder / "rbc_routing_diagnostics.xlsx"
    df.to_excel(out_path, index=False)
    print("")
    print(f"Saved detailed report: {out_path}")

    return df


if __name__ == "__main__":
    try:
        run_rbc_routing_diagnostics("data/rbc")
    except Exception:
        print("Fatal error while running diagnostics:")
        traceback.print_exc()
