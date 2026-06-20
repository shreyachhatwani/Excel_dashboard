
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
import io
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
_df_cache  = None   # small sample only — for column detection
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
        host      = POSTGRES_HOST,
        port      = POSTGRES_PORT,
        user      = POSTGRES_USER,
        password  = POSTGRES_PASSWORD,
        dbname    = POSTGRES_DB,
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
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables "
                "  WHERE table_schema = 'public' AND table_name = 'data'"
                ")"
            ))
            return bool(result.scalar())
    except Exception:
        return False


def _rows_in_db_for_file(engine, fname: str) -> int:
    """
    PostgreSQL is the ONLY source of truth.
    Counts how many rows for this specific filename already exist in DB.
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


def _total_rows_in_db(engine) -> int:
    if not _table_exists(engine):
        return 0
    try:
        with engine.connect() as c:
            return int(c.execute(text("SELECT COUNT(*) FROM data")).scalar())
    except Exception:
        return 0


def _fast_write(df: pd.DataFrame, engine):
    """
    Uses PostgreSQL COPY command — fastest possible bulk insert.
    Creates table schema first if it doesn't exist.
    """
    # Create table structure if first time
    if not _table_exists(engine):
        df.head(0).to_sql(
            "data", engine,
            if_exists="append",
            index=False
        )
        print("[db] ✓ Created table schema")

    # Write data to in-memory CSV buffer
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)

    # Bulk copy via PostgreSQL COPY
    raw_conn = psycopg2.connect(
        host     = POSTGRES_HOST,
        port     = POSTGRES_PORT,
        user     = POSTGRES_USER,
        password = POSTGRES_PASSWORD,
        dbname   = POSTGRES_DB,
    )
    try:
        with raw_conn.cursor() as cur:
            cols = ', '.join([f'"{c}"' for c in df.columns])
            cur.copy_expert(
                f'COPY data ({cols}) FROM STDIN WITH CSV',
                buffer
            )
        raw_conn.commit()
        print(f"[db] ✓ Wrote {len(df)} rows via COPY")
    finally:
        raw_conn.close()


def _load_sample_for_types(engine):
    """
    Loads 5000 rows just to detect column types.
    Charts run against full PostgreSQL data directly — not this sample.
    This is purely for column type detection and dashboard column list.
    """
    global _df_cache, _col_types
    try:
        sample     = pl.from_pandas(
            pd.read_sql("SELECT * FROM data LIMIT 5000", engine)
        )
        _df_cache  = sample
        _col_types = detect_column_types(sample.to_pandas())
        print(f"[db] ✓ Column types detected from sample")
    except Exception as e:
        print(f"[db] ✗ Sample load failed: {e}")


def load_excel_to_postgres(filepath: str = None, folder_path: str = None):
    global _df_cache, _col_types

    fp     = filepath    or EXCEL_FILE_PATH    or None
    folder = folder_path or EXCEL_FOLDER_PATH  or None

    if not fp and not folder:
        raise ValueError(
            "No input provided. "
            "Set EXCEL_FILE_PATH or EXCEL_FOLDER_PATH in config.py"
        )

    # ── Load Excel file(s) ────────────────────────────────────────────────
    if folder:
        full_df, file_list = _loader.load_folder(folder)
    else:
        full_df, file_list = _loader.load_file(fp)

    engine     = _get_engine()
    new_frames = []

    for fpath in file_list:
        fname         = os.path.basename(fpath)
        file_df       = full_df.filter(pl.col("_source_file") == fname)
        total         = len(file_df)

        # Ask PostgreSQL directly — only source of truth
        already_in_db = _rows_in_db_for_file(engine, fname)

        if already_in_db >= total:
            print(f"[db] ↷  {fname}: {total} rows — already in PostgreSQL, skipping")
            continue

        if already_in_db == 0:
            print(f"[db] ✚  {fname}: loading all {total} rows")
            new_frames.append(file_df)
        else:
            missing = total - already_in_db
            print(f"[db] ✚  {fname}: loading {missing} missing rows "
                  f"(had {already_in_db}, now {total})")
            new_frames.append(file_df.slice(already_in_db, missing))

    if not new_frames:
        print("[db] ✓ All data already in PostgreSQL")
        _load_sample_for_types(engine)
        return None, _col_types

    # ── Prepare data ──────────────────────────────────────────────────────
    incremental_df     = pl.concat(new_frames, how="diagonal")
    pandas_incremental = incremental_df.to_pandas()
    col_types          = detect_column_types(pandas_incremental)

    # Coerce date columns
    for col, t in col_types.items():
        if t == "date" and col in incremental_df.columns:
            try:
                incremental_df = incremental_df.with_columns(
                    pl.col(col).cast(pl.String, strict=False).str.slice(0, 10)
                )
            except Exception:
                pass

    pandas_incremental = incremental_df.to_pandas()

    # ── Write to PostgreSQL via COPY (fast) ───────────────────────────────
    _fast_write(pandas_incremental, engine)

    # Update cache as a record (never used for load decisions)
    for fpath in file_list:
        fname   = os.path.basename(fpath)
        file_df = full_df.filter(pl.col("_source_file") == fname)
        _cache.update_cache(fpath, len(file_df))

    # ── Load sample for column type detection ─────────────────────────────
    _load_sample_for_types(engine)

    # ── Write to Neo4j ────────────────────────────────────────────────────
    try:
        _nw.write_incremental(pandas_incremental, col_types)
    except Exception as e:
        print(f"[neo4j] ✗ {e} — dashboard works via PostgreSQL.")

    total_in_db = _total_rows_in_db(engine)
    print(f"[db] ✓ PostgreSQL total: {total_in_db} rows")
    return pandas_incremental, col_types


def _auto_load():
    fp     = EXCEL_FILE_PATH   or None
    folder = EXCEL_FOLDER_PATH or None
    if not fp and not folder:
        print("[db] ℹ No path configured in config.py")
        return
    try:
        load_excel_to_postgres(filepath=fp, folder_path=folder)
    except Exception as e:
        print(f"[db] ✗ Auto-load failed: {e}")


_auto_load()