


# import sqlite3
# import polars as pl
 
 
# # ── Helper ──────────────────────────────────────────────────────────────────
# #number of rows and columns identified
# def _query(conn: sqlite3.Connection, sql: str) -> pl.DataFrame:
#     """Execute SQL on a sqlite3 connection → Polars DataFrame."""
#     cur = conn.execute(sql)
#     cols = [d[0] for d in cur.description]
#     rows = cur.fetchall()
#     if not rows:
#         return pl.DataFrame(schema={c: pl.Utf8 for c in cols})
#     # Build as list-of-dicts so Polars infers types correctly
#     return pl.DataFrame([dict(zip(cols, r)) for r in rows])
 
 
# # ── SUMMARY ─────────────────────────────────────────────────────────────────
# #number of rows counted 
# def q_row_count(conn: sqlite3.Connection) -> pl.DataFrame:
#     return _query(conn, "SELECT COUNT(*) AS total_rows FROM data")
 
#  #null counting (checks how many missing values)
# def q_column_summary(conn: sqlite3.Connection, col_types: dict) -> pl.DataFrame:
#     """Per-column: count, nulls, distinct values, type."""
#     dfs = []
#     for col, ctype in col_types.items():
#         sql = f"""
#             SELECT
#                 '{col}'                                              AS column_name,
#                 COUNT("{col}")                                       AS count,
#                 SUM(CASE WHEN "{col}" IS NULL THEN 1 ELSE 0 END)    AS nulls,
#                 COUNT(DISTINCT "{col}")                              AS distinct_values,
#                 '{ctype}'                                            AS col_type
#             FROM data
#         """
#         dfs.append(_query(conn, sql))
#     return pl.concat(dfs) if dfs else pl.DataFrame()
 
# #finds min max avg
# def q_numeric_stats(conn: sqlite3.Connection, numeric_cols: list) -> pl.DataFrame:
#     """MIN / MAX / AVG for every numeric column."""
#     if not numeric_cols:
#         return pl.DataFrame()
#     parts = [
#         f"""
#         SELECT '{col}'              AS column_name,
#                MIN("{col}")         AS min_val,
#                MAX("{col}")         AS max_val,
#                ROUND(AVG("{col}"),2) AS avg_val,
#                COUNT("{col}")       AS count
#         FROM data
#         """
#         for col in numeric_cols
#     ]
#     return _query(conn, " UNION ALL ".join(parts))
 
 
# # ── CATEGORIES ───────────────────────────────────────────────────────────────
# #gives count of the category choosen
# def q_category_counts(conn: sqlite3.Connection,
#                       cat_col: str, top_n: int = 10) -> pl.DataFrame:
#     sql = f"""
#         SELECT "{cat_col}"   AS category,
#                COUNT(*)      AS count,
#                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
#         FROM data
#         WHERE "{cat_col}" IS NOT NULL
#         GROUP BY "{cat_col}"
#         ORDER BY count DESC
#         LIMIT {top_n}
#     """
#     return _query(conn, sql)
 
 
# def q_category_aggregate(conn: sqlite3.Connection,
#                          cat_col: str, num_col: str,
#                          agg: str = 'SUM', top_n: int = 10) -> pl.DataFrame:
#     safe_agg = agg.upper()
#     if safe_agg not in ('SUM', 'AVG', 'MIN', 'MAX', 'COUNT'):
#         safe_agg = 'SUM'
#     sql = f"""
#         SELECT "{cat_col}"                      AS category,
#                ROUND({safe_agg}("{num_col}"),2) AS value
#         FROM data
#         WHERE "{cat_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
#         GROUP BY "{cat_col}"
#         ORDER BY value DESC
#         LIMIT {top_n}
#     """
#     return _query(conn, sql)
 
 
# def q_pareto(conn: sqlite3.Connection,
#              cat_col: str, num_col: str, top_n: int = 20) -> pl.DataFrame:
#     sql = f"""
#         WITH base AS (
#             SELECT "{cat_col}" AS category,
#                    SUM("{num_col}") AS total
#             FROM data
#             WHERE "{cat_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
#             GROUP BY "{cat_col}"
#             ORDER BY total DESC
#             LIMIT {top_n}
#         ),
#         totals AS (
#             SELECT *, SUM(total) OVER () AS grand_total FROM base
#         )
#         SELECT category,
#                total,
#                ROUND(100.0 * SUM(total) OVER (ORDER BY total DESC) / grand_total, 1)
#                    AS cum_pct
#         FROM totals
#     """
#     return _query(conn, sql)
 
 
# def q_cross_tab(conn: sqlite3.Connection,
#                 cat_col1: str, cat_col2: str) -> pl.DataFrame:
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
 
 
# # ── DISTRIBUTIONS ────────────────────────────────────────────────────────────
 
# def q_histogram_data(conn: sqlite3.Connection, num_col: str) -> pl.DataFrame:
#     return _query(conn,
#         f'SELECT "{num_col}" AS value FROM data WHERE "{num_col}" IS NOT NULL')
 
# #calculate IQR and upper limit and lower limit and the values above upper or below lower are outliers
# def q_outliers_iqr(conn: sqlite3.Connection, num_col: str) -> pl.DataFrame:
#     sql = f"""
#         WITH quartiles AS (
#             SELECT "{num_col}" AS val,
#                    NTILE(4) OVER (ORDER BY "{num_col}") AS quartile
#             FROM data WHERE "{num_col}" IS NOT NULL
#         ),
#         bounds AS (
#             SELECT MAX(CASE WHEN quartile = 1 THEN val END) AS Q1,
#                    MAX(CASE WHEN quartile = 3 THEN val END) AS Q3
#             FROM quartiles
#         )
#         SELECT d.*,
#                b.Q1, b.Q3,
#                (b.Q3 - b.Q1)              AS iqr,
#                b.Q1 - 1.5*(b.Q3 - b.Q1)  AS lower_fence,
#                b.Q3 + 1.5*(b.Q3 - b.Q1)  AS upper_fence
#         FROM data d, bounds b
#         WHERE d."{num_col}" < b.Q1 - 1.5*(b.Q3 - b.Q1)
#            OR d."{num_col}" > b.Q3 + 1.5*(b.Q3 - b.Q1)
#         ORDER BY d."{num_col}" DESC
#         LIMIT 100
#     """
#     return _query(conn, sql)
 
 
# # ── CORRELATIONS / RELATIONSHIPS ─────────────────────────────────────────────
# #creates x vs y bubble chart (if upwars and left to right means both attributes grow togerther)
# def q_scatter_data(conn: sqlite3.Connection,
#                    x_col: str, y_col: str,
#                    color_col: str = None,
#                    size_col: str = None) -> pl.DataFrame:
#     cols  = [f'"{x_col}" AS x', f'"{y_col}" AS y']
#     where = f'"{x_col}" IS NOT NULL AND "{y_col}" IS NOT NULL'
#     if color_col:
#         cols.append(f'"{color_col}" AS color')
#     if size_col:
#         cols.append(f'"{size_col}" AS size')
#     sql = f"SELECT {', '.join(cols)} FROM data WHERE {where} LIMIT 2000"
#     return _query(conn, sql)
 
 
# def q_scatter_matrix(conn: sqlite3.Connection,
#                      numeric_cols: list) -> pl.DataFrame:
#     if len(numeric_cols) < 2:
#         return pl.DataFrame()
#     col_list = ', '.join([f'"{c}"' for c in numeric_cols[:6]])
#     return _query(conn, f"SELECT {col_list} FROM data LIMIT 1000")
 
 
# # ── TIME TRENDS ──────────────────────────────────────────────────────────────
# #chopsdata up by dates and aggregates a number over chosen interval
# def q_time_series(conn: sqlite3.Connection,
#                   date_col: str, num_col: str,
#                   agg: str = 'SUM', period: str = 'Month') -> pl.DataFrame:
#     safe_agg = agg.upper()
#     if safe_agg not in ('SUM', 'AVG', 'MIN', 'MAX', 'COUNT'):
#         safe_agg = 'SUM'
#     period_expr = {
#         'Day':     f'substr("{date_col}", 1, 10)',
#         'Week':    f'strftime("%Y-W%W", "{date_col}")',
#         'Month':   f'strftime("%Y-%m", "{date_col}")',
#         'Quarter': (f'strftime("%Y", "{date_col}") || "-Q" || '
#                     f'((CAST(strftime("%m", "{date_col}") AS INTEGER) - 1) / 3 + 1)'),
#         'Year':    f'strftime("%Y", "{date_col}")',
#     }.get(period, f'strftime("%Y-%m", "{date_col}")')
 
#     sql = f"""
#         SELECT {period_expr}          AS period,
#                {safe_agg}("{num_col}") AS value
#         FROM data
#         WHERE "{date_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
#         GROUP BY period
#         ORDER BY period
#     """
#     return _query(conn, sql)
 
# #looks at monthly totals and previous month's total, and calculates the math percentage difference
# def q_mom_change(conn: sqlite3.Connection,
#                  date_col: str, num_col: str) -> pl.DataFrame:
#     sql = f"""
#         WITH monthly AS (
#             SELECT strftime('%Y-%m', "{date_col}") AS month,
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
#                  100.0 * (total - LAG(total) OVER (ORDER BY month))
#                         / NULLIF(LAG(total) OVER (ORDER BY month), 0),
#                1) AS pct_change
#         FROM monthly
#     """
#     return _query(conn, sql)
 
 
# def q_running_total(conn: sqlite3.Connection,
#                     date_col: str, num_col: str) -> pl.DataFrame:
#     # Fixed: removed stray backtick that was inside the SQL string
#     sql = f"""
#         WITH daily AS (
#             SELECT substr("{date_col}", 1, 10)  AS day,
#                    SUM("{num_col}")              AS daily_total
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
 
 
# def q_day_of_week(conn: sqlite3.Connection,
#                   date_col: str, num_col: str) -> pl.DataFrame:
#     sql = f"""
#         SELECT CAST(strftime('%w', "{date_col}") AS INTEGER) AS dow_num,
#                CASE strftime('%w', "{date_col}")
#                  WHEN '0' THEN 'Sunday'   WHEN '1' THEN 'Monday'
#                  WHEN '2' THEN 'Tuesday'  WHEN '3' THEN 'Wednesday'
#                  WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday'
#                  WHEN '6' THEN 'Saturday'
#                END AS day_name,
#                ROUND(AVG("{num_col}"), 2) AS avg_value
#         FROM data
#         WHERE "{date_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
#         GROUP BY dow_num, day_name
#         ORDER BY dow_num
#     """
#     return _query(conn, sql)
 
 
# def q_seasonality(conn: sqlite3.Connection,
#                   date_col: str, num_col: str) -> pl.DataFrame:
#     sql = f"""
#         SELECT CAST(strftime('%m', "{date_col}") AS INTEGER) AS month_num,
#                CASE strftime('%m', "{date_col}")
#                  WHEN '01' THEN 'Jan' WHEN '02' THEN 'Feb' WHEN '03' THEN 'Mar'
#                  WHEN '04' THEN 'Apr' WHEN '05' THEN 'May' WHEN '06' THEN 'Jun'
#                  WHEN '07' THEN 'Jul' WHEN '08' THEN 'Aug' WHEN '09' THEN 'Sep'
#                  WHEN '10' THEN 'Oct' WHEN '11' THEN 'Nov' WHEN '12' THEN 'Dec'
#                END AS month_name,
#                ROUND(AVG("{num_col}"), 2) AS avg_value
#         FROM data
#         WHERE "{date_col}" IS NOT NULL AND "{num_col}" IS NOT NULL
#         GROUP BY month_num, month_name
#         ORDER BY month_num
#     """
#     return _query(conn, sql)
# queries.py
import psycopg2
import polars as pl


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

def q_histogram_data(conn, num_col: str) -> pl.DataFrame:
    return _query(
        conn,
        f'SELECT "{num_col}" AS value FROM data WHERE "{num_col}" IS NOT NULL'
    )


def q_outliers_iqr(conn, num_col: str) -> pl.DataFrame:
    sql = f"""
        WITH quartiles AS (
            SELECT "{num_col}" AS val,
                   NTILE(4) OVER (ORDER BY "{num_col}") AS quartile
            FROM data WHERE "{num_col}" IS NOT NULL
        ),
        bounds AS (
            SELECT MAX(CASE WHEN quartile = 1 THEN val END) AS q1,
                   MAX(CASE WHEN quartile = 3 THEN val END) AS q3
            FROM quartiles
        )
        SELECT d.*,
               b.q1, b.q3,
               (b.q3 - b.q1)             AS iqr,
               b.q1 - 1.5*(b.q3 - b.q1) AS lower_fence,
               b.q3 + 1.5*(b.q3 - b.q1) AS upper_fence
        FROM data d, bounds b
        WHERE d."{num_col}" < b.q1 - 1.5*(b.q3 - b.q1)
           OR d."{num_col}" > b.q3 + 1.5*(b.q3 - b.q1)
        ORDER BY d."{num_col}" DESC
        LIMIT 100
    """
    return _query(conn, sql)


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