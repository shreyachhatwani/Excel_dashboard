
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
# db.py
# import os
# import io
# import psycopg2
# import pandas as pd
# import polars as pl
# from sqlalchemy import create_engine, text
# from urllib.parse import quote_plus

# from detector import detect_column_types
# import loader as _loader
# import cache  as _cache
# from config import (
#     EXCEL_FILE_PATH, EXCEL_FOLDER_PATH,
#     POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
# )

# _conn      = None
# _engine    = None
# _df_cache  = None
# _col_types = None


# def _get_engine():
#     global _engine
#     if _engine is None:
#         safe_password = quote_plus(POSTGRES_PASSWORD)
#         url = (
#             f"postgresql+psycopg2://{POSTGRES_USER}:{safe_password}"
#             f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
#         )
#         _engine = create_engine(url, pool_pre_ping=True)
#     return _engine


# def get_connection():
#     global _conn
#     try:
#         if _conn is not None and not _conn.closed:
#             cur = _conn.cursor()
#             cur.execute("SELECT 1")
#             cur.close()
#             return _conn
#     except Exception:
#         _conn = None
#     _conn = psycopg2.connect(
#         host      = POSTGRES_HOST,
#         port      = POSTGRES_PORT,
#         user      = POSTGRES_USER,
#         password  = POSTGRES_PASSWORD,
#         dbname    = POSTGRES_DB,
#     )
#     _conn.autocommit = True
#     return _conn


# def get_col_types():
#     return _col_types


# def get_df():
#     return _df_cache


# def _table_exists(engine) -> bool:
#     try:
#         with engine.connect() as c:
#             result = c.execute(text(
#                 "SELECT EXISTS ("
#                 "  SELECT 1 FROM information_schema.tables "
#                 "  WHERE table_schema = 'public' AND table_name = 'data'"
#                 ")"
#             ))
#             return bool(result.scalar())
#     except Exception:
#         return False


# def _rows_in_db_for_file(engine, fname: str) -> int:
#     """PostgreSQL is the only source of truth."""
#     if not _table_exists(engine):
#         return 0
#     try:
#         with engine.connect() as c:
#             result = c.execute(
#                 text('SELECT COUNT(*) FROM data WHERE "_source_file" = :fname'),
#                 {"fname": fname}
#             )
#             return int(result.scalar())
#     except Exception:
#         return 0


# def _get_all_loaded_files(engine) -> dict:
#     """
#     Returns {filename: row_count} for every file in PostgreSQL.
#     One query instead of one per file — much faster for large folders.
#     """
#     if not _table_exists(engine):
#         return {}
#     try:
#         with engine.connect() as c:
#             result = c.execute(text(
#                 'SELECT "_source_file", COUNT(*) as cnt '
#                 'FROM data GROUP BY "_source_file"'
#             ))
#             return {row[0]: row[1] for row in result}
#     except Exception:
#         return {}


# def _total_rows_in_db(engine) -> int:
#     if not _table_exists(engine):
#         return 0
#     try:
#         with engine.connect() as c:
#             return int(c.execute(text("SELECT COUNT(*) FROM data")).scalar())
#     except Exception:
#         return 0


# def _get_db_columns(engine) -> set:
#     if not _table_exists(engine):
#         return set()
#     try:
#         with engine.connect() as c:
#             result = c.execute(text(
#                 "SELECT column_name FROM information_schema.columns "
#                 "WHERE table_schema = 'public' AND table_name = 'data'"
#             ))
#             return {row[0] for row in result}
#     except Exception:
#         return set()


# def _add_missing_columns(engine, df_cols: list):
#     """Add any columns this file has that the table doesn't yet."""
#     existing = _get_db_columns(engine)
#     missing  = [c for c in df_cols if c not in existing]
#     if not missing:
#         return
#     raw_conn = psycopg2.connect(
#         host     = POSTGRES_HOST,
#         port     = POSTGRES_PORT,
#         user     = POSTGRES_USER,
#         password = POSTGRES_PASSWORD,
#         dbname   = POSTGRES_DB,
#     )
#     try:
#         with raw_conn.cursor() as cur:
#             for col in missing:
#                 cur.execute(f'ALTER TABLE data ADD COLUMN "{col}" TEXT')
#                 print(f"[db] + Added missing column: {col}")
#         raw_conn.commit()
#     finally:
#         raw_conn.close()


# def _fast_write(df: pd.DataFrame, engine):
#     """Bulk write via PostgreSQL COPY — fastest possible method."""
#     if not _table_exists(engine):
#         df.head(0).to_sql(
#             "data", engine,
#             if_exists="append",
#             index=False
#         )
#         print("[db] ✓ Created table schema")

#     _add_missing_columns(engine, list(df.columns))

#     db_cols     = _get_db_columns(engine)
#     write_cols  = [c for c in df.columns if c in db_cols]
#     df_to_write = df[write_cols]

#     buffer = io.StringIO()
#     df_to_write.to_csv(buffer, index=False, header=False)
#     buffer.seek(0)

#     raw_conn = psycopg2.connect(
#         host     = POSTGRES_HOST,
#         port     = POSTGRES_PORT,
#         user     = POSTGRES_USER,
#         password = POSTGRES_PASSWORD,
#         dbname   = POSTGRES_DB,
#     )
#     try:
#         with raw_conn.cursor() as cur:
#             cols = ', '.join([f'"{c}"' for c in write_cols])
#             cur.copy_expert(
#                 f'COPY data ({cols}) FROM STDIN WITH CSV',
#                 buffer
#             )
#         raw_conn.commit()
#         print(f"[db] ✓ Wrote {len(df_to_write)} rows via COPY")
#     finally:
#         raw_conn.close()


# def _update_row_count_cache(engine):
#     """
#     Store total row count in data_meta table.
#     /ready reads this instead of doing COUNT(*) on 7M rows — instant.
#     """
#     try:
#         with engine.connect() as c:
#             c.execute(text("""
#                 CREATE TABLE IF NOT EXISTS data_meta (
#                     key TEXT PRIMARY KEY,
#                     value TEXT
#                 )
#             """))
#             c.execute(text("""
#                 INSERT INTO data_meta (key, value)
#                 VALUES ('row_count', (SELECT COUNT(*) FROM data)::TEXT)
#                 ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
#             """))
#             c.commit()
#         print("[db] ✓ Row count cache updated")
#     except Exception as e:
#         print(f"[db] ✗ Could not update row count cache: {e}")


# def _load_sample_for_types(engine):
#     """
#     5000-row sample for column type detection only.
#     All charts query PostgreSQL directly — not this sample.
#     """
#     global _df_cache, _col_types
#     try:
#         sample     = pl.from_pandas(
#             pd.read_sql("SELECT * FROM data LIMIT 5000", engine)
#         )
#         _df_cache  = sample
#         _col_types = detect_column_types(sample.to_pandas())
#         print("[db] ✓ Column types detected")
#         # Update cached row count so /ready is instant
#         _update_row_count_cache(engine)
#     except Exception as e:
#         print(f"[db] ✗ Sample load failed: {e}")


# def load_excel_to_postgres(filepath: str = None, folder_path: str = None):
#     global _df_cache, _col_types

#     fp     = filepath    or EXCEL_FILE_PATH    or None
#     folder = folder_path or EXCEL_FOLDER_PATH  or None

#     if not fp and not folder:
#         raise ValueError("No input provided in config.py")

#     engine = _get_engine()

#     # Get file list
#     if folder:
#         file_list = _loader.load_folder(folder)
#     else:
#         file_list = [fp]

#     # One query to get all already-loaded files from PostgreSQL
#     already_loaded = _get_all_loaded_files(engine)
#     print(f"[db] PostgreSQL already has {len(already_loaded)} file(s) loaded")

#     for fpath in file_list:
#         fname = os.path.basename(fpath)

#         # If PostgreSQL has any rows for this file — skip entirely
#         # Don't even open the file from disk
#         already_in_db = already_loaded.get(fname, 0)

#         if already_in_db > 0:
#             print(f"[db] ↷  {fname}: {already_in_db:,} rows — "
#                   f"already in PostgreSQL, skipping")
#             continue

#         # Only reach here if file is genuinely new
#         print(f"[db] 📖 Reading {fname} from disk...")
#         try:
#             single_df, _ = _loader.load_file(fpath)
#         except Exception as e:
#             print(f"[loader] ✗ Skipped {fname}: {e}")
#             continue

#         total = len(single_df)
#         print(f"[db] ✚  {fname}: loading all {total:,} rows")

#         # Coerce date columns
#         pandas_df = single_df.to_pandas()
#         col_types = detect_column_types(pandas_df)
#         for col, t in col_types.items():
#             if t == "date" and col in single_df.columns:
#                 try:
#                     single_df = single_df.with_columns(
#                         pl.col(col).cast(pl.String, strict=False).str.slice(0, 10)
#                     )
#                 except Exception:
#                     pass
#         pandas_df = single_df.to_pandas()

#         # Write to PostgreSQL via COPY
#         _fast_write(pandas_df, engine)

#         # Update cache as record
#         _cache.update_cache(fpath, total)

#         # Free memory before next file
#         del single_df, pandas_df

#     # Load 5000-row sample for type detection
#     # Also updates the row count cache so /ready is instant
#     _load_sample_for_types(engine)

#     total_in_db = _total_rows_in_db(engine)
#     print(f"[db] ✓ Done — PostgreSQL total: {total_in_db:,} rows")
#     return None, _col_types


# def _auto_load():
#     fp     = EXCEL_FILE_PATH   or None
#     folder = EXCEL_FOLDER_PATH or None
#     if not fp and not folder:
#         print("[db] ℹ No path configured in config.py")
#         return
#     try:
#         load_excel_to_postgres(filepath=fp, folder_path=folder)
#     except Exception as e:
#         print(f"[db] ✗ Auto-load failed: {e}")


# _auto_load()

# db.py
import os
import io
import re
import psycopg2
import pandas as pd
import polars as pl
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
 
from detector import detect_column_types
import loader as _loader
import cache  as _cache
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
    """PostgreSQL is the only source of truth."""
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
 
 
def _get_all_loaded_files(engine) -> dict:
    """
    Returns {filename: row_count} for every file in PostgreSQL.
    One query instead of one per file — much faster for large folders.
    """
    if not _table_exists(engine):
        return {}
    try:
        with engine.connect() as c:
            result = c.execute(text(
                'SELECT "_source_file", COUNT(*) as cnt '
                'FROM data GROUP BY "_source_file"'
            ))
            return {row[0]: row[1] for row in result}
    except Exception:
        return {}
 
 
def _total_rows_in_db(engine) -> int:
    if not _table_exists(engine):
        return 0
    try:
        with engine.connect() as c:
            return int(c.execute(text("SELECT COUNT(*) FROM data")).scalar())
    except Exception:
        return 0
 
 
def _get_db_columns(engine) -> set:
    if not _table_exists(engine):
        return set()
    try:
        with engine.connect() as c:
            result = c.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'data'"
            ))
            return {row[0] for row in result}
    except Exception:
        return set()
 
 
def _add_missing_columns(engine, df_cols: list):
    """Add any columns this file has that the table doesn't yet."""
    existing = _get_db_columns(engine)
    missing  = [c for c in df_cols if c not in existing]
    if not missing:
        return
    raw_conn = psycopg2.connect(
        host     = POSTGRES_HOST,
        port     = POSTGRES_PORT,
        user     = POSTGRES_USER,
        password = POSTGRES_PASSWORD,
        dbname   = POSTGRES_DB,
    )
    try:
        with raw_conn.cursor() as cur:
            for col in missing:
                cur.execute(f'ALTER TABLE data ADD COLUMN "{col}" TEXT')
                print(f"[db] + Added missing column: {col}")
        raw_conn.commit()
    finally:
        raw_conn.close()
 
 
def _fast_write(df: pd.DataFrame, engine):
    """Bulk write via PostgreSQL COPY — fastest possible method."""
    if not _table_exists(engine):
        df.head(0).to_sql(
            "data", engine,
            if_exists="append",
            index=False
        )
        print("[db] ✓ Created table schema")
 
    _add_missing_columns(engine, list(df.columns))
 
    db_cols     = _get_db_columns(engine)
    write_cols  = [c for c in df.columns if c in db_cols]
    df_to_write = df[write_cols]
 
    buffer = io.StringIO()
    df_to_write.to_csv(buffer, index=False, header=False)
    buffer.seek(0)
 
    raw_conn = psycopg2.connect(
        host     = POSTGRES_HOST,
        port     = POSTGRES_PORT,
        user     = POSTGRES_USER,
        password = POSTGRES_PASSWORD,
        dbname   = POSTGRES_DB,
    )
    try:
        with raw_conn.cursor() as cur:
            cols = ', '.join([f'"{c}"' for c in write_cols])
            cur.copy_expert(
                f'COPY data ({cols}) FROM STDIN WITH CSV',
                buffer
            )
        raw_conn.commit()
        print(f"[db] ✓ Wrote {len(df_to_write)} rows via COPY")
    finally:
        raw_conn.close()
 
 
def _update_row_count_cache(engine):
    """
    Store total row count in data_meta table.
    /ready reads this instead of doing COUNT(*) on 7M rows — instant.
    """
    try:
        with engine.connect() as c:
            c.execute(text("""
                CREATE TABLE IF NOT EXISTS data_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """))
            c.execute(text("""
                INSERT INTO data_meta (key, value)
                VALUES ('row_count', (SELECT COUNT(*) FROM data)::TEXT)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """))
            c.commit()
        print("[db] ✓ Row count cache updated")
    except Exception as e:
        print(f"[db] ✗ Could not update row count cache: {e}")
 
 
def _safe_index_name(col: str) -> str:
    """Turn a column name into a valid, predictable Postgres index name."""
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", col).lower()
    name = f"idx_data_{safe}"
    return name[:63]   # Postgres identifier length limit
 
 
def _ensure_indexes(engine, col_types: dict):
    """
    Adds a database index on every numeric column, so the box-plot and
    outlier queries (which need the column in sorted order) don't have
    to sort the whole table from scratch on every request.
 
    Uses CREATE INDEX IF NOT EXISTS, so this is safe to call every time
    the server starts:
      - The FIRST time a column is indexed, Postgres does real work
        (one pass over the table to build the sorted structure). On a
        multi-million-row table this can take a little while.
      - Every time after that, it's an instant no-op for columns that
        already have their index — nothing gets rebuilt.
    """
    if not col_types:
        return
    numeric_cols = [c for c, t in col_types.items() if t == "numeric"]
    if not numeric_cols:
        return
 
    for col in numeric_cols:
        idx_name = _safe_index_name(col)
        try:
            with engine.connect() as c:
                c.execute(text(
                    f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON data ("{col}")'
                ))
                c.commit()
            print(f"[db] ✓ Index ready on '{col}'")
        except Exception as e:
            print(f"[db] ✗ Could not index '{col}': {e}")
 
 
def _load_sample_for_types(engine):
    """
    5000-row sample for column type detection only.
    All charts query PostgreSQL directly — not this sample.
    """
    global _df_cache, _col_types
    try:
        sample     = pl.from_pandas(
            pd.read_sql("SELECT * FROM data LIMIT 5000", engine)
        )
        _df_cache  = sample
        _col_types = detect_column_types(sample.to_pandas())
        print("[db] ✓ Column types detected")
        # Update cached row count so /ready is instant
        _update_row_count_cache(engine)
        # Make sure numeric columns are indexed (instant if already done)
        _ensure_indexes(engine, _col_types)
    except Exception as e:
        print(f"[db] ✗ Sample load failed: {e}")
 
 
def load_excel_to_postgres(filepath: str = None, folder_path: str = None):
    global _df_cache, _col_types
 
    fp     = filepath    or EXCEL_FILE_PATH    or None
    folder = folder_path or EXCEL_FOLDER_PATH  or None
 
    if not fp and not folder:
        raise ValueError("No input provided in config.py")
 
    engine = _get_engine()
 
    # Get file list
    if folder:
        file_list = _loader.load_folder(folder)
    else:
        file_list = [fp]
 
    # One query to get all already-loaded files from PostgreSQL
    already_loaded = _get_all_loaded_files(engine)
    print(f"[db] PostgreSQL already has {len(already_loaded)} file(s) loaded")
 
    for fpath in file_list:
        fname = os.path.basename(fpath)
 
        # If PostgreSQL has any rows for this file — skip entirely
        # Don't even open the file from disk
        already_in_db = already_loaded.get(fname, 0)
 
        if already_in_db > 0:
            print(f"[db] ↷  {fname}: {already_in_db:,} rows — "
                  f"already in PostgreSQL, skipping")
            continue
 
        # Only reach here if file is genuinely new
        print(f"[db] 📖 Reading {fname} from disk...")
        try:
            single_df, _ = _loader.load_file(fpath)
        except Exception as e:
            print(f"[loader] ✗ Skipped {fname}: {e}")
            continue
 
        total = len(single_df)
        print(f"[db] ✚  {fname}: loading all {total:,} rows")
 
        # Coerce date columns
        pandas_df = single_df.to_pandas()
        col_types = detect_column_types(pandas_df)
        for col, t in col_types.items():
            if t == "date" and col in single_df.columns:
                try:
                    single_df = single_df.with_columns(
                        pl.col(col).cast(pl.String, strict=False).str.slice(0, 10)
                    )
                except Exception:
                    pass
        pandas_df = single_df.to_pandas()
 
        # Write to PostgreSQL via COPY
        _fast_write(pandas_df, engine)
 
        # Update cache as record
        _cache.update_cache(fpath, total)
 
        # Free memory before next file
        del single_df, pandas_df
 
    # Load 5000-row sample for type detection
    # Also updates the row count cache so /ready is instant
    _load_sample_for_types(engine)
 
    total_in_db = _total_rows_in_db(engine)
    print(f"[db] ✓ Done — PostgreSQL total: {total_in_db:,} rows")
    return None, _col_types
 
 
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