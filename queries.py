
# queries.py
# import psycopg2
# import polars as pl


# def _query(conn, sql: str, params=None) -> pl.DataFrame:
#     """Execute SQL on a psycopg2 connection → Polars DataFrame."""
#     with conn.cursor() as cur:
#         cur.execute(sql, params or ())
#         cols = [d[0] for d in cur.description]
#         rows = cur.fetchall()
#     if not rows:
#         return pl.DataFrame()
#     return pl.DataFrame([dict(zip(cols, r)) for r in rows])


# # ── SUMMARY ───────────────────────────────────────────────────────────────────

# def q_row_count(conn) -> pl.DataFrame:
#     return _query(conn, "SELECT COUNT(*) AS total_rows FROM data")


# def q_column_summary(conn, col_types: dict) -> pl.DataFrame:
#     """
#     Single query for null counts across all columns.
#     No COUNT(DISTINCT) — that was extremely slow on large datasets.
#     Null chart only needs null counts, not distinct counts.
#     """
#     if not col_types:
#         return pl.DataFrame()

#     cols  = list(col_types.keys())
#     parts = []
#     for col in cols:
#         parts.append(
#             f'SUM(CASE WHEN "{col}" IS NULL THEN 1 ELSE 0 END) AS "null__{col}"'
#         )

#     sql = f"SELECT COUNT(*) AS __total__, {', '.join(parts)} FROM data"

#     with conn.cursor() as cur:
#         cur.execute(sql)
#         row  = cur.fetchone()
#         desc = [d[0] for d in cur.description]

#     result = dict(zip(desc, row))
#     total  = result["__total__"]

#     rows = []
#     for col in cols:
#         null_count = result.get(f"null__{col}", 0) or 0
#         rows.append({
#             "column_name":     col,
#             "count":           total - null_count,
#             "nulls":           null_count,
#             "distinct_values": 0,
#             "col_type":        col_types[col],
#         })

#     return pl.DataFrame(rows)


# def q_numeric_stats(conn, numeric_cols: list) -> pl.DataFrame:
#     if not numeric_cols:
#         return pl.DataFrame()
#     parts = [
#         f"""
#         SELECT %s                             AS column_name,
#                MIN("{col}")                   AS min_val,
#                MAX("{col}")                   AS max_val,
#                ROUND(AVG("{col}")::numeric, 2) AS avg_val,
#                COUNT("{col}")                 AS count
#         FROM data
#         """
#         for col in numeric_cols
#     ]
#     return _query(conn, " UNION ALL ".join(parts), tuple(numeric_cols))


# # ── CATEGORIES ────────────────────────────────────────────────────────────────

# def q_category_counts(conn, cat_col: str, top_n: int = 10) -> pl.DataFrame:
#     sql = f"""
#         SELECT "{cat_col}"  AS category,
#                COUNT(*)     AS count,
#                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
#         FROM data
#         WHERE "{cat_col}" IS NOT NULL
#         GROUP BY "{cat_col}"
#         ORDER BY count DESC
#         LIMIT %s
#     """
#     return _query(conn, sql, (top_n,))


# def q_category_aggregate(conn, cat_col: str, num_col: str,
#                           agg: str = "SUM", top_n: int = 10) -> pl.DataFrame:
#     safe_agg = agg.upper()
#     if safe_agg not in ("SUM", "AVG", "MIN", "MAX", "COUNT"):
#         safe_agg = "SUM"
#     sql = f"""
#         SELECT "{cat_col}"                              AS category,
#                ROUND({safe_agg}("{num_col}")::numeric, 2) AS value
#         FROM data
#         WHERE "{cat_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
#         GROUP BY "{cat_col}"
#         ORDER BY value DESC
#         LIMIT %s
#     """
#     return _query(conn, sql, (top_n,))


# def q_pareto(conn, cat_col: str, num_col: str, top_n: int = 20) -> pl.DataFrame:
#     sql = f"""
#         WITH base AS (
#             SELECT "{cat_col}" AS category,
#                    SUM("{num_col}") AS total
#             FROM data
#             WHERE "{cat_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
#             GROUP BY "{cat_col}"
#             ORDER BY total DESC
#             LIMIT %s
#         ),
#         totals AS (SELECT *, SUM(total) OVER () AS grand_total FROM base)
#         SELECT category,
#                total,
#                ROUND((100.0 * SUM(total) OVER (ORDER BY total DESC)
#                       / grand_total)::numeric, 1) AS cum_pct
#         FROM totals
#     """
#     return _query(conn, sql, (top_n,))


# def q_cross_tab(conn, cat_col1: str, cat_col2: str) -> pl.DataFrame:
#     sql = f"""
#         SELECT "{cat_col1}" AS col1,
#                "{cat_col2}" AS col2,
#                COUNT(*)     AS count
#         FROM data
#         WHERE "{cat_col1}" IS NOT NULL AND "{cat_col2}" IS NOT NULL
#         GROUP BY "{cat_col1}", "{cat_col2}"
#     """
#     df = _query(conn, sql)
#     if df.is_empty():
#         return df
#     return (
#         df.pivot(values="count", index="col1", columns="col2",
#                  aggregate_function="sum")
#           .fill_null(0)
#     )


# # ── DISTRIBUTIONS ─────────────────────────────────────────────────────────────

# def q_histogram_data(conn, num_col: str) -> pl.DataFrame:
#     return _query(
#         conn,
#         f'SELECT "{num_col}" AS value FROM data WHERE "{num_col}" IS NOT NULL'
#     )


# def q_outliers_iqr(conn, num_col: str) -> pl.DataFrame:
#     sql = f"""
#         WITH quartiles AS (
#             SELECT "{num_col}" AS val,
#                    NTILE(4) OVER (ORDER BY "{num_col}") AS quartile
#             FROM data WHERE "{num_col}" IS NOT NULL
#         ),
#         bounds AS (
#             SELECT MAX(CASE WHEN quartile = 1 THEN val END) AS q1,
#                    MAX(CASE WHEN quartile = 3 THEN val END) AS q3
#             FROM quartiles
#         )
#         SELECT d.*,
#                b.q1, b.q3,
#                (b.q3 - b.q1)             AS iqr,
#                b.q1 - 1.5*(b.q3 - b.q1) AS lower_fence,
#                b.q3 + 1.5*(b.q3 - b.q1) AS upper_fence
#         FROM data d, bounds b
#         WHERE d."{num_col}" < b.q1 - 1.5*(b.q3 - b.q1)
#            OR d."{num_col}" > b.q3 + 1.5*(b.q3 - b.q1)
#         ORDER BY d."{num_col}" DESC
#         LIMIT 100
#     """
#     return _query(conn, sql)


# # ── RELATIONSHIPS ─────────────────────────────────────────────────────────────

# def q_scatter_data(conn, x_col: str, y_col: str,
#                    color_col: str = None, size_col: str = None) -> pl.DataFrame:
#     cols  = [f'"{x_col}" AS x', f'"{y_col}" AS y']
#     where = f'"{x_col}" IS NOT NULL AND "{y_col}" IS NOT NULL'
#     if color_col:
#         cols.append(f'"{color_col}" AS color')
#     if size_col:
#         cols.append(f'"{size_col}" AS size')
#     return _query(conn,
#         f"SELECT {', '.join(cols)} FROM data WHERE {where} LIMIT 2000")


# def q_scatter_matrix(conn, numeric_cols: list) -> pl.DataFrame:
#     if len(numeric_cols) < 2:
#         return pl.DataFrame()
#     col_list = ", ".join([f'"{c}"' for c in numeric_cols[:6]])
#     return _query(conn, f"SELECT {col_list} FROM data LIMIT 1000")


# # ── TIME TRENDS ───────────────────────────────────────────────────────────────

# def q_time_series(conn, date_col: str, num_col: str,
#                   agg: str = "SUM", period: str = "Month") -> pl.DataFrame:
#     safe_agg = agg.upper()
#     if safe_agg not in ("SUM", "AVG", "MIN", "MAX", "COUNT"):
#         safe_agg = "SUM"

#     period_expr = {
#         "Day":     f'TO_CHAR("{date_col}"::date, \'YYYY-MM-DD\')',
#         "Week":    f'TO_CHAR("{date_col}"::date, \'IYYY-IW\')',
#         "Month":   f'TO_CHAR("{date_col}"::date, \'YYYY-MM\')',
#         "Quarter": f'CONCAT(EXTRACT(YEAR FROM "{date_col}"::date), \'-Q\','
#                    f' EXTRACT(QUARTER FROM "{date_col}"::date))',
#         "Year":    f'EXTRACT(YEAR FROM "{date_col}"::date)::text',
#     }.get(period, f'TO_CHAR("{date_col}"::date, \'YYYY-MM\')')

#     sql = f"""
#         SELECT {period_expr}           AS period,
#                {safe_agg}("{num_col}") AS value
#         FROM data
#         WHERE "{date_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
#         GROUP BY period
#         ORDER BY period
#     """
#     return _query(conn, sql)


# def q_mom_change(conn, date_col: str, num_col: str) -> pl.DataFrame:
#     sql = f"""
#         WITH monthly AS (
#             SELECT TO_CHAR("{date_col}"::date, 'YYYY-MM') AS month,
#                    SUM("{num_col}") AS total
#             FROM data
#             WHERE "{date_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
#             GROUP BY month
#             ORDER BY month
#         )
#         SELECT month,
#                total,
#                LAG(total) OVER (ORDER BY month) AS prev_total,
#                ROUND(
#                  (100.0 * (total - LAG(total) OVER (ORDER BY month))
#                        / NULLIF(LAG(total) OVER (ORDER BY month), 0))::numeric,
#                1) AS pct_change
#         FROM monthly
#     """
#     return _query(conn, sql)


# def q_running_total(conn, date_col: str, num_col: str) -> pl.DataFrame:
#     sql = f"""
#         WITH daily AS (
#             SELECT TO_CHAR("{date_col}"::date, 'YYYY-MM-DD') AS day,
#                    SUM("{num_col}")                          AS daily_total
#             FROM data
#             WHERE "{date_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
#             GROUP BY day
#             ORDER BY day
#         )
#         SELECT day,
#                daily_total,
#                SUM(daily_total) OVER (ORDER BY day) AS running_total
#         FROM daily
#     """
#     return _query(conn, sql)


# def q_day_of_week(conn, date_col: str, num_col: str) -> pl.DataFrame:
#     sql = f"""
#         SELECT EXTRACT(DOW FROM "{date_col}"::date)::int     AS dow_num,
#                TO_CHAR("{date_col}"::date, 'Day')             AS day_name,
#                ROUND(AVG("{num_col}")::numeric, 2)            AS avg_value
#         FROM data
#         WHERE "{date_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
#         GROUP BY dow_num, day_name
#         ORDER BY dow_num
#     """
#     return _query(conn, sql)


# def q_seasonality(conn, date_col: str, num_col: str) -> pl.DataFrame:
#     sql = f"""
#         SELECT EXTRACT(MONTH FROM "{date_col}"::date)::int AS month_num,
#                TO_CHAR("{date_col}"::date, 'Mon')           AS month_name,
#                ROUND(AVG("{num_col}")::numeric, 2)          AS avg_value
#         FROM data
#         WHERE "{date_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
#         GROUP BY month_num, month_name
#         ORDER BY month_num
#     """
#     return _query(conn, sql)

import psycopg2
import polars as pl
import pandas as pd
 
 
def _query(conn, sql: str, params=None) -> pl.DataFrame:
    """Execute SQL on a psycopg2 connection → Polars DataFrame."""
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    if not rows:
        return pl.DataFrame()
    return pl.DataFrame([dict(zip(cols, r)) for r in rows])
 
 
# ── SUMMARY ───────────────────────────────────────────────────────────────────
 
def q_row_count(conn) -> pl.DataFrame:
    return _query(conn, "SELECT COUNT(*) AS total_rows FROM data")
 
 
def q_column_summary(conn, col_types: dict) -> pl.DataFrame:
    """
    Single query for null counts across all columns.
    No COUNT(DISTINCT) — that was extremely slow on large datasets.
    Null chart only needs null counts, not distinct counts.
    """
    if not col_types:
        return pl.DataFrame()
 
    cols  = list(col_types.keys())
    parts = []
    for col in cols:
        parts.append(
            f'SUM(CASE WHEN "{col}" IS NULL THEN 1 ELSE 0 END) AS "null__{col}"'
        )
 
    sql = f"SELECT COUNT(*) AS __total__, {', '.join(parts)} FROM data"
 
    with conn.cursor() as cur:
        cur.execute(sql)
        row  = cur.fetchone()
        desc = [d[0] for d in cur.description]
 
    result = dict(zip(desc, row))
    total  = result["__total__"]
 
    rows = []
    for col in cols:
        null_count = result.get(f"null__{col}", 0) or 0
        rows.append({
            "column_name":     col,
            "count":           total - null_count,
            "nulls":           null_count,
            "distinct_values": 0,
            "col_type":        col_types[col],
        })
 
    return pl.DataFrame(rows)
 
 
def q_numeric_stats(conn, numeric_cols: list) -> pl.DataFrame:
    if not numeric_cols:
        return pl.DataFrame()
    parts = [
        f"""
        SELECT %s                             AS column_name,
               MIN("{col}")                   AS min_val,
               MAX("{col}")                   AS max_val,
               ROUND(AVG("{col}")::numeric, 2) AS avg_val,
               COUNT("{col}")                 AS count
        FROM data
        """
        for col in numeric_cols
    ]
    return _query(conn, " UNION ALL ".join(parts), tuple(numeric_cols))
 
 
# ── CATEGORIES ────────────────────────────────────────────────────────────────
 
def q_category_counts(conn, cat_col: str, top_n: int = 10) -> pl.DataFrame:
    sql = f"""
        SELECT "{cat_col}"  AS category,
               COUNT(*)     AS count,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM data
        WHERE "{cat_col}" IS NOT NULL
        GROUP BY "{cat_col}"
        ORDER BY count DESC
        LIMIT %s
    """
    return _query(conn, sql, (top_n,))
 
 
def q_category_aggregate(conn, cat_col: str, num_col: str,
                          agg: str = "SUM", top_n: int = 10) -> pl.DataFrame:
    safe_agg = agg.upper()
    if safe_agg not in ("SUM", "AVG", "MIN", "MAX", "COUNT"):
        safe_agg = "SUM"
    sql = f"""
        SELECT "{cat_col}"                              AS category,
               ROUND({safe_agg}("{num_col}")::numeric, 2) AS value
        FROM data
        WHERE "{cat_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
        GROUP BY "{cat_col}"
        ORDER BY value DESC
        LIMIT %s
    """
    return _query(conn, sql, (top_n,))
 
 
def q_pareto(conn, cat_col: str, num_col: str, top_n: int = 20) -> pl.DataFrame:
    sql = f"""
        WITH base AS (
            SELECT "{cat_col}" AS category,
                   SUM("{num_col}") AS total
            FROM data
            WHERE "{cat_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
            GROUP BY "{cat_col}"
            ORDER BY total DESC
            LIMIT %s
        ),
        totals AS (SELECT *, SUM(total) OVER () AS grand_total FROM base)
        SELECT category,
               total,
               ROUND((100.0 * SUM(total) OVER (ORDER BY total DESC)
                      / grand_total)::numeric, 1) AS cum_pct
        FROM totals
    """
    return _query(conn, sql, (top_n,))
 
 
def q_cross_tab(conn, cat_col1: str, cat_col2: str) -> pl.DataFrame:
    sql = f"""
        SELECT "{cat_col1}" AS col1,
               "{cat_col2}" AS col2,
               COUNT(*)     AS count
        FROM data
        WHERE "{cat_col1}" IS NOT NULL AND "{cat_col2}" IS NOT NULL
        GROUP BY "{cat_col1}", "{cat_col2}"
    """
    df = _query(conn, sql)
    if df.is_empty():
        return df
    return (
        df.pivot(values="count", index="col1", columns="col2",
                 aggregate_function="sum")
          .fill_null(0)
    )
 
 
# ── DISTRIBUTIONS ─────────────────────────────────────────────────────────────
#
# These use the FULL dataset — no sampling. The trick for staying fast on
# millions of rows isn't to look at less data; it's to never pull the raw
# values out of Postgres at all. Postgres counts/aggregates internally and
# sends back a tiny summary (a few dozen bucket counts, or a handful of
# numbers for the box plot) instead of millions of individual rows.
 
def q_histogram_data(conn, num_col: str, bins: int = 40) -> pl.DataFrame:
    """
    Exact histogram across every row, computed as binned counts inside
    Postgres (one pass over the column) — only `bins` rows ever come back,
    not the raw values.
    """
    sql = f"""
        WITH stats AS (
            SELECT MIN("{num_col}") AS min_v, MAX("{num_col}") AS max_v
            FROM data WHERE "{num_col}" IS NOT NULL
        ),
        bucketed AS (
            SELECT
                CASE
                    WHEN s.max_v = s.min_v THEN 0
                    ELSE width_bucket("{num_col}", s.min_v, s.max_v, %s)
                END AS bucket,
                s.min_v, s.max_v
            FROM data, stats s
            WHERE "{num_col}" IS NOT NULL
        )
        SELECT bucket,
               COUNT(*)    AS count,
               MIN(min_v)  AS min_v,
               MIN(max_v)  AS max_v
        FROM bucketed
        GROUP BY bucket
        ORDER BY bucket
    """
    return _query(conn, sql, (bins,))
 
 
# Cache the five-number summary per column. The box plot and the outlier
# list both need it, and the frontend fires both requests at the same time
# — without this, Postgres would run the same full-table percentile scan
# twice, in parallel, for every single chart load. Cleared whenever new
# data is loaded (see db.py).
_dist_stats_cache: dict = {}
 
 
def clear_distribution_cache():
    _dist_stats_cache.clear()
 
 
def q_distribution_stats(conn, num_col: str) -> pl.DataFrame:
    """
    Exact five-number summary (min, Q1, median, Q3, max) over the full
    column, computed in one aggregate pass with percentile_cont. Used to
    draw the box plot without ever transferring individual row values.
    """
    if num_col in _dist_stats_cache:
        return _dist_stats_cache[num_col]
 
    sql = f"""
        SELECT
            MIN("{num_col}")                                            AS min_val,
            percentile_cont(0.25) WITHIN GROUP (ORDER BY "{num_col}")    AS q1,
            percentile_cont(0.50) WITHIN GROUP (ORDER BY "{num_col}")    AS median,
            percentile_cont(0.75) WITHIN GROUP (ORDER BY "{num_col}")    AS q3,
            MAX("{num_col}")                                            AS max_val,
            COUNT("{num_col}")                                          AS n
        FROM data
        WHERE "{num_col}" IS NOT NULL
    """
    result = _query(conn, sql)
    _dist_stats_cache[num_col] = result
    return result
 
 
def q_outliers_iqr(conn, num_col: str, limit: int = 200) -> pl.DataFrame:
    """
    Exact outliers: fences come from the real Q1/Q3 over the WHOLE column
    (via q_distribution_stats), then we pull back only the rows that
    actually fall outside those fences, capped at `limit` for display.
 
    This still touches every row once to compute the fences (unavoidable
    if you want an exact answer rather than an estimate), but it never
    sorts the whole table the way the original NTILE() version did, and
    it never ships more than `limit` rows back to the browser.
    """
    stats = q_distribution_stats(conn, num_col).to_pandas()
    if stats.empty or pd.isna(stats.loc[0, "q1"]) or pd.isna(stats.loc[0, "q3"]):
        return pl.DataFrame()
 
    q1  = float(stats.loc[0, "q1"])
    q3  = float(stats.loc[0, "q3"])
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
 
    sql = f"""
        SELECT *,
               %s AS q1, %s AS q3, %s AS iqr,
               %s AS lower_fence, %s AS upper_fence
        FROM data
        WHERE "{num_col}" < %s OR "{num_col}" > %s
        ORDER BY "{num_col}" DESC
        LIMIT %s
    """
    params = (q1, q3, iqr, lower, upper, lower, upper, limit)
    return _query(conn, sql, params)
 
 
# ── RELATIONSHIPS ─────────────────────────────────────────────────────────────
 
def q_scatter_data(conn, x_col: str, y_col: str,
                   color_col: str = None, size_col: str = None) -> pl.DataFrame:
    cols  = [f'"{x_col}" AS x', f'"{y_col}" AS y']
    where = f'"{x_col}" IS NOT NULL AND "{y_col}" IS NOT NULL'
    if color_col:
        cols.append(f'"{color_col}" AS color')
    if size_col:
        cols.append(f'"{size_col}" AS size')
    return _query(conn,
        f"SELECT {', '.join(cols)} FROM data WHERE {where} LIMIT 2000")
 
 
def q_scatter_matrix(conn, numeric_cols: list) -> pl.DataFrame:
    if len(numeric_cols) < 2:
        return pl.DataFrame()
    col_list = ", ".join([f'"{c}"' for c in numeric_cols[:6]])
    return _query(conn, f"SELECT {col_list} FROM data LIMIT 1000")
 
 
# ── TIME TRENDS ───────────────────────────────────────────────────────────────
 
def q_time_series(conn, date_col: str, num_col: str,
                  agg: str = "SUM", period: str = "Month") -> pl.DataFrame:
    safe_agg = agg.upper()
    if safe_agg not in ("SUM", "AVG", "MIN", "MAX", "COUNT"):
        safe_agg = "SUM"
 
    period_expr = {
        "Day":     f'TO_CHAR("{date_col}"::date, \'YYYY-MM-DD\')',
        "Week":    f'TO_CHAR("{date_col}"::date, \'IYYY-IW\')',
        "Month":   f'TO_CHAR("{date_col}"::date, \'YYYY-MM\')',
        "Quarter": f'CONCAT(EXTRACT(YEAR FROM "{date_col}"::date), \'-Q\','
                   f' EXTRACT(QUARTER FROM "{date_col}"::date))',
        "Year":    f'EXTRACT(YEAR FROM "{date_col}"::date)::text',
    }.get(period, f'TO_CHAR("{date_col}"::date, \'YYYY-MM\')')
 
    sql = f"""
        SELECT {period_expr}           AS period,
               {safe_agg}("{num_col}") AS value
        FROM data
        WHERE "{date_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
        GROUP BY period
        ORDER BY period
    """
    return _query(conn, sql)
 
 
def q_mom_change(conn, date_col: str, num_col: str) -> pl.DataFrame:
    sql = f"""
        WITH monthly AS (
            SELECT TO_CHAR("{date_col}"::date, 'YYYY-MM') AS month,
                   SUM("{num_col}") AS total
            FROM data
            WHERE "{date_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
            GROUP BY month
            ORDER BY month
        )
        SELECT month,
               total,
               LAG(total) OVER (ORDER BY month) AS prev_total,
               ROUND(
                 (100.0 * (total - LAG(total) OVER (ORDER BY month))
                       / NULLIF(LAG(total) OVER (ORDER BY month), 0))::numeric,
               1) AS pct_change
        FROM monthly
    """
    return _query(conn, sql)
 
 
def q_running_total(conn, date_col: str, num_col: str) -> pl.DataFrame:
    sql = f"""
        WITH daily AS (
            SELECT TO_CHAR("{date_col}"::date, 'YYYY-MM-DD') AS day,
                   SUM("{num_col}")                          AS daily_total
            FROM data
            WHERE "{date_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
            GROUP BY day
            ORDER BY day
        )
        SELECT day,
               daily_total,
               SUM(daily_total) OVER (ORDER BY day) AS running_total
        FROM daily
    """
    return _query(conn, sql)
 
 
def q_day_of_week(conn, date_col: str, num_col: str) -> pl.DataFrame:
    sql = f"""
        SELECT EXTRACT(DOW FROM "{date_col}"::date)::int     AS dow_num,
               TO_CHAR("{date_col}"::date, 'Day')             AS day_name,
               ROUND(AVG("{num_col}")::numeric, 2)            AS avg_value
        FROM data
        WHERE "{date_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
        GROUP BY dow_num, day_name
        ORDER BY dow_num
    """
    return _query(conn, sql)
 
 
def q_seasonality(conn, date_col: str, num_col: str) -> pl.DataFrame:
    sql = f"""
        SELECT EXTRACT(MONTH FROM "{date_col}"::date)::int AS month_num,
               TO_CHAR("{date_col}"::date, 'Mon')           AS month_name,
               ROUND(AVG("{num_col}")::numeric, 2)          AS avg_value
        FROM data
        WHERE "{date_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
        GROUP BY month_num, month_name
        ORDER BY month_num
    """
    return _query(conn, sql)