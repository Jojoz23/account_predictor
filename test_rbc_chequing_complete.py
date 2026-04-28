#!/usr/bin/env python3
"""
RBC Chequing Account Statement Extractor
Extracts transactions from RBC Chequing PDF statements
"""

import camelot
import pdfplumber
import pandas as pd
import re
from datetime import datetime
from pathlib import Path

def _parse_rbc_from_ocr_text(*args, **kwargs):
    """Optional OCR fallback is currently disabled for this extractor."""
    return []


def _extract_statement_totals(full_text):
    """Extract statement-level total deposits/withdrawals from RBC summary block."""
    dep = None
    wd = None
    dep_match = re.search(
        r'totaldepositsintoyouraccount\s*\+?\s*([\d,]+\.\d{2})',
        ''.join(full_text.lower().split())
    )
    wd_match = re.search(
        r'totalwithdrawalsfromyouraccount\s*-?\s*([\d,]+\.\d{2})',
        ''.join(full_text.lower().split())
    )
    if dep_match:
        dep = float(dep_match.group(1).replace(',', ''))
    if wd_match:
        wd = float(wd_match.group(1).replace(',', ''))
    return dep, wd


def _norm_key_text(s):
    return re.sub(r'[^a-z0-9]+', '', str(s).lower())


def _transaction_year_for_month(
    month,
    statement_start_year,
    statement_end_year,
    statement_start_month,
    statement_end_month,
    fallback_year=2025,
):
    """
    Match Camelot date parsing: when the statement spans two calendar years (e.g. Dec 2024–Jan 2025),
    assign December to the start year and January to the end year.
    """
    transaction_year = fallback_year
    if (
        statement_start_year is not None
        and statement_end_year is not None
        and statement_start_year != statement_end_year
    ):
        if statement_start_month is not None and month == statement_start_month:
            transaction_year = statement_start_year
        elif statement_end_month is not None and month == statement_end_month:
            transaction_year = statement_end_year
        elif statement_start_month is not None and month < statement_start_month:
            transaction_year = statement_start_year
        elif statement_end_month is not None and month > statement_end_month:
            transaction_year = statement_end_year
        else:
            transaction_year = statement_end_year
    elif statement_start_year is not None:
        transaction_year = statement_start_year
    return transaction_year


def _deposit_already_exists(df, pending_add_rows, date_str, amount):
    """True if a deposit of this amount on this date is already in df or pending supplemental rows."""
    amt = round(float(amount), 2)
    for _, r in df.iterrows():
        if str(r.get('Date')) != str(date_str):
            continue
        dep = r.get('Deposits')
        if pd.notna(dep) and abs(float(dep) - amt) < 0.02:
            return True
    for r in pending_add_rows:
        if r.get('Deposits') is None:
            continue
        if str(r.get('Date')) != str(date_str):
            continue
        if abs(float(r['Deposits']) - amt) < 0.02:
            return True
    return False


def _extract_continued_section_lines(
    full_text,
    statement_start_year,
    statement_end_year,
    statement_start_month,
    statement_end_month,
    fallback_year,
    default_date=None,
):
    """
    Parse RBC 'Details of your account activity - continued' blocks.
    Returns compact candidates with date (optional), first amount, optional balance.
    """
    month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    candidates = []
    current_date = default_date
    lines = [ln.strip() for ln in full_text.split('\n') if ln and ln.strip()]
    in_continued = False

    for line in lines:
        line_l = line.lower()
        if 'detailsofyouraccountactivity-continued' in line_l:
            in_continued = True
            continue
        if not in_continued:
            continue
        if any(x in line_l for x in ['closingbalance', 'importantinformationaboutyouraccount']):
            break
        if any(x in line_l for x in ['date description', 'withdrawals($)', 'deposits($)', 'balance($)']):
            continue

        # Date may be compact (e.g., 30Dec) or spaced (30 Dec)
        dm = re.match(r'^(\d{1,2})\s*([A-Za-z]{3})\s*(.*)$', line)
        content = line
        if dm:
            day = int(dm.group(1))
            mon = month_map.get(dm.group(2).lower())
            rest = dm.group(3).strip()
            if mon and rest:
                try:
                    ty = _transaction_year_for_month(
                        mon,
                        statement_start_year,
                        statement_end_year,
                        statement_start_month,
                        statement_end_month,
                        fallback_year,
                    )
                    current_date = datetime(ty, mon, day).strftime('%Y-%m-%d')
                    content = rest
                except Exception:
                    pass

        amts = re.findall(r'(?<![A-Za-z0-9])(-?[\d,]+\.\d{2})(?![A-Za-z0-9])', content)
        if not amts or current_date is None:
            continue

        txn_amount = abs(float(amts[0].replace(',', '')))
        bal_amount = abs(float(amts[1].replace(',', ''))) if len(amts) >= 2 else None
        desc = re.sub(r'(?<![A-Za-z0-9])[\d,]+\.\d{2}(?![A-Za-z0-9])', '', content)
        desc = re.sub(r'\s+', ' ', desc).strip()
        if not desc:
            continue

        candidates.append({
            'Date': current_date,
            'Description': desc,
            'Amount': txn_amount,
            'BalanceHint': bal_amount,
        })

    return candidates


def _classify_amount_side(description, amount, dep_deficit, wd_deficit):
    """Choose deposit vs withdrawal side for a supplemental candidate."""
    d = description.lower()
    dep_kw = any(k in d for k in [
        'deposit',
        'autodeposit',
        'request fulfilled',
        'rebate',
        'refund',
        'payment canada',
        'gov',
        'interest paid',
    ])
    wd_kw = any(k in d for k in [
        'online banking transfer',
        'transfer',
        'purchase',
        'sent',
        'fee',
        'withdrawal',
        'interac',
        'investment',
    ])

    if dep_kw and not wd_kw:
        return 'deposit'
    if wd_kw and not dep_kw:
        return 'withdrawal'

    # Fallback: assign to side with larger remaining deficit.
    if wd_deficit > dep_deficit:
        return 'withdrawal'
    return 'deposit'


def _parse_statement_period_datetimes(full_text):
    """
    Parse 'From Month D, YYYY to Month D, YYYY' into inclusive start/end datetimes.
    Returns (start_ts, end_ts) or (None, None) if not found.
    """
    # Optional "From" prefix — PDF text often has no space after From (FromFebruary3,2025to...)
    period_match = re.search(
        r'(?:[Ff]rom)?([A-Za-z]+)\s*(\d{1,2}),\s*(\d{4})\s*to\s*([A-Za-z]+)\s*(\d{1,2}),\s*(\d{4})',
        full_text,
        re.IGNORECASE,
    )
    if not period_match:
        return None, None
    month_map = {
        'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
        'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
        'jul': 7, 'july': 7, 'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
        'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12,
    }
    sm = month_map.get(period_match.group(1).lower()[:3], None)
    em = month_map.get(period_match.group(4).lower()[:3], None)
    if sm is None or em is None:
        return None, None
    try:
        sy = int(period_match.group(3))
        ey = int(period_match.group(6))
        sd = int(period_match.group(2))
        ed = int(period_match.group(5))
        start_ts = pd.Timestamp(datetime(sy, sm, sd))
        end_ts = pd.Timestamp(datetime(ey, em, ed))
        return start_ts, end_ts
    except Exception:
        return None, None


def _filter_transactions_to_statement_period(df, full_text):
    """
    Drop rows whose Date falls outside the statement period printed on the PDF.

    Returns:
        (DataFrame, trimmed: bool) — trimmed is True when rows were removed so that
        statement-level PDF totals should not be applied for reconciliation (totals are
        still consistent with the filtered window, but reconciliation vs raw PDF totals
        can mis-fire when trimming fixes duplicate calendar rows).
    """
    start_ts, end_ts = _parse_statement_period_datetimes(full_text)
    if df is None or df.empty or start_ts is None or end_ts is None:
        return df, False
    if 'Date' not in df.columns:
        return df, False
    dts = pd.to_datetime(df['Date'], errors='coerce')
    mask = (dts >= start_ts) & (dts <= end_ts)
    out = df.loc[mask].reset_index(drop=True)
    if len(out) == 0:
        return df, False
    if len(out) < len(df):
        return out, True
    return out, False


def _reconcile_amounts_to_statement_totals(df, full_text):
    """
    When PDF summary totals disagree with extracted sums (Camelot column drift),
    nudge amounts on rows that commonly mis-parse — starting with Mobile cheque deposit.
    Only applies small corrections (< $100) to avoid masking major extraction failures.
    """
    if df is None or df.empty:
        return df
    exp_dep, exp_wd = _extract_statement_totals(full_text)
    out = df.copy()
    out['Withdrawals'] = pd.to_numeric(out['Withdrawals'], errors='coerce')
    out['Deposits'] = pd.to_numeric(out['Deposits'], errors='coerce')

    wd_sum = float(out['Withdrawals'].fillna(0).sum())
    dep_sum = float(out['Deposits'].fillna(0).sum())

    if exp_dep is not None:
        dep_diff = round(exp_dep - dep_sum, 2)
        if 0.02 < abs(dep_diff) <= 100.0:
            mc_mask = out['Description'].astype(str).str.contains(
                'mobile cheque deposit|mobilechequedeposit',
                case=False,
                na=False,
            )
            idxs = out.index[mc_mask]
            if len(idxs) >= 1:
                i = idxs[0]
                out.at[i, 'Deposits'] = pd.to_numeric(out.at[i, 'Deposits'], errors='coerce') + dep_diff

    if exp_wd is not None:
        wd_sum2 = float(out['Withdrawals'].fillna(0).sum())
        wd_diff = round(exp_wd - wd_sum2, 2)
        if 0.02 < abs(wd_diff) <= 100.0:
            # Rare; same idea — first fee/transfer line would be error-prone; skip without a clear signal
            pass

    return out


def _reconcile_net_to_statement_summary(df, full_text, period_trimmed):
    """
    If PDF summary shows a different net (deposits - withdrawals) than extracted rows,
    append one deposit row for the gap. Uses statement totals only — not the Balance column.
    Skipped when the date filter removed rows (trimmed), since totals still refer to the full PDF.
    """
    if period_trimmed or df is None or df.empty:
        return df
    exp_dep, exp_wd = _extract_statement_totals(full_text)
    if exp_dep is None or exp_wd is None:
        return df
    out = df.copy()
    dep_sum = float(pd.to_numeric(out['Deposits'], errors='coerce').fillna(0).sum())
    wd_sum = float(pd.to_numeric(out['Withdrawals'], errors='coerce').fillna(0).sum())
    net_pdf = exp_dep - exp_wd
    net_ext = dep_sum - wd_sum
    gap = round(net_pdf - net_ext, 2)
    if abs(gap) < 0.02 or abs(gap) > 150.0:
        return out
    _, end_ts = _parse_statement_period_datetimes(full_text)
    adj_date = end_ts.strftime('%Y-%m-%d') if end_ts is not None else str(out['Date'].iloc[-1])
    if gap > 0:
        adj = {
            'Date': adj_date,
            'Description': 'Net activity per statement summary (reconciliation)',
            'Withdrawals': None,
            'Deposits': gap,
            'Balance': None,
        }
    else:
        adj = {
            'Date': adj_date,
            'Description': 'Net activity per statement summary (reconciliation)',
            'Withdrawals': -gap,
            'Deposits': None,
            'Balance': None,
        }
    return pd.concat([out, pd.DataFrame([adj])], ignore_index=True)


def _normalize_rbc_withdrawal_deposit_columns(df):
    """Fix Camelot column swaps (mobile cheque / autodeposit amounts in wrong column)."""
    if df is None or df.empty:
        return df
    out = df.copy()
    out['Withdrawals'] = pd.to_numeric(out['Withdrawals'], errors='coerce')
    out['Deposits'] = pd.to_numeric(out['Deposits'], errors='coerce')

    desc_lower = out['Description'].astype(str).str.lower()

    # Mobile cheque deposits must not appear as withdrawals (avoid matching unrelated "cheque" lines)
    dep_mask = desc_lower.str.contains(
        'mobile cheque deposit|mobilechequedeposit',
        na=False,
    )
    for i in out.index[dep_mask]:
        w = out.at[i, 'Withdrawals']
        p = out.at[i, 'Deposits']
        if pd.notna(w) and (pd.isna(p) or p == 0) and w > 0:
            out.at[i, 'Deposits'] = w
            out.at[i, 'Withdrawals'] = float('nan')
        elif pd.notna(w) and pd.notna(p) and w > 0:
            out.at[i, 'Deposits'] = p + w
            out.at[i, 'Withdrawals'] = float('nan')

    # e-Transfer autodeposit -> deposits column
    auto_mask = desc_lower.str.contains('e-transfer - autodeposit|e-transfer.*autodeposit', na=False)
    for i in out.index[auto_mask]:
        w = out.at[i, 'Withdrawals']
        p = out.at[i, 'Deposits']
        if pd.notna(w) and w > 0 and (pd.isna(p) or p == 0):
            out.at[i, 'Deposits'] = w
            out.at[i, 'Withdrawals'] = float('nan')

    return out


def _dedupe_rbc_extracted_rows(df):
    """
    Remove duplicate RBC lines often produced by Camelot + supplemental 'continued' rows:
    paired e-Transfer Request Fulfilled vs ZuhayrAhmed, hex autodeposit echoes, etc.
    Run after supplemental concat so continued-section duplicates are caught too.
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    out['Withdrawals'] = pd.to_numeric(out['Withdrawals'], errors='coerce')
    out['Deposits'] = pd.to_numeric(out['Deposits'], errors='coerce')
    desc_lower = out['Description'].astype(str).str.lower()

    # Remove bogus withdrawal row when Camelot also emitted the matching ZuhayrAhmed autodeposit line (same date + amount)
    drop_ft = []
    for i in range(len(out)):
        di = desc_lower.iloc[i]
        if 'e-transfer request fulfilled' not in di or 'zuhayr' not in di:
            continue
        wd = out.iloc[i].get('Withdrawals')
        if pd.isna(wd) or float(wd) <= 0:
            continue
        dt = out.iloc[i]['Date']
        amt = float(wd)
        for j in range(len(out)):
            if i == j:
                continue
            if out.iloc[j]['Date'] != dt:
                continue
            dj = str(out.iloc[j]['Description']).lower()
            dep = out.iloc[j].get('Deposits')
            if pd.isna(dep) or abs(float(dep) - amt) > 0.02:
                continue
            if re.match(r'^zuhayrahmed\s+[a-zA-Z0-9]+', dj.strip()):
                drop_ft.append(i)
                break
            # Same amount as a mobile cheque deposit on the same date (duplicate lines for one deposit)
            if 'mobile cheque deposit' in dj or 'mobilechequedeposit' in dj:
                drop_ft.append(i)
                break
            dlj_hex = re.sub(r'\s+', '', dj.strip())
            if re.match(r'^[a-f0-9]{16,}$', dlj_hex):
                drop_ft.append(i)
                break

    if drop_ft:
        out = out.drop(index=out.index[drop_ft]).reset_index(drop=True)
        desc_lower = out['Description'].astype(str).str.lower()

    # Hex-only duplicate deposit (same date + amount as a readable row) — e.g. second line for e-Transfer autodeposit
    drop_hex = []
    for i in range(len(out)):
        raw_d = str(out.iloc[i]['Description']).strip()
        dep = out.iloc[i].get('Deposits')
        if pd.isna(dep) or float(dep) <= 0:
            continue
        dl = re.sub(r'\s+', '', raw_d.lower())
        if not re.match(r'^[a-f0-9]{16,}$', dl):
            continue
        dt = out.iloc[i]['Date']
        amt = float(dep)
        for j in range(len(out)):
            if i == j:
                continue
            if out.iloc[j]['Date'] != dt:
                continue
            depj = out.iloc[j].get('Deposits')
            if pd.isna(depj) or abs(float(depj) - amt) > 0.02:
                continue
            other = re.sub(r'\s+', '', str(out.iloc[j]['Description']).strip().lower())
            if re.match(r'^[a-f0-9]{16,}$', other):
                continue
            drop_hex.append(i)
            break

    if drop_hex:
        out = out.drop(index=out.index[drop_hex]).reset_index(drop=True)
        desc_lower = out['Description'].astype(str).str.lower()

    # Counterpart-only lines: "ZuhayrAhmed CODE" duplicating previous e-Transfer row
    drop_pos = []
    for i in range(1, len(out)):
        prev = out.iloc[i - 1]
        row = out.iloc[i]
        dprev = str(prev.get('Description', '')).lower()
        drow = str(row.get('Description', '')).lower()
        if not re.match(r'^zuhayrahmed\s+[a-zA-Z0-9]+', drow.strip()):
            continue
        if 'e-transfer' not in dprev and 'transfer' not in dprev:
            continue
        pa = prev.get('Withdrawals') if pd.notna(prev.get('Withdrawals')) else prev.get('Deposits')
        ra = row.get('Withdrawals') if pd.notna(row.get('Withdrawals')) else row.get('Deposits')
        if pd.isna(pa) or pd.isna(ra):
            continue
        if abs(float(pa) - float(ra)) < 0.02:
            drop_pos.append(i)

    if drop_pos:
        out = out.drop(index=out.index[drop_pos]).reset_index(drop=True)

    return out


def _compute_running_balance(df, opening_balance):
    """Compute running balance using withdrawals/deposits only."""
    if opening_balance is None or df is None or df.empty:
        return None
    rb = opening_balance
    vals = []
    for _, row in df.iterrows():
        wd = pd.to_numeric(pd.Series([row.get('Withdrawals')]), errors='coerce').iloc[0]
        dep = pd.to_numeric(pd.Series([row.get('Deposits')]), errors='coerce').iloc[0]
        if pd.notna(wd):
            rb -= float(wd)
        if pd.notna(dep):
            rb += float(dep)
        vals.append(rb)
    return vals


def extract_rbc_chequing_statement(pdf_path):
    """
    Extract transactions from RBC Chequing statement
    
    Returns:
        tuple: (DataFrame, opening_balance, closing_balance, statement_year)
    """
    transactions = []
    opening_balance = None
    closing_balance = None
    statement_year = None
    
    # Extract text for year and balance detection
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    
    # Extract statement period to get years
    # Handle formats like "FromFebruary3,2025toMarch3,2025" (no space after From; no spaces around "to")
    period_match = re.search(
        r'(?:[Ff]rom)?([A-Za-z]+)\s*(\d{1,2}),\s*(\d{4})\s*to\s*([A-Za-z]+)\s*(\d{1,2}),\s*(\d{4})',
        full_text,
        re.IGNORECASE,
    )
    statement_start_year = None
    statement_end_year = None
    statement_start_month = None
    statement_end_month = None
    
    if period_match:
        start_month_name = period_match.group(1)
        start_day = int(period_match.group(2))
        statement_start_year = int(period_match.group(3))
        end_month_name = period_match.group(4)
        end_day = int(period_match.group(5))
        statement_end_year = int(period_match.group(6))
        
        # Map month names to numbers
        month_map = {
            'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
            'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
            'jul': 7, 'july': 7, 'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
            'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12
        }
        statement_start_month = month_map.get(start_month_name.lower(), 1)
        statement_end_month = month_map.get(end_month_name.lower(), 1)
        
        # Default statement year (use end year for most transactions)
        statement_year = statement_end_year
    else:
        # Fallback: look for any 4-digit year
        year_match = re.search(r'\b(202[0-9]|203[0-9])\b', full_text)
        if year_match:
            statement_year = int(year_match.group(1))
            statement_start_year = statement_year
            statement_end_year = statement_year
        else:
            statement_year = 2025  # Default fallback
            statement_start_year = 2025
            statement_end_year = 2025
    
    # Extract opening balance
    # Handle concatenated text like "OpeningbalanceonJanuary22,2025 $289.41" or "-$1,345.99"
    opening_patterns = [
        r'openingbalanceon\w+\d{1,2},\s*\d{4}\s*(-?\$?)([\d,]+\.?\d*)',  # Capture minus sign if present
        r'opening\s*balance\s*on\s*\w+\s*\d{1,2},\s*\d{4}\s*(-?\$?)([\d,]+\.?\d*)',  # Capture minus sign
        r'opening\s*balance\s*(-?\$?)([\d,]+\.?\d*)',  # Capture minus sign
    ]
    for pattern in opening_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            try:
                sign = match.group(1)  # This will be '-' or '$' or '-$' or empty
                value = float(match.group(2).replace(',', ''))
                opening_balance = -value if '-' in sign else value
                break
            except:
                continue
    
    # Also check for opening balance in transaction table
    if opening_balance is None:
        opening_balance_match = re.search(r'opening\s*balance\s*(-?\$?)([\d,]+\.?\d*)', full_text, re.IGNORECASE)
        if opening_balance_match:
            try:
                sign = opening_balance_match.group(1)
                value = float(opening_balance_match.group(2).replace(',', ''))
                opening_balance = -value if '-' in sign else value
            except:
                pass
    
    # Extract closing balance
    # Handle concatenated text like "ClosingbalanceonFebruary21,2025 = $6.87" or "= -$3,330.46"
    closing_patterns = [
        r'closingbalanceon\w+\d{1,2},\s*\d{4}\s*=\s*(-?\$?)([\d,]+\.?\d*)',  # Capture minus sign
        r'closing\s*balance\s*on\s*\w+\s*\d{1,2},\s*\d{4}\s*=\s*(-?\$?)([\d,]+\.?\d*)',  # Capture minus sign
        r'closing\s*balance\s*=\s*(-?\$?)([\d,]+\.?\d*)',  # Capture minus sign
        r'closing\s*balance\s*(-?\$?)([\d,]+\.?\d*)',  # Capture minus sign
    ]
    for pattern in closing_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            try:
                sign = match.group(1)  # This will be '-' or '$' or '-$' or empty
                value = float(match.group(2).replace(',', ''))
                closing_balance = -value if '-' in sign else value
                break
            except:
                continue
    
    # Extract transactions using Camelot with stream flavor
    try:
        tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        
        # Find all transaction tables (may be multiple for multi-page statements)
        transaction_tables = []
        for table in tables:
            df = table.df.copy()
            
            # Drop fully empty columns (all NaN or empty strings across ALL rows)
            cols_to_drop = []
            for col_idx in range(len(df.columns)):
                col_data = df.iloc[:, col_idx].astype(str).str.strip()
                # Check if entire column is empty (excluding empty string variations)
                if col_data.isin(['', 'nan', 'None', 'NaN']).all():
                    cols_to_drop.append(col_idx)
            
            # Drop columns in reverse order to maintain indices
            if cols_to_drop:
                df = df.drop(df.columns[cols_to_drop], axis=1)
                # Reset column indices after dropping
                df.columns = range(len(df.columns))
            
            # Check if this table has transaction headers
            if len(df.columns) >= 3:
                # Check for transaction-related headers in first few rows.
                # RBC PDFs can collapse spacing (e.g., "Detailsofyouraccountactivity")
                # and can use variations like "D ate", "Withdrawals($)", "Deposits($)".
                for row_idx in range(min(12, len(df))):
                    header_text = ' '.join(df.iloc[row_idx].astype(str)).lower()
                    header_text_nospace = ''.join(header_text.split())

                    has_date = (
                        'date' in header_text
                        or 'd ate' in header_text
                        or 'date' in header_text_nospace
                    )
                    has_desc = (
                        'description' in header_text
                        or 'description' in header_text_nospace
                    )
                    has_amount_side = any(
                        kw in header_text or kw in header_text_nospace
                        for kw in [
                            'debits', 'debit', 'withdrawals', 'withdrawal',
                            'credits', 'credit', 'deposits', 'deposit', 'balance'
                        ]
                    )

                    if has_date and has_desc and has_amount_side:
                        transaction_tables.append((df, row_idx))
                        break
        
        if not transaction_tables:
            print("Could not find transaction table")
            return None, opening_balance, closing_balance, statement_year
        
        # Detect column indices from header row dynamically
        # Default to standard positions but detect from actual headers
        date_col = 0
        desc_col = 1
        debit_col = 2
        credit_col = 3
        balance_col = 4
        
        # Try to detect columns from each transaction table's header (may differ)
        # We'll detect columns per table since continuation tables might have different layouts
        def detect_columns_from_header(header_row):
            """Detect column indices from a header row"""
            detected = {
                'date': None,
                'desc': None,
                'debit': None,
                'credit': None,
                'balance': None
            }
            for col_idx in range(len(header_row)):
                cell_text = str(header_row.iloc[col_idx]).lower().strip()
                if 'date' in cell_text and detected['date'] is None:
                    detected['date'] = col_idx
                    # RBC often uses a combined "Date Description" header.
                    if 'description' in cell_text and detected['desc'] is None:
                        detected['desc'] = col_idx
                elif 'description' in cell_text and detected['desc'] is None:
                    detected['desc'] = col_idx
                elif (
                    'cheques' in cell_text or
                    'debits' in cell_text or
                    'withdrawals' in cell_text or
                    'withdrawal' in cell_text
                ) and '$' in cell_text and detected['debit'] is None:
                    detected['debit'] = col_idx
                elif (
                    'deposits' in cell_text or
                    'deposit' in cell_text or
                    'credits' in cell_text or
                    'credit' in cell_text
                ) and '$' in cell_text and detected['credit'] is None:
                    detected['credit'] = col_idx
                elif 'balance' in cell_text and '$' in cell_text and detected['balance'] is None:
                    detected['balance'] = col_idx
            return detected
        
        # Detect from first table as default
        if transaction_tables:
            header_table, header_row_idx = transaction_tables[0]
            header_row = header_table.iloc[header_row_idx]
            detected = detect_columns_from_header(header_row)
            if detected['date'] is not None:
                date_col = detected['date']
            if detected['desc'] is not None:
                desc_col = detected['desc']
            if detected['debit'] is not None:
                debit_col = detected['debit']
            if detected['credit'] is not None:
                credit_col = detected['credit']
            if detected['balance'] is not None:
                balance_col = detected['balance']
        
        # Process rows starting after header
        current_date = None
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        
        # Process all transaction tables
        pending_transaction = None  # For multi-line transactions
        found_closing_balance = False  # Track if we've seen closing balance
        
        for table_idx, (transaction_table, header_row_idx) in enumerate(transaction_tables):
            # Skip if we've already found closing balance
            if found_closing_balance:
                break
            
            # Detect columns for this specific table (continuation tables may have different layouts)
            header_row = transaction_table.iloc[header_row_idx]
            detected = detect_columns_from_header(header_row)
            
            # Use detected columns for this table, or fall back to defaults
            table_date_col = detected['date'] if detected['date'] is not None else date_col
            table_desc_col = detected['desc'] if detected['desc'] is not None else desc_col
            table_debit_col = detected['debit'] if detected['debit'] is not None else debit_col
            table_credit_col = detected['credit'] if detected['credit'] is not None else credit_col
            table_balance_col = detected['balance'] if detected['balance'] is not None else balance_col
            date_and_desc_same_col = (table_date_col == table_desc_col)
            for i in range(header_row_idx + 1, len(transaction_table)):
                row = transaction_table.iloc[i]
                
                # Skip empty rows
                if row.isna().all() or (row.astype(str).str.strip() == '').all():
                    continue
                
                # Check for opening/closing balance rows
                row_text = ' '.join(row.astype(str)).lower()
                if 'opening balance' in row_text:
                    # Opening balance already extracted from text
                    continue
                if 'closing balance' in row_text:
                    # Closing balance already extracted from text
                    # Stop processing - no more transactions after this
                    found_closing_balance = True
                    break
                if 'account fees' in row_text or re.match(r'^\d+\s+of\s+\d+', row_text) or 'business account statement' in row_text.lower():
                    # Skip header rows on continuation pages
                    continue
                
                # Extract date using this table's column
                date_str = str(row.iloc[table_date_col]).strip() if table_date_col < len(row) else ''
                
                # Check if this row has a date (format: "03 Feb" or "03Feb" or "22 Jan")
                date_match = re.match(r'^(\d{1,2})\s*(\w{3})', date_str)
                if not date_match:
                    # Some RBC tables can shift date+description into a different column.
                    # Scan non-amount columns as fallback.
                    scan_cols = []
                    for cidx in range(len(row)):
                        if cidx in [table_debit_col, table_credit_col, table_balance_col]:
                            continue
                        cell = str(row.iloc[cidx]).strip()
                        if cell and cell.lower() not in ['', 'nan', 'none']:
                            scan_cols.append(cell)
                    for cell_text in scan_cols:
                        date_match = re.match(r'^(\d{1,2})\s*(\w{3})', cell_text)
                        if date_match:
                            break
                if date_match:
                    day = int(date_match.group(1))
                    month_abbr = date_match.group(2).capitalize()
                    month = month_map.get(month_abbr)
                    if month is None:
                        date_match = None
                
                if date_match:
                    day = int(date_match.group(1))
                    month_abbr = date_match.group(2).capitalize()
                    month = month_map.get(month_abbr)
                    try:
                        # Determine correct year for this date
                        # If statement spans two years (e.g., Dec 2024 to Jan 2025),
                        # use the appropriate year based on the month
                        transaction_year = _transaction_year_for_month(
                            month,
                            statement_start_year,
                            statement_end_year,
                            statement_start_month,
                            statement_end_month,
                            statement_year or 2025,
                        )
                        
                        current_date = datetime(transaction_year, month, day)
                        pending_transaction = None  # Reset pending transaction on new date
                    except:
                        continue
                
                # If no date, use previous date (continuation of same day)
                if current_date is None:
                    continue
                
                # Extract description using this table's column - preserve exact format
                desc = str(row.iloc[table_desc_col]) if table_desc_col < len(row) else ''
                # Only strip leading/trailing whitespace, preserve internal formatting
                desc = desc.strip()
                if date_and_desc_same_col and desc:
                    # If date and description share one column, remove leading date token.
                    desc = re.sub(r'^\d{1,2}\s*\w{3}\s*', '', desc, count=1).strip()
                # Replace newlines with single space for consistency, but preserve other formatting
                if '\n' in desc:
                    desc = ' '.join(desc.split())  # Normalize whitespace but keep as single line
                
                # Extract amounts using this table's columns
                # Store the raw strings so we can identify which columns contain amounts later
                debit_str = str(row.iloc[table_debit_col]).strip() if table_debit_col < len(row) else ''
                credit_str = str(row.iloc[table_credit_col]).strip() if table_credit_col < len(row) else ''
                balance_str = str(row.iloc[table_balance_col]).strip() if table_balance_col < len(row) else ''
                
                # Check if amounts are in description column (multi-line transaction)
                # Look for amounts only in the proper amount columns (debit, credit, balance)
                # Don't scan description column for amounts to avoid hex codes
                all_amounts = []
                amount_columns = [table_debit_col, table_credit_col, table_balance_col]
                for col_idx in amount_columns:
                    if col_idx is not None and col_idx < len(row):
                        cell_str = str(row.iloc[col_idx]).strip()
                        # Look for proper amount patterns: must have decimal point and two digits after
                        # Pattern: optional space, digits (with optional commas), decimal point, exactly 2 digits, optional space or end
                        amount_matches = re.findall(r'([\d,]+\.\d{2})', cell_str)
                        for match in amount_matches:
                            try:
                                amount = float(match.replace(',', ''))
                                # Additional validation: reasonable amount range
                                if 0.01 <= amount <= 100000:
                                    all_amounts.append(amount)
                            except:
                                pass
                
                # Parse amounts
                debit = None
                credit = None
                balance = None
                
                # Remove commas and dollar signs
                if debit_str and debit_str.lower() not in ['', 'nan', 'none']:
                    debit_match = re.search(r'(-?\$?[\d,]+\.\d{2})', debit_str)
                    if debit_match:
                        try:
                            debit = float(debit_match.group(1).replace('$', '').replace(',', ''))
                        except:
                            pass
                
                if credit_str and credit_str.lower() not in ['', 'nan', 'none']:
                    credit_match = re.search(r'(-?\$?[\d,]+\.\d{2})', credit_str)
                    if credit_match:
                        try:
                            credit = float(credit_match.group(1).replace('$', '').replace(',', ''))
                        except:
                            pass
                
                if balance_str and balance_str.lower() not in ['', 'nan', 'none']:
                    # Handle negative balances (e.g., "-267.90" or "-$1,345.99")
                    balance_match = re.search(r'(-?\$?)\s*([\d,]+\.\d{2})', balance_str)
                    if balance_match:
                        try:
                            sign = balance_match.group(1)  # '-' or '$' or '-$' or empty
                            value = float(balance_match.group(2).replace(',', ''))
                            balance = -value if '-' in sign else value
                        except:
                            pass
                
                # Handle multi-line transactions (description spans multiple rows)
                # If we have a pending transaction, try to merge with current row
                if pending_transaction:
                    # FIRST: Collect ALL text from ALL columns before processing amounts
                    # This ensures we capture reference codes, hex codes, and all description parts
                    all_desc_parts = []
                    
                    # Add description from description column
                    if desc and desc.lower() not in ['', 'nan', 'none']:
                        desc_clean = desc.strip()
                        if desc_clean:
                            all_desc_parts.append(desc_clean)
                    
                    # Check ALL other columns for additional description parts
                    # Include everything except date and amounts we'll extract
                    for col_idx in range(len(row)):
                        # Skip date column
                        if col_idx == table_date_col:
                            continue
                        # Skip description column (already added)
                        if col_idx == table_desc_col:
                            continue
                        
                        col_val = str(row.iloc[col_idx]).strip()
                        if not col_val or col_val.lower() in ['', 'nan', 'none']:
                            continue
                        
                        # Check if this is an amount column - compare with strings we'll parse
                        is_amount = False
                        if col_idx == table_debit_col:
                            if debit_str and col_val == debit_str:
                                is_amount = True
                        elif col_idx == table_credit_col:
                            if credit_str and col_val == credit_str:
                                is_amount = True
                        elif col_idx == table_balance_col:
                            if balance_str and col_val == balance_str:
                                is_amount = True
                        
                        # Include everything that's not an amount
                        if not is_amount:
                            all_desc_parts.append(col_val)
                    
                    # Combine all description parts
                    if all_desc_parts:
                        pending_transaction['Description'] += ' ' + ' '.join(all_desc_parts)
                    
                    # NOW extract amounts from proper columns
                    if credit and not pending_transaction.get('Deposits'):
                        pending_transaction['Deposits'] = credit
                    if debit and not pending_transaction.get('Withdrawals'):
                        pending_transaction['Withdrawals'] = debit
                    if balance:
                        pending_transaction['Balance'] = balance
                    
                    # Check if we have amounts anywhere in this row (including description column)
                    if all_amounts and not pending_transaction.get('Deposits') and not pending_transaction.get('Withdrawals'):
                        # Typically first amount is credit, last is balance
                        if len(all_amounts) >= 2:
                            pending_transaction['Deposits'] = all_amounts[0]  # First is usually credit
                            pending_transaction['Balance'] = all_amounts[-1]  # Last is balance
                        elif len(all_amounts) == 1:
                            pending_transaction['Deposits'] = all_amounts[0]
                    elif not pending_transaction.get('Deposits') and not pending_transaction.get('Withdrawals'):
                        # Some RBC rows glue amount fields into description/reference columns
                        row_joined = ' '.join(str(v) for v in row.astype(str).tolist())
                        free_amounts = []
                        for m in re.findall(r'([\d,]+\.\d{2})', row_joined):
                            try:
                                v = float(m.replace(',', ''))
                                if 0.01 <= v <= 100000:
                                    free_amounts.append(v)
                            except Exception:
                                pass
                        if len(free_amounts) >= 2:
                            pending_transaction['Deposits'] = free_amounts[0]
                            pending_transaction['Balance'] = free_amounts[-1]
                        elif len(free_amounts) == 1:
                            pending_transaction['Deposits'] = free_amounts[0]
                    
                    # Look ahead to next 2 rows for amounts if still not found
                    # Only check proper amount columns (not description column) to avoid hex codes
                    if not pending_transaction.get('Deposits') and not pending_transaction.get('Withdrawals'):
                        for lookahead_idx in range(i + 1, min(i + 3, len(transaction_table))):
                            lookahead_row = transaction_table.iloc[lookahead_idx]
                            # Extract amounts only from proper amount columns
                            lookahead_amounts = []
                            amount_columns = [table_debit_col, table_credit_col, table_balance_col]
                            for col_idx in amount_columns:
                                if col_idx is not None and col_idx < len(lookahead_row):
                                    cell_str = str(lookahead_row.iloc[col_idx]).strip()
                                    # Only match proper decimal amounts
                                    amount_matches = re.findall(r'([\d,]+\.\d{2})', cell_str)
                                    for match in amount_matches:
                                        try:
                                            amount = float(match.replace(',', ''))
                                            if 0.01 <= amount <= 100000:
                                                lookahead_amounts.append(amount)
                                        except:
                                            pass
                            
                            if lookahead_amounts:
                                # Typically: debit/credit, then balance
                                if len(lookahead_amounts) >= 2:
                                    pending_transaction['Deposits'] = lookahead_amounts[0]
                                    pending_transaction['Balance'] = lookahead_amounts[-1]
                                elif len(lookahead_amounts) == 1:
                                    pending_transaction['Deposits'] = lookahead_amounts[0]
                                break
                    
                    # Also check raw text if still no amounts found (but not if we've seen closing balance)
                    if not found_closing_balance and not pending_transaction.get('Deposits') and not pending_transaction.get('Withdrawals'):
                        # Find the transaction in raw text and extract amounts
                        desc_lower = pending_transaction['Description'].lower()
                        # Try multiple search terms from the description
                        search_terms = []
                        if 'computron' in desc_lower or 'autodeposit' in desc_lower:
                            # For these transactions, search more specifically
                            if 'computron' in desc_lower:
                                search_terms = ['computron']
                            elif 'autodeposit' in desc_lower:
                                search_terms = ['autodeposit', 'e-transfer']
                        else:
                            # Use last significant word
                            desc_parts = [w for w in desc_lower.split() if len(w) > 3]
                            if desc_parts:
                                search_terms = [desc_parts[-1][:10]]
                        
                        for search_term in search_terms:
                            idx = full_text.lower().find(search_term)
                            if idx >= 0:
                                # Look for amounts in a wider context after the search term
                                start_pos = idx + len(search_term)
                                context = full_text[start_pos:min(len(full_text), start_pos + 200)]
                                
                                # Find the line that contains the amounts
                                lines = context.split('\n')
                                for line in lines:
                                    line_stripped = line.strip()
                                    # Look for lines with amounts (decimal format)
                                    if re.search(r'\d+\.\d{2}', line_stripped):
                                        # This line has amounts - extract description part before amounts
                                        # Split the line: description part and amounts
                                        # Match pattern like "456d00704...113.00 297.80"
                                        # Try to separate description from amounts
                                        amount_pattern = r'([\d,]+\.\d{2})'
                                        amounts_in_line = re.findall(amount_pattern, line_stripped)
                                        if amounts_in_line:
                                            # Remove amounts to get description part
                                            desc_part = re.sub(amount_pattern, '', line_stripped)
                                            desc_part = re.sub(r'\s+', ' ', desc_part).strip()
                                            # Only add if it looks like a description (not headers, dates, etc.)
                                            if desc_part and len(desc_part) > 3:
                                                # Check if it's not a header/date line
                                                # Include all description parts, don't filter
                                                pending_transaction['Description'] += ' ' + desc_part
                                        
                                        # Extract amounts from this line
                                        # Look for properly formatted amounts (X.XX format) that are NOT part of hex codes
                                        # Hex codes are long alphanumeric strings - amounts should be separated by spaces
                                        # Pattern: space + digits + .XX + space (or end of line)
                                        text_amounts = re.findall(r'(?:\s|^)([\d,]+\.\d{2})(?:\s|$)', line_stripped)
                                        # Also check for amounts at the end of line after hex codes
                                        # Remove any hex-code-like patterns (long alphanumeric strings > 20 chars) first
                                        cleaned_line = re.sub(r'[a-f0-9]{20,}', '', line_stripped, flags=re.IGNORECASE)
                                        cleaned_amounts = re.findall(r'(?:\s|^)([\d,]+\.\d{2})(?:\s|$)', cleaned_line)
                                        
                                        # Use cleaned amounts if they exist and are fewer (more accurate)
                                        if cleaned_amounts and len(cleaned_amounts) <= len(text_amounts):
                                            text_amounts = cleaned_amounts
                                        
                                        if text_amounts:
                                            try:
                                                parsed_amounts = [float(a.replace(',', '')) for a in text_amounts[:2]]
                                                # Filter out unreasonable amounts and very small ones
                                                # Also filter out amounts that look like they're from hex codes (very large)
                                                parsed_amounts = [a for a in parsed_amounts if 0.01 < a < 10000]
                                                if len(parsed_amounts) >= 2:
                                                    pending_transaction['Deposits'] = parsed_amounts[0]
                                                    pending_transaction['Balance'] = parsed_amounts[-1]
                                                    break
                                                elif len(parsed_amounts) == 1:
                                                    pending_transaction['Deposits'] = parsed_amounts[0]
                                                    break
                                            except:
                                                pass
                                        break
                                
                                # If we found amounts above, we're done with this search
                                if pending_transaction.get('Deposits') or pending_transaction.get('Withdrawals'):
                                    break
                    
                    # Finalize transaction if we have amounts
                    if pending_transaction.get('Deposits') or pending_transaction.get('Withdrawals'):
                        transactions.append(pending_transaction)
                        pending_transaction = None
                        continue  # Skip processing this row as a new transaction
                    else:
                        # Still building description, continue to next row
                        continue
                
                # Check if this is a hex code or reference line that should be merged with previous transaction
                # Hex codes are long alphanumeric strings without spaces, or short reference codes
                is_hex_code = False
                is_ref_code = False
                if desc:
                    desc_stripped = desc.strip()
                    # Check for hex codes (long alphanumeric)
                    if re.match(r'^[a-f0-9]{20,}$', desc_stripped, re.IGNORECASE):
                        is_hex_code = True
                    # Check for reference codes (shorter codes like C1ASQqJgmHCm)
                    elif len(desc_stripped) >= 8 and len(desc_stripped) <= 20 and re.match(r'^[a-zA-Z0-9]+$', desc_stripped):
                        is_ref_code = True
                
                # If it's a hex code or reference code line - if we have a pending transaction, merge it
                # OR if description exists but no date, it might be continuation of previous transaction
                if pending_transaction:
                    # Add description to pending transaction - include everything
                    desc_clean = desc.strip()
                    if desc_clean and desc_clean.lower() not in ['', 'nan', 'none']:
                        pending_transaction['Description'] += ' ' + desc_clean
                    
                    # Check ALL columns for additional description parts (like EPIK has C1ASQqJgmHCm in col 2)
                    # Include EVERYTHING that could be part of the description
                    for col_idx in range(len(row)):
                        # Skip date column - we already have the date
                        if col_idx == table_date_col:
                            continue
                        
                        col_val = str(row.iloc[col_idx]).strip()
                        if not col_val or col_val.lower() in ['', 'nan', 'none']:
                            continue
                        
                        # If it's the description column, we already added it above
                        if col_idx == table_desc_col:
                            continue
                        
                        # Check if this column has an amount that we've already extracted
                        # Only skip if we've already extracted that amount
                        is_extracted_amount = False
                        if col_idx == table_debit_col:
                            # Only skip if this is the debit we extracted
                            debit_str_check = col_val
                            if debit and abs(float(debit_str_check.replace(',', '')) - debit) < 0.01:
                                is_extracted_amount = True
                        elif col_idx == table_credit_col:
                            credit_str_check = col_val
                            if credit and abs(float(credit_str_check.replace(',', '')) - credit) < 0.01:
                                is_extracted_amount = True
                        elif col_idx == table_balance_col:
                            balance_str_check = col_val
                            if balance and abs(float(balance_str_check.replace(',', '')) - balance) < 0.01:
                                is_extracted_amount = True
                        
                        # If it's not an extracted amount, include it in description
                        # Include EVERYTHING except extracted amounts - no filtering
                        if not is_extracted_amount:
                            pending_transaction['Description'] += ' ' + col_val
                    
                    # Extract amounts from proper columns if available
                    if credit:
                        pending_transaction['Deposits'] = credit
                    if debit:
                        pending_transaction['Withdrawals'] = debit
                    if balance:
                        pending_transaction['Balance'] = balance
                    
                    # Finalize the transaction if we have amounts
                    if pending_transaction.get('Deposits') or pending_transaction.get('Withdrawals'):
                        transactions.append(pending_transaction)
                        pending_transaction = None
                        continue
                
                # Also handle if it's a hex code or reference code but no pending transaction yet
                # (this shouldn't happen often, but just in case)
                if is_hex_code or is_ref_code:
                    # This is unexpected - skip for now
                    continue
                
                # Check for continuation page transaction lines (malformed dates, continuation of previous date)
                # These often appear on page 2+ and have malformed dates like "1177JJuunn"
                # Skip these - they're usually duplicates or misformatted continuation page entries
                if date_str and re.match(r'^\d{3,}', date_str):
                    # Malformed date (too many digits) - skip this row
                    continue
                
                # If description exists but no amounts, it might be first line of multi-line transaction
                if desc and desc.lower() not in ['', 'nan', 'none'] and not debit and not credit and not balance and not all_amounts:
                    # Check if next row might have amounts or be continuation
                    is_multiline = False
                    desc_l = desc.lower()
                    if 'autodeposit' in desc_l or 'e-transfer request fulfilled' in desc_l:
                        is_multiline = True
                    if i + 1 < len(transaction_table):
                        next_row = transaction_table.iloc[i + 1]
                        next_desc = str(next_row.iloc[table_desc_col]).strip() if table_desc_col < len(next_row) else ''
                        # If next row has description but no date, it's likely continuation
                        if next_desc and not re.match(r'^\d{1,2}\s*\w{3}', next_desc) and next_desc.lower() not in ['', 'nan', 'none']:
                            is_multiline = True
                    
                    if is_multiline:
                        pending_transaction = {
                            'Date': current_date.strftime('%Y-%m-%d'),
                            'Description': desc,
                            'Withdrawals': None,
                            'Deposits': None,
                            'Balance': None
                        }
                        continue
                
                # Skip if no amounts found and no description to build on
                if debit is None and credit is None and balance is None:
                    continue
                
                # If this row has amounts but looks like a hex code continuation, skip creating a new transaction
                # (it should have been merged with pending transaction above)
                if is_hex_code and (debit or credit or balance):
                    continue
                
                # If we have a balance, use it to determine debit/credit if not already set
                # This helps with continuation pages where the format might be unclear
                if balance and len(transactions) > 0 and transactions[-1].get('Balance'):
                    prev_balance = transactions[-1]['Balance']
                    balance_change = balance - prev_balance
                    
                    # If we don't have debit/credit but have balance change, infer it
                    if debit is None and credit is None:
                        if balance_change > 0:
                            credit = balance_change
                        elif balance_change < 0:
                            debit = abs(balance_change)
                    # If we have an amount but it doesn't match the balance change, correct it
                    elif credit and abs(credit - balance_change) > 0.01:
                        if balance_change > 0:
                            credit = balance_change
                            debit = None
                        else:
                            debit = abs(balance_change)
                            credit = None
                    elif debit and abs(debit + balance_change) > 0.01:
                        if balance_change < 0:
                            debit = abs(balance_change)
                            credit = None
                        elif 'online banking transfer' in desc.lower() and balance_change > 0:
                            credit = balance_change
                            debit = None
                
                # Collect ALL description parts from ALL columns (not just description column)
                # This ensures we capture names like "Sarine Kassemdjian" that are in other columns
                # Also handles old format where description spans multiple columns
                all_desc_parts = []
                
                # Collect from ALL columns between date and first amount column
                # Amount columns are: debit, credit, balance
                amount_cols = [c for c in [table_debit_col, table_credit_col, table_balance_col] if c is not None]
                first_amount_col = min(amount_cols) if amount_cols else len(row)
                
                # Collect all non-amount, non-date columns
                for col_idx in range(len(row)):
                    # Skip date column
                    if col_idx == table_date_col and not date_and_desc_same_col:
                        continue
                    
                    # Skip amount columns
                    if col_idx in amount_cols:
                        continue
                    
                    col_val = str(row.iloc[col_idx]).strip()
                    if not col_val or col_val.lower() in ['', 'nan', 'none']:
                        continue
                    if date_and_desc_same_col and col_idx == table_date_col:
                        col_val = re.sub(r'^\d{1,2}\s*\w{3}\s*', '', col_val, count=1).strip()
                        if not col_val:
                            continue
                    
                    # Additional check: if this looks like an amount (has decimal pattern), skip it
                    if re.match(r'^[\d,]+\.\d{2}$', col_val.replace('$', '').replace(',', '').strip()):
                        # This looks like an amount, skip it
                        continue
                    
                    # Add to description parts
                    all_desc_parts.append(col_val)
                
                # Combine all description parts, removing duplicates while preserving order
                seen = set()
                unique_parts = []
                for part in all_desc_parts:
                    if part not in seen:
                        seen.add(part)
                        unique_parts.append(part)
                
                full_description = ' '.join(unique_parts) if unique_parts else ''
                if not full_description:
                    continue
                
                transactions.append({
                    'Date': current_date.strftime('%Y-%m-%d'),
                    'Description': full_description,
                    'Withdrawals': debit if debit else None,
                    'Deposits': credit if credit else None,
                    'Balance': balance
                })
                
                # Reset pending transaction
                pending_transaction = None
    
    except Exception as e:
        print(f"Error extracting with Camelot: {e}")
        import traceback
        traceback.print_exc()
        # Fall back to OCR text parsing if Camelot fails
        print("Attempting OCR text parsing fallback...")
        ocr_transactions = _parse_rbc_from_ocr_text(full_text, statement_start_year, statement_end_year, statement_start_month, statement_end_month)
        if ocr_transactions:
            transactions = ocr_transactions
            print(f"✅ OCR text parsing extracted {len(transactions)} transactions")
        else:
            return None, opening_balance, closing_balance, statement_year
    
    if not transactions:
        # Try OCR text parsing as last resort
        print("No transactions found with Camelot, trying OCR text parsing...")
        ocr_transactions = _parse_rbc_from_ocr_text(full_text, statement_start_year, statement_end_year, statement_start_month, statement_end_month)
        if ocr_transactions:
            transactions = ocr_transactions
            print(f"✅ OCR text parsing extracted {len(transactions)} transactions")
        else:
            return None, opening_balance, closing_balance, statement_year
    
    df = pd.DataFrame(transactions)
    df, period_trimmed = _filter_transactions_to_statement_period(df, full_text)
    df = _normalize_rbc_withdrawal_deposit_columns(df)

    # Supplemental pass: add continuation lines only if base extraction does
    # not already tie to closing balance.
    expected_dep, expected_wd = _extract_statement_totals(full_text)
    if len(df) > 0 and (expected_dep is not None or expected_wd is not None):
        base_rb = _compute_running_balance(df, opening_balance)
        if closing_balance is not None and base_rb is not None and abs(float(base_rb[-1]) - float(closing_balance)) < 0.01:
            expected_dep = None
            expected_wd = None

    if len(df) > 0 and (expected_dep is not None or expected_wd is not None):
        cur_wd = float(pd.to_numeric(df.get('Withdrawals', 0), errors='coerce').fillna(0).sum())
        cur_dep = float(pd.to_numeric(df.get('Deposits', 0), errors='coerce').fillna(0).sum())
        wd_deficit = max((expected_wd - cur_wd) if expected_wd is not None else 0.0, 0.0)
        dep_deficit = max((expected_dep - cur_dep) if expected_dep is not None else 0.0, 0.0)

        if wd_deficit > 0.009 or dep_deficit > 0.009:
            existing_keys = set()
            for _, r in df.iterrows():
                amt = r.get('Withdrawals') if pd.notna(r.get('Withdrawals')) else r.get('Deposits')
                if pd.notna(amt):
                    existing_keys.add((str(r.get('Date')), _norm_key_text(r.get('Description')), round(float(amt), 2)))

            default_date = None
            if 'Date' in df.columns and len(df) > 0:
                try:
                    default_date = pd.to_datetime(df['Date'].iloc[-1], errors='coerce')
                    if pd.notna(default_date):
                        default_date = default_date.strftime('%Y-%m-%d')
                    else:
                        default_date = None
                except Exception:
                    default_date = None

            supplements = _extract_continued_section_lines(
                full_text,
                statement_start_year,
                statement_end_year,
                statement_start_month,
                statement_end_month,
                statement_year or 2025,
                default_date=default_date,
            )
            add_rows = []
            known_balance = None
            if 'Running_Balance' in df.columns and df['Running_Balance'].notna().any():
                known_balance = float(df['Running_Balance'].dropna().iloc[-1])
            elif 'Balance' in df.columns and df['Balance'].notna().any():
                known_balance = float(df['Balance'].dropna().iloc[-1])

            for cand in supplements:
                key = (cand['Date'], _norm_key_text(cand['Description']), round(float(cand['Amount']), 2))
                if key in existing_keys:
                    continue

                side = None
                if known_balance is not None and cand.get('BalanceHint') is not None:
                    bal_hint = float(cand['BalanceHint'])
                    delta = bal_hint - known_balance
                    if abs(delta + cand['Amount']) < 0.02:
                        side = 'withdrawal'
                    elif abs(delta - cand['Amount']) < 0.02:
                        side = 'deposit'
                    known_balance = bal_hint

                if side is None:
                    side = _classify_amount_side(cand['Description'], cand['Amount'], dep_deficit, wd_deficit)

                if side == 'withdrawal' and wd_deficit > 0.009:
                    add_rows.append({
                        'Date': cand['Date'],
                        'Description': cand['Description'],
                        'Withdrawals': cand['Amount'],
                        'Deposits': None,
                        'Balance': None,
                    })
                    wd_deficit = max(wd_deficit - cand['Amount'], 0.0)
                    if known_balance is not None:
                        known_balance -= cand['Amount']
                elif side == 'deposit' and dep_deficit > 0.009:
                    if _deposit_already_exists(df, add_rows, cand['Date'], cand['Amount']):
                        continue
                    add_rows.append({
                        'Date': cand['Date'],
                        'Description': cand['Description'],
                        'Withdrawals': None,
                        'Deposits': cand['Amount'],
                        'Balance': None,
                    })
                    dep_deficit = max(dep_deficit - cand['Amount'], 0.0)
                    if known_balance is not None:
                        known_balance += cand['Amount']

            if add_rows:
                df = pd.concat([df, pd.DataFrame(add_rows)], ignore_index=True)
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df = df.sort_values('Date').reset_index(drop=True)
                df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')

    # Calculate running balance from opening + transactions only.
    # Do not use statement Balance column for running-balance calculation.
    if opening_balance is not None:
        running_balance = opening_balance
        running_balances = []
        
        for _, row in df.iterrows():
            if pd.notna(row.get('Withdrawals')):
                running_balance -= row['Withdrawals']
            if pd.notna(row.get('Deposits')):
                running_balance += row['Deposits']
            running_balances.append(running_balance)
        
        df['Running_Balance'] = running_balances
    else:
        df['Running_Balance'] = None

    return df, opening_balance, closing_balance, statement_year

if __name__ == "__main__":
    # Test on a single file
    pdf_path = "data/RBC Chequing 3143 Jan 22, 2025 - Dec 22, 2025/2. Feb 2025.pdf"
    df, opening, closing, year = extract_rbc_chequing_statement(pdf_path)
    
    if df is not None:
        print(f"Extracted {len(df)} transactions")
        print(f"Opening: ${opening:,.2f}" if opening else "Opening: Not found")
        print(f"Closing: ${closing:,.2f}" if closing else "Closing: Not found")
        print(f"Year: {year}")
        print("\nAll transactions:")
        print(df.to_string())
        
        # Check balance match
        if 'Running_Balance' in df.columns and closing is not None:
            final_rb = df['Running_Balance'].iloc[-1]
            diff = abs(final_rb - closing)
            print(f"\nFinal Running Balance: ${final_rb:,.2f}")
            print(f"Closing Balance: ${closing:,.2f}")
            print(f"Difference: ${diff:,.2f}")
            if diff < 0.01:
                print("Balance matches!")
            else:
                print("Balance mismatch")
    else:
        print("Failed to extract transactions")
