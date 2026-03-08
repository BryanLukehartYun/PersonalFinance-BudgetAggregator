import pandas as pd

# ─────────────────────────────────────────────
# NAVY FEDERAL (NFCU) PARSER
#
# Columns we care about:
#   Col B — Transaction Date
#   Col C — Amount
#   Col D — Credit Debit Indicator  ("Credit" = money in, "Debit" = money out)
#   Col E — type
#   Col K — Description
#   Col L — Category  (NFCU's own label — used as Layer 0 if present)
#
# Note: NFCU CSVs sometimes have a "transactions" title row above the real headers.
#       detect() and parse() both handle this by skipping that row if found.
# ─────────────────────────────────────────────

REQUIRED_COLUMNS = {
    "Transaction Date",
    "Amount",
    "Credit Debit Indicator",
    "Description",
}

def _maybe_fix_header(df: pd.DataFrame) -> pd.DataFrame:
    """
    NFCU exports sometimes have a stray 'transactions' title row
    before the real header row. If row 0 col 0 looks like a title,
    re-read treating row 1 as the header.
    """
    first_val = str(df.columns[0]).strip().lower()
    if first_val in ('transactions', 'transaction', ''):
        df.columns = df.iloc[0]
        df = df[1:].reset_index(drop=True)
    return df

def detect(df: pd.DataFrame) -> bool:
    """Returns True if this CSV looks like an NFCU export."""
    df = _maybe_fix_header(df)
    cols = {c.strip() for c in df.columns}
    return REQUIRED_COLUMNS.issubset(cols)

def parse(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalizes a raw NFCU CSV into the standard schema.
    Returns a DataFrame with columns: [date, desc, amount, source_bank, nfcu_category]
    """
    df = _maybe_fix_header(df)
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    # Amount — strip $ or commas just in case
    df['Amount'] = (
        df['Amount']
        .astype(str)
        .str.replace(r'[$,]', '', regex=True)
    )
    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)

    # Apply sign: Debit = negative (you paid), Credit = positive (money in)
    indicator = df['Credit Debit Indicator'].astype(str).str.strip().str.lower()
    df['amount'] = df['Amount'].where(indicator == 'credit', -df['Amount'])

    df = df.rename(columns={
        'Transaction Date': 'date',
        'Description':      'desc',
    })

    # Pass through NFCU's own category as Layer 0
    if 'Category' in df.columns:
        df['nfcu_category'] = df['Category'].astype(str).str.strip()
        df['nfcu_category'] = df['nfcu_category'].replace({'nan': None, '': None})
    else:
        df['nfcu_category'] = None

    df['source_bank'] = 'Navy Federal'

    return df[['date', 'desc', 'amount', 'source_bank', 'nfcu_category']].copy()