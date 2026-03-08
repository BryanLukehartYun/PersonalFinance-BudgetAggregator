import pandas as pd

# ─────────────────────────────────────────────
# CAPITAL ONE PARSER
# Expected columns: Transaction Date, Description, Debit, Credit
# Outputs standard schema: [date, desc, amount]
# ─────────────────────────────────────────────

# These are the columns we need to confirm this is a Capital One file
REQUIRED_COLUMNS = {"Debit", "Credit", "Transaction Date", "Description"}

def detect(df: pd.DataFrame) -> bool:
    """Returns True if this CSV looks like a Capital One export."""
    return REQUIRED_COLUMNS.issubset(set(df.columns))

def parse(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalizes a raw Capital One CSV into the standard schema.
    Returns a DataFrame with columns: [date, desc, amount]
    - amount is positive for credits (money in), negative for debits (money out)
    """
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    df['Debit']  = pd.to_numeric(df['Debit'],  errors='coerce').fillna(0)
    df['Credit'] = pd.to_numeric(df['Credit'], errors='coerce').fillna(0)
    df['amount'] = df['Credit'] - df['Debit']

    df = df.rename(columns={
        'Transaction Date': 'date',
        'Description':      'desc'
    })

    df['source_bank'] = 'Capital One'
    return df[['date', 'desc', 'amount', 'source_bank']].copy()