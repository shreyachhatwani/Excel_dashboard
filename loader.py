# loader.py
import os
import polars as pl
import pandas as pd

SUPPORTED = (".xlsx", ".xls")


def _clean_cols(df: pl.DataFrame) -> pl.DataFrame:
    cleaned = [
        c.strip()
         .replace(" ", "_").replace("(", "").replace(")", "")
         .replace("/", "_").replace("-", "_")
        for c in df.columns
    ]
    return df.rename({old: new for old, new in zip(df.columns, cleaned)})


def _coerce_types(df: pl.DataFrame) -> pl.DataFrame:
    """
    Cast all integer columns to Float64 so files with the same column
    but different numeric types don't crash when stacking.
    """
    for col in df.columns:
        if df[col].dtype in (
            pl.Int8, pl.Int16, pl.Int32, pl.Int64,
            pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64
        ):
            df = df.with_columns(pl.col(col).cast(pl.Float64))
    return df


def _read_one(filepath: str) -> pl.DataFrame:
    if filepath.lower().endswith(".xls"):
        df = pl.from_pandas(pd.read_excel(filepath, engine="xlrd"))
    else:
        df = pl.read_excel(filepath)
    df = _clean_cols(df)
    df = _coerce_types(df)
    return df


def load_file(filepath: str):
    """Load a single Excel file. Returns (polars_df, [filepath])."""
    df = _read_one(filepath)
    df = df.with_columns(
        pl.lit(os.path.basename(filepath)).alias("_source_file")
    )
    return df, [filepath]


def load_folder(folder_path: str):
    """
    Returns list of file paths only — does NOT load into memory.
    db.py loads each file one at a time to avoid RAM issues.
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
    return files