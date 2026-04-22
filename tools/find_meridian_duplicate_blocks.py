#!/usr/bin/env python3
"""Find repeated transaction blocks in Meridian combined Excel."""

from collections import defaultdict
from pathlib import Path

import pandas as pd


def main() -> int:
    excel_path = Path("data/Burger Factory/meridian/Meridian_BurgerFactory_combined.xlsx")
    report_path = Path("data/Burger Factory/meridian/meridian_duplicate_blocks_report.txt")
    if not excel_path.exists():
        print(f"Missing file: {excel_path}")
        return 1

    df = pd.read_excel(excel_path)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    post = df[df["Date"] > pd.Timestamp("2025-03-31")].copy().reset_index(drop=False).rename(
        columns={"index": "orig_idx"}
    )

    cols = [c for c in ["Date", "Description", "Withdrawals", "Deposits", "Running_Balance"] if c in post.columns]
    wrk = post[cols].copy()
    wrk["Date"] = wrk["Date"].dt.strftime("%Y-%m-%d")
    for col in ["Withdrawals", "Deposits", "Running_Balance"]:
        if col in wrk.columns:
            wrk[col] = pd.to_numeric(wrk[col], errors="coerce").round(2)
    wrk = wrk.fillna("")

    sig = ["|".join(str(r[c]) for c in cols) for _, r in wrk.iterrows()]
    positions = defaultdict(list)
    for i, s in enumerate(sig):
        positions[s].append(i)

    blocks = []
    seen = set()
    n = len(sig)
    for i in range(n):
        for j in positions[sig[i]]:
            if j <= i:
                continue
            # skip if this pair can be extended to the left
            if i > 0 and j > 0 and sig[i - 1] == sig[j - 1]:
                continue
            k = 0
            while i + k < n and j + k < n and sig[i + k] == sig[j + k]:
                k += 1
            if k < 2:
                continue
            key = (i, j, k)
            if key in seen:
                continue
            seen.add(key)
            blocks.append((i, j, k))

    # Keep maximal blocks (drop strict sub-blocks with same shift)
    blocks_sorted = sorted(blocks, key=lambda x: (-x[2], x[0], x[1]))
    kept = []
    for i, j, k in blocks_sorted:
        contained = False
        for ii, jj, kk in kept:
            if (j - i) == (jj - ii) and i >= ii and j >= jj and (i + k) <= (ii + kk) and (j + k) <= (jj + kk):
                contained = True
                break
        if not contained:
            kept.append((i, j, k))
    kept.sort(key=lambda x: (x[0], x[1]))

    with report_path.open("w", encoding="utf-8") as f:
        f.write(f"File: {excel_path}\n")
        f.write(f"Rows after 2025-03-31: {len(post)}\n")
        f.write(f"Maximal repeated blocks (len>=2): {len(kept)}\n\n")
        for idx, (i, j, k) in enumerate(kept, 1):
            oi = int(post.loc[i, "orig_idx"])
            oj = int(post.loc[j, "orig_idx"])
            ei = int(post.loc[i + k - 1, "orig_idx"])
            ej = int(post.loc[j + k - 1, "orig_idx"])
            d1 = str(post.loc[i, "Date"].date()) if pd.notna(post.loc[i, "Date"]) else "NA"
            d2 = str(post.loc[i + k - 1, "Date"].date()) if pd.notna(post.loc[i + k - 1, "Date"]) else "NA"
            d3 = str(post.loc[j, "Date"].date()) if pd.notna(post.loc[j, "Date"]) else "NA"
            d4 = str(post.loc[j + k - 1, "Date"].date()) if pd.notna(post.loc[j + k - 1, "Date"]) else "NA"
            f.write(f"BLOCK {idx}: length={k}\n")
            f.write(f"  Occurrence A: filtered {i}-{i + k - 1} | original {oi}-{ei} | dates {d1}..{d2}\n")
            f.write(f"  Occurrence B: filtered {j}-{j + k - 1} | original {oj}-{ej} | dates {d3}..{d4}\n")
            f.write("  Rows (A):\n")
            show = post.loc[i : i + k - 1, ["orig_idx"] + cols]
            for _, row in show.iterrows():
                date_str = pd.to_datetime(row["Date"]).strftime("%Y-%m-%d") if pd.notna(row["Date"]) else ""
                f.write(
                    f"    {int(row['orig_idx'])} | {date_str} | {row['Description']} | "
                    f"W={row.get('Withdrawals', '')} | D={row.get('Deposits', '')} | "
                    f"RB={row.get('Running_Balance', '')}\n"
                )
            f.write("\n")

    print(f"Report written: {report_path}")
    print(f"Blocks found: {len(kept)}")
    print("Top 10 longest blocks:")
    for i, j, k in sorted(kept, key=lambda x: -x[2])[:10]:
        print(
            f"  len={k} | A orig {int(post.loc[i, 'orig_idx'])}-{int(post.loc[i + k - 1, 'orig_idx'])}"
            f" | B orig {int(post.loc[j, 'orig_idx'])}-{int(post.loc[j + k - 1, 'orig_idx'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

