
# import os
# import sqlite3
# import polars as pl
# from detector import detect_column_types

# # ── Config
# # The dashboard will load it automatically on server start — no upload UI needed.
# EXCEL_FILE_PATH = r"C:\Users\Shreya\Downloads\PUR_DATA (1).xls"        
# DB_FILE_NAME    = "dashboard_analytics.db"
# #folder link instead of file

# # ── Global session state
# _conn      = None
# _df_cache  = None   # Polars DataFrame
# _col_types = None


# # ── Public accessors

# def get_connection():
#     global _conn
#     if _conn is None:
#         _conn = sqlite3.connect(DB_FILE_NAME, check_same_thread=False)
#     return _conn


# def get_col_types():
#     return _col_types


# def get_df():
#     return _df_cache

# #
# # ── Core loader 

# def load_excel_to_sqlite(filepath: str):
#     """
#     Read an xlsx/xls file via Polars (fast), detect column types,
#     write into a local SQLite file, and cache everything in module globals.
#     """
#     global _conn, _df_cache, _col_types

#     # ── 1. Read file
#     if not os.path.exists(filepath):
#         raise FileNotFoundError(
#             f"Excel file not found: '{filepath}'\n"
#             f"Set EXCEL_FILE_PATH in db.py to the correct path."
#         )

#     if filepath.lower().endswith('.xls'):
#         # Legacy .xls — fall back through pandas + xlrd
#         import pandas as pd
#         pandas_df = pd.read_excel(filepath, engine='xlrd')
#         df = pl.from_pandas(pandas_df)
#     else:
#         # Modern .xlsx — Polars native (fast)
#         df = pl.read_excel(filepath)

#     # ── 2. Clean column names ────────────────────────────────────────────────
#     cleaned = [
#         c.strip()
#          .replace(' ', '_')
#          .replace('(', '').replace(')', '')
#          .replace('/', '_')
#          .replace('-', '_')
#         for c in df.columns
#     ]
#     df = df.rename({old: new for old, new in zip(df.columns, cleaned)})

#     # ── 3. Detect types (uses pandas detector — keep as-is) ──────────────────
#     pandas_df_for_detector = df.to_pandas()
#     col_types = detect_column_types(pandas_df_for_detector)

#     # ── 4. Coerce date columns to ISO-string "YYYY-MM-DD" ────────────────────
#     for col, t in col_types.items():
#         if t == 'date' and col in df.columns:
#             try:
#                 df = df.with_columns(
#                     pl.col(col).cast(pl.String, strict=False).str.slice(0, 10)
#                 )
#             except Exception:
#                 pass   # leave column as-is if coercion fails
#     # ── 4. Coerce date columns to ISO-string "YYYY-MM-DD" ────────────────────


#     # ── 5. Write to SQLite (via pandas bridge — reliable & fast enough) ───────
#     if _conn is not None:
#         try:
#             _conn.close()
#         except Exception:
#             pass

#     _conn = sqlite3.connect(DB_FILE_NAME, check_same_thread=False)
#     df.to_pandas().to_sql('data', _conn, if_exists='replace', index=False)

#     # ── 6. Cache ──────────────────────────────────────────────────────────────
#     _df_cache  = df
#     _col_types = col_types

#     return pandas_df_for_detector, col_types


# # ── Auto-load on import ────────────────────────────────────────────────────────
# # Runs once when the server starts. If the file is missing the server still
# # boots; the /ready endpoint will return not-ready and the UI shows an error.

# def _auto_load():
#     try:
#         load_excel_to_sqlite(EXCEL_FILE_PATH)
#         print(f"[db] ✓ Loaded '{EXCEL_FILE_PATH}' → {len(_df_cache)} rows, "
#               f"{len(_df_cache.columns)} columns")
#     except FileNotFoundError as e:
#         print(f"[db] ✗ {e}")
#     except Exception as e:
#         print(f"[db] ✗ Failed to load '{EXCEL_FILE_PATH}': {e}")

# _auto_load()
# db.py
import os
import psycopg2
import pandas as pd
import polars as pl
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

from detector import detect_column_types
import loader as _loader
import cache  as _cache
import neo4j_writer as _nw
from config import (
    EXCEL_FILE_PATH, EXCEL_FOLDER_PATH,
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
)

_conn      = None
_engine    = None
_df_cache  = None
_col_types = None


def _get_engine():
    global _engine
    if _engine is None:
        safe_password = quote_plus(POSTGRES_PASSWORD)
        url = (
            f"postgresql+psycopg2://{POSTGRES_USER}:{safe_password}"
            f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        )
        _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def get_connection():
    global _conn
    try:
        if _conn is not None and not _conn.closed:
            cur = _conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return _conn
    except Exception:
        _conn = None

    _conn = psycopg2.connect(
        host     = POSTGRES_HOST,
        port     = POSTGRES_PORT,
        user     = POSTGRES_USER,
        password = POSTGRES_PASSWORD,
        dbname   = POSTGRES_DB,
    )
    _conn.autocommit = True
    return _conn


def get_col_types():
    return _col_types


def get_df():
    return _df_cache


def _table_exists(engine) -> bool:
    try:
        with engine.connect() as c:
            result = c.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'data')"
            ))
            return bool(result.scalar())
    except Exception:
        return False


def _actual_row_count_for_file(engine, fname: str) -> int:
    """
    Counts rows ACTUALLY present in PostgreSQL for this file — the real
    source of truth. This prevents duplicate stacking even if cache.json
    is deleted, stale, or out of sync, because we never trust cache.json
    alone anymore.
    """
    if not _table_exists(engine):
        return 0
    try:
        with engine.connect() as c:
            result = c.execute(
                text('SELECT COUNT(*) FROM data WHERE "_source_file" = :fname'),
                {"fname": fname}
            )
            return int(result.scalar())
    except Exception:
        return 0


def load_excel_to_postgres(filepath: str = None, folder_path: str = None):
    global _conn, _engine, _df_cache, _col_types

    fp     = filepath    or EXCEL_FILE_PATH    or None
    folder = folder_path or EXCEL_FOLDER_PATH  or None

    if not fp and not folder:
        raise ValueError(
            "No input provided. "
            "Set EXCEL_FILE_PATH or EXCEL_FOLDER_PATH in config.py"
        )

    if folder:
        full_df, file_list = _loader.load_folder(folder)
    else:
        full_df, file_list = _loader.load_file(fp)

    engine = _get_engine()

    new_frames = []
    for fpath in file_list:
        fname   = os.path.basename(fpath)
        file_df = full_df.filter(pl.col("_source_file") == fname)
        total   = len(file_df)

        # Real check against PostgreSQL — the true source of truth.
        actual_in_db = _actual_row_count_for_file(engine, fname)
        cached       = _cache.get_cached_row_count(fpath)
        already_loaded = max(actual_in_db, cached)

        if total <= already_loaded:
            print(f"[db] ↷  {fname}: {total} rows — unchanged, skipping "
                  f"(db has {actual_in_db}, cache had {cached})")
            try:
                existing = pl.from_pandas(
                    pd.read_sql(
                        'SELECT * FROM data WHERE "_source_file" = %(fname)s',
                        engine,
                        params={"fname": fname}
                    )
                )
                new_frames.append(existing)
            except Exception:
                new_frames.append(file_df)
            _cache.update_cache(fpath, total)
            continue

        new_rows = file_df.slice(already_loaded, total - already_loaded)
        print(f"[db] ✚  {fname}: {total - already_loaded} new rows "
              f"(db had {actual_in_db}, now {total})")
        new_frames.append(new_rows)
        _cache.update_cache(fpath, total)

    if not new_frames:
        print("[db] ✓ Nothing new — all files unchanged.")
        return _df_cache.to_pandas() if _df_cache is not None else None, _col_types

    incremental_df = pl.concat(new_frames, how="diagonal")

    pandas_incremental = incremental_df.to_pandas()
    col_types          = detect_column_types(pandas_incremental)

    for col, t in col_types.items():
        if t == "date" and col in incremental_df.columns:
            try:
                incremental_df = incremental_df.with_columns(
                    pl.col(col).cast(pl.String, strict=False).str.slice(0, 10)
                )
            except Exception:
                pass

    pandas_incremental = incremental_df.to_pandas()

    if len(pandas_incremental) > 0:
        pandas_incremental.to_sql(
            "data", engine,
            if_exists="append",
            index=False,
            chunksize=500,
            method="multi",
        )
        print(f"[db] ✓ Wrote {len(pandas_incremental)} new rows to PostgreSQL")
    else:
        print("[db] ✓ No new rows to write to PostgreSQL.")

    full_loaded = pl.from_pandas(pd.read_sql("SELECT * FROM data", engine))
    _df_cache   = full_loaded
    _col_types  = detect_column_types(full_loaded.to_pandas())

    try:
        _nw.write_incremental(pandas_incremental, col_types)
    except Exception as e:
        print(f"[neo4j] ✗ {e} — dashboard still works via PostgreSQL.")

    print(f"[db] ✓ PostgreSQL total: {len(full_loaded)} rows, "
          f"{len(full_loaded.columns)} columns")
    return pandas_incremental, col_types


def _auto_load():
    fp     = EXCEL_FILE_PATH   or None
    folder = EXCEL_FOLDER_PATH or None
    if not fp and not folder:
        print("[db] ℹ No default path configured in config.py")
        return
    try:
        load_excel_to_postgres(filepath=fp, folder_path=folder)
    except Exception as e:
        print(f"[db] ✗ Auto-load failed: {e}")


_auto_load()