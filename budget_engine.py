# ─────────────────────────────────────────────
# OFFLINE FLAG — must be set before sentence_transformers is imported.
# Prevents HuggingFace network calls after the model is cached locally.
# ─────────────────────────────────────────────
import os
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"]  = "1"
os.environ["HF_HUB_OFFLINE"]       = "1"   # covers the huggingface_hub layer too

import json
import tkinter as tk
from tkinter import filedialog

import pandas as pd
from rapidfuzz import process, fuzz
from sentence_transformers import SentenceTransformer, util

from parsers import PARSERS   # auto-detection registry
from analytics import run_analytics

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
FUZZY_THRESHOLD    = 85      # RapidFuzz cutoff (0–100)
SEMANTIC_THRESHOLD = 0.40    # Cosine similarity cutoff (0.0–1.0)
ENCODER_MODEL      = "BAAI/bge-small-en-v1.5"

CATEGORY_MAP_PATH = os.path.join(
    os.path.dirname(__file__), "mapping", "category_map.json"
)

# ─────────────────────────────────────────────
# SEMANTIC ATTRACTORS
# Edit freely — no need to touch category_map.json for new patterns.
# ─────────────────────────────────────────────
CATEGORY_ATTRACTORS: dict[str, list[str]] = {
    "Dining":        ["restaurant", "fast food", "coffee shop", "cafe", "donut", "pizza", "burger", "sushi", "bar and grill", "bakery", "diner", "takeout", "food delivery"],
    "Groceries":     ["grocery store", "supermarket", "food market", "fresh produce", "whole foods", "organic market"],
    "Shopping":      ["retail store", "online shopping", "department store", "clothing", "electronics purchase", "marketplace"],
    "Gas":           ["gas station", "fuel", "petrol", "filling station", "automotive fuel"],
    "Transport":     ["rideshare", "taxi", "subway", "bus fare", "parking", "toll", "train ticket", "car rental"],
    "Subscriptions": ["monthly subscription", "streaming service", "software subscription", "membership fee", "digital service"],
    "Health":        ["pharmacy", "drugstore", "medical", "healthcare", "dental", "vision", "clinic", "urgent care"],
    "Utilities":     ["electric bill", "water bill", "internet service", "phone bill", "utility payment", "gas utility"],
    "Transfer":      ["money transfer", "peer payment", "send money", "bank transfer", "wire transfer"],
    "Payment":       ["credit card payment", "loan payment", "autopay", "bill payment", "account payment"],
    "Travel":        ["hotel", "airline", "flight", "airbnb", "motel", "travel booking", "vacation rental"],
    "Entertainment": ["movie theater", "concert", "event ticket", "amusement park", "gaming", "sports ticket"],
    "Fitness":       ["gym", "fitness center", "yoga studio", "personal trainer", "sports equipment"],
}

# ─────────────────────────────────────────────
# STARTUP LOADERS
# ─────────────────────────────────────────────
def load_category_map(path: str) -> dict:
    if not os.path.exists(path):
        print(f"[WARN] No category map found at: {path}")
        return {}
    with open(path, "r") as f:
        return json.load(f)

def load_encoder(model_name: str) -> SentenceTransformer:
    """
    Loads BGE model from local cache only (offline mode enforced above).
    If cache is missing, run once WITHOUT offline flags to download it.
    """
    print(f"[ENCODER] Loading model from cache: {model_name} ...")
    model = SentenceTransformer(model_name)
    print(f"[ENCODER] Model ready.")
    return model

def build_attractor_index(model: SentenceTransformer, attractors: dict) -> dict:
    """Pre-encodes all attractor phrases once at startup."""
    print("[ENCODER] Pre-encoding category attractors...")
    index = {}
    for category, phrases in attractors.items():
        prefixed   = [f"Represent this sentence: {p}" for p in phrases]
        embeddings = model.encode(prefixed, convert_to_tensor=True, normalize_embeddings=True)
        index[category] = embeddings
    print(f"[ENCODER] Attractor index built for {len(index)} categories.")
    return index

# ─────────────────────────────────────────────
# SEMANTIC CLASSIFIER
# ─────────────────────────────────────────────
def semantic_classify(
    description: str,
    model: SentenceTransformer,
    attractor_index: dict
) -> tuple[str, float]:
    query     = f"Represent this sentence: {description}"
    query_emb = model.encode(query, convert_to_tensor=True, normalize_embeddings=True)

    best_category = "Uncategorized"
    best_score    = 0.0

    for category, attractor_embeddings in attractor_index.items():
        scores    = util.cos_sim(query_emb, attractor_embeddings)[0]
        top_score = float(scores.max())
        if top_score > best_score:
            best_score    = top_score
            best_category = category

    return best_category, best_score

# ─────────────────────────────────────────────
# MASTER CATEGORIZER — 4-layer pipeline
# ─────────────────────────────────────────────
def categorize(
    description: str,
    category_map: dict,
    model: SentenceTransformer,
    attractor_index: dict
) -> tuple[str, str, float]:
    """
    Layer 1 — Direct Lookup  : exact/substring match in category_map.json
    Layer 2 — RapidFuzz      : fuzzy string match against map keys
    Layer 3 — BGE Encoder    : semantic similarity to category attractors
    Layer 4 — Fallback       : "Uncategorized"
    """
    normalized = description.upper().strip()

    # ── Layer 1: Direct Lookup ─────────────────
    if category_map:
        if normalized in category_map:
            return category_map[normalized], "direct", 1.0
        for key, cat in category_map.items():
            if key in normalized:
                return cat, "direct", 1.0

    # ── Layer 2: RapidFuzz ────────────────────
    if category_map:
        result = process.extractOne(
            normalized,
            list(category_map.keys()),
            scorer=fuzz.WRatio,
            score_cutoff=FUZZY_THRESHOLD
        )
        if result:
            matched_key, score, _ = result
            return category_map[matched_key], "fuzzy", round(score / 100, 3)

    # ── Layer 3: BGE Semantic Encoder ─────────
    category, score = semantic_classify(description, model, attractor_index)
    if score >= SEMANTIC_THRESHOLD:
        return category, "semantic", round(score, 3)

    # ── Layer 4: Fallback ─────────────────────
    return "Uncategorized", "uncategorized", 0.0

# ─────────────────────────────────────────────
# PARSER AUTO-DETECTION
# ─────────────────────────────────────────────
def detect_parser(df: pd.DataFrame):
    """
    Loops through registered parsers and returns the first one
    whose detect() returns True. Returns None if no match.
    """
    for parser in PARSERS:
        try:
            if parser.detect(df):
                return parser
        except NotImplementedError:
            continue
    return None

# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────
def run_pipeline():
    # All slow startup ops happen once
    category_map    = load_category_map(CATEGORY_MAP_PATH)
    model           = load_encoder(ENCODER_MODEL)
    attractor_index = build_attractor_index(model, CATEGORY_ATTRACTORS)

    print(f"\n[INFO] Category map: {len(category_map)} entries loaded.")

    # File picker
    root = tk.Tk()
    root.withdraw()
    print("\nSelect one or more bank CSV files...")
    file_paths = filedialog.askopenfilenames(
        title="Select Bank Exports",
        filetypes=[("CSV files", "*.csv")]
    )

    if not file_paths:
        print("No files selected. Exiting.")
        return

    # Process each file
    combined_list = []
    for f_path in file_paths:
        fname = os.path.basename(f_path)
        print(f"[READ] {fname}")
        try:
            raw_df  = pd.read_csv(f_path)
            parser  = detect_parser(raw_df)

            if parser is None:
                print(f"[SKIP] {fname} — no matching parser found.")
                continue

            print(f"[INFO] {fname} → using parser: {parser.__name__.split('.')[-1]}")
            parsed_df = parser.parse(raw_df)

            # Apply categorization (Layer 0: use NFCU's own category if present)
            has_nfcu_cat = 'nfcu_category' in parsed_df.columns

            def categorize_row(row):
                if has_nfcu_cat and row.get('nfcu_category'):
                    return row['nfcu_category'], "nfcu_native", 1.0
                return categorize(str(row['desc']), category_map, model, attractor_index)

            results = parsed_df.apply(categorize_row, axis=1)
            parsed_df['category']     = results.apply(lambda r: r[0])
            parsed_df['match_method'] = results.apply(lambda r: r[1])
            parsed_df['confidence']   = results.apply(lambda r: r[2])

            # Drop the helper column before combining
            if has_nfcu_cat:
                parsed_df = parsed_df.drop(columns=['nfcu_category'])

            combined_list.append(parsed_df)

        except NotImplementedError as e:
            print(f"[SKIP] {fname} — {e}")
        except Exception as e:
            print(f"[ERR]  {fname}: {e}")

    if not combined_list:
        print("Nothing was processed.")
        return

    # Aggregate, sort, export
    final_df = pd.concat(combined_list, ignore_index=True)
    final_df['date'] = pd.to_datetime(final_df['date'], format='mixed')
    final_df = final_df.sort_values(by=['date', 'source_bank'], ascending=[False, True])

    out_path = os.path.join(os.path.expanduser("~"), "Downloads", "budget_master.csv")
    final_df.to_csv(out_path, index=False)

    # Summary
    total     = len(final_df)
    by_method = final_df['match_method'].value_counts().to_dict()
    by_bank   = final_df['source_bank'].value_counts().to_dict()
    print(f"\n✅  {len(combined_list)} file(s) → {total} transactions categorized.")
    for bank, count in by_bank.items():
        print(f"    {bank:<20}: {count} transactions")
    print(f"    ──────────────────────────────")
    print(f"    Layer 0 – NFCU Native: {by_method.get('nfcu_native', 0)}")
    print(f"    Layer 1 – Direct     : {by_method.get('direct', 0)}")
    print(f"    Layer 2 – Fuzzy      : {by_method.get('fuzzy', 0)}")
    print(f"    Layer 3 – Semantic   : {by_method.get('semantic', 0)}")
    print(f"    Layer 4 – Fallback   : {by_method.get('uncategorized', 0)}")
    print(f"\n📄  Saved to: {out_path}")

    run_analytics(final_df)

if __name__ == "__main__":
    run_pipeline()