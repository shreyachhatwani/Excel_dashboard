

# import pandas as pd
# import numpy as np


# def detect_column_types(df: pd.DataFrame) -> dict:
#     result = {}
#     for col in df.columns:
#         series = df[col].dropna()
#         if len(series) == 0:
#             result[col] = 'text'
#             continue

#         # ── 1. Already a datetime dtype (pandas / polars read it natively) ──
#         if pd.api.types.is_datetime64_any_dtype(series):
#             result[col] = 'date'
#             continue

#         # ── 2. Try numeric — but only if NOT already datetime-like ──────────
#         try:
#             numeric_series = pd.to_numeric(series)
#             unique_ratio = series.nunique() / len(series)
#             # Distinguish IDs (very high cardinality integers) from plain numbers
#             if unique_ratio > 0.95 and str(series.dtype) in ('int64', 'float64'):
#                 result[col] = 'id'
#             else:
#                 result[col] = 'numeric'
#             continue
#         except (ValueError, TypeError):
#             pass

#         # ── 3. Try parsing as date strings ───────────────────────────────────
#         try:
#             parsed = pd.to_datetime(series.head(50), format='mixed', dayfirst=False)
#             if parsed.notna().sum() >= len(series.head(50)) * 0.8:
#                 result[col] = 'date'
#                 continue
#         except Exception:
#             pass

#         # ── 4. Category vs free text ─────────────────────────────────────────
#         unique_ratio = series.nunique() / len(series)
#         if unique_ratio < 0.5 or series.nunique() <= 30:
#             result[col] = 'category'
#         else:
#             result[col] = 'text'

#     return result


# def get_columns_by_type(df: pd.DataFrame) -> dict:
#     types = detect_column_types(df)
#     grouped = {'numeric': [], 'category': [], 'date': [], 'id': [], 'text': []}
#     for col, t in types.items():
#         grouped[t].append(col)
#     return grouped
import pandas as pd
import numpy as np


def detect_column_types(df: pd.DataFrame) -> dict:
    result = {}
    for col in df.columns:
        series = df[col].dropna()
        if len(series) == 0:
            result[col] = 'text'
            continue

        # ── 1. Already a datetime dtype (pandas / polars read it natively) ──
        if pd.api.types.is_datetime64_any_dtype(series):
            result[col] = 'date'
            continue

        # ── 2. Try numeric — but only if NOT already datetime-like ──────────
        try:
            numeric_series = pd.to_numeric(series)
            unique_ratio = series.nunique() / len(series)
            # Distinguish IDs (very high cardinality integers) from plain numbers
            if unique_ratio > 0.95 and str(series.dtype) in ('int64', 'float64'):
                result[col] = 'id'
            else:
                result[col] = 'numeric'
            continue
        except (ValueError, TypeError):
            pass

        # ── 3. Try parsing as date strings ───────────────────────────────────
        try:
            parsed = pd.to_datetime(series.head(50), format='mixed', dayfirst=False)
            if parsed.notna().sum() >= len(series.head(50)) * 0.8:
                result[col] = 'date'
                continue
        except Exception:
            pass

        # ── 4. Category vs free text ─────────────────────────────────────────
        unique_ratio = series.nunique() / len(series)
        if unique_ratio < 0.5 or series.nunique() <= 30:
            result[col] = 'category'
        else:
            result[col] = 'text'

    return result


def get_columns_by_type(df: pd.DataFrame) -> dict:
    types = detect_column_types(df)
    grouped = {'numeric': [], 'category': [], 'date': [], 'id': [], 'text': []}
    for col, t in types.items():
        grouped[t].append(col)
    return grouped