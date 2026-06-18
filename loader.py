# loader.py  — reads a single file OR every Excel file in a folder
import os
import polars as pl
import pandas as pd

SUPPORTED = (".xlsx", ".xls")


def _clean_cols(df: pl.DataFrame) -> pl.DataFrame:
    """Standardise column names."""
    cleaned = [
        c.strip()
         .replace(" ", "_").replace("(", "").replace(")", "")
         .replace("/", "_").replace("-", "_")
        for c in df.columns
    ]
    return df.rename({old: new for old, new in zip(df.columns, cleaned)})


def _read_one(filepath: str) -> pl.DataFrame:
    """Read a single .xls or .xlsx into a Polars DataFrame."""
    if filepath.lower().endswith(".xls"):
        df = pl.from_pandas(pd.read_excel(filepath, engine="xlrd"))
    else:
        df = pl.read_excel(filepath)
    return _clean_cols(df)


def load_file(filepath: str):
    """
    Load a single Excel file.
    Returns (polars_df, [filepath])
    Adds _source_file column.
    """
    df = _read_one(filepath)
    df = df.with_columns(
        pl.lit(os.path.basename(filepath)).alias("_source_file")
    )
    return df, [filepath]


def load_folder(folder_path: str):
    """
    Load every Excel file inside a folder.
    Stacks them all into one DataFrame.
    Adds _source_file column so every row knows which file it came from.
    Returns (combined_polars_df, [list_of_full_filepaths])
    """
    files = sorted([
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith(SUPPORTED) and not f.startswith("~")
    ])

    if not files:
        raise FileNotFoundError(
            f"No Excel files found in folder: {folder_path}"
        )

    frames = []
    loaded = []
    for fp in files:
        try:
            df = _read_one(fp)
            df = df.with_columns(
                pl.lit(os.path.basename(fp)).alias("_source_file")
            )
            frames.append(df)
            loaded.append(fp)
            print(f"[loader] ✓ {os.path.basename(fp)} — {len(df)} rows")
        except Exception as e:
            print(f"[loader] ✗ Skipped {os.path.basename(fp)}: {e}")

    if not frames:
        raise ValueError("All files in folder failed to load.")

    # diagonal fill fills missing columns with null so mismatched schemas stack cleanly
    combined = pl.concat(frames, how="diagonal")
    return combined, loaded