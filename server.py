

# from flask import Flask, jsonify, render_template, request
# from flask_cors import CORS
 
# import db
# import queries as q
# import charts as c
 
# app = Flask(__name__)
# CORS(app)
 
 
# # ── Helpers ──────────────────────────────────────────────────────────────────
 
# def _col_types():
#     return db.get_col_types() or {}
 
 
# def _grouped():
#     ct = _col_types()
#     grouped = {'numeric': [], 'category': [], 'date': [], 'id': [], 'text': []}
#     for col, t in ct.items():
#         grouped[t].append(col)
#     return grouped
 
 
# def _first(lst):
#     return lst[0] if lst else None
 
 
# # ── Routes ───────────────────────────────────────────────────────────────────
 
# @app.route('/')
# def index():
#     return render_template('index.html')
 
 
# @app.route('/ready')
# def ready():
#     """
#     Returns dataset metadata if data has been loaded, else an error.
#     The frontend calls this on page load to skip the upload step.
#     """
#     conn = db.get_connection()
#     ct   = _col_types()
#     if conn is None or not ct:
#         return jsonify({'ready': False, 'error': 'No data loaded yet'}), 503
 
#     df       = db.get_df()
#     grouped  = _grouped()
#     n_rows   = len(df) if df is not None else 0
#     n_cols   = len(df.columns) if df is not None else 0
 
#     return jsonify({
#         'ready':     True,
#         'rows':      n_rows,
#         'columns':   list(df.columns) if df is not None else [],
#         'col_types': ct,
#         'grouped':   grouped,
#     })
 
 
# @app.route('/chart/<section>', methods=['POST'])
# def chart(section):
#     conn = db.get_connection()
#     if conn is None:
#         return jsonify({'error': 'No data loaded'}), 400
 
#     data    = request.json or {}
#     grouped = _grouped()
#     ct      = _col_types()
 
#     # ── Parameters sent from the frontend ──────────────────────────────────
#     top_n    = int(data.get('top_n', 10))
#     agg      = data.get('agg', 'SUM').upper()
#     period   = data.get('period', 'Month')
#     x_col    = data.get('x_col')    or _first(grouped['numeric'])
#     y_col    = data.get('y_col')    or _first([c2 for c2 in grouped['numeric'] if c2 != x_col])
#     cat_col  = data.get('cat_col')  or _first(grouped['category'])
#     num_col  = data.get('num_col')  or _first(grouped['numeric'])
#     date_col = data.get('date_col') or _first(grouped['date'])
#     color_col = data.get('color_col') or None
#     size_col  = data.get('size_col')  or None
 
#     try:
#         # ── §1 Summary ────────────────────────────────────────────────────
#         if section == 'summary_types':
#             return jsonify(c.chart_column_types_pie(ct))
 
#         if section == 'summary_nulls':
#             df_s = q.q_column_summary(conn, ct)
#             return jsonify(c.chart_null_bar(df_s.to_pandas()))
 
#         if section == 'summary_stats':
#             df_s = q.q_numeric_stats(conn, grouped['numeric'])
#             if df_s.is_empty():
#                 return jsonify({'error': 'No numeric columns'})
#             return jsonify(df_s.fill_null("").to_dicts())
 
#         # ── §2 Categories ─────────────────────────────────────────────────
#         if section == 'cat_bar':
#             df_c = q.q_category_counts(conn, cat_col, top_n).to_pandas()
#             return jsonify(c.chart_bar_counts(df_c, cat_col, top_n))
 
#         if section == 'cat_pie':
#             df_c = q.q_category_counts(conn, cat_col, top_n).to_pandas()
#             return jsonify(c.chart_pie(df_c, cat_col))
 
#         if section == 'cat_hbar':
#             if not num_col:
#                 return jsonify({'error': 'No numeric column'})
#             df_c = q.q_category_aggregate(conn, cat_col, num_col, agg, top_n).to_pandas()
#             return jsonify(c.chart_horizontal_bar(df_c, cat_col, num_col, agg))
 
#         if section == 'cat_grouped':
#             if not num_col:
#                 return jsonify({'error': 'No numeric column'})
#             df_c = q.q_category_aggregate(conn, cat_col, num_col, agg, top_n).to_pandas()
#             return jsonify(c.chart_grouped_bar(df_c, cat_col, num_col))
 
#         if section == 'cat_avg':
#             if not num_col or not cat_col:
#                 return jsonify({'error': 'Need category and numeric column'})
#             df_avg = q.q_category_aggregate(conn, cat_col, num_col, 'AVG', top_n).to_pandas()
#             return jsonify(c.chart_avg_by_category(df_avg, cat_col, num_col))
 
#         # ── §3 Distributions ──────────────────────────────────────────────
#         if section == 'dist_hist':
#             df_h = q.q_histogram_data(conn, num_col).to_pandas()
#             return jsonify(c.chart_histogram(df_h, num_col))
 
#         if section == 'dist_box':
#             df_h = q.q_histogram_data(conn, num_col).to_pandas()
#             return jsonify(c.chart_box_single(df_h, num_col))
 
#         if section == 'dist_outliers':
#             df_out = q.q_outliers_iqr(conn, num_col)
#             return jsonify(df_out.head(50).to_dicts())
 
#         # ── §4 Relationships ──────────────────────────────────────────────
#         if section == 'corr_scatter':
#             df_sc = q.q_scatter_data(conn, x_col, y_col, color_col, None).to_pandas()
#             return jsonify(c.chart_scatter(df_sc, x_col, y_col, color_col))
 
#         if section == 'corr_bubble':
#             df_sc = q.q_scatter_data(conn, x_col, y_col, None, size_col).to_pandas()
#             return jsonify(c.chart_bubble(df_sc, x_col, y_col, size_col or ''))
 
#         # ── §5 Time Trends ────────────────────────────────────────────────
#         if section == 'time_line':
#             if not date_col or not num_col:
#                 return jsonify({'error': 'Need a date column and numeric column'})
#             df_t = q.q_time_series(conn, date_col, num_col, agg, period).to_pandas()
#             return jsonify(c.chart_line(df_t, date_col, num_col, period, agg))
 
#         if section == 'time_mom':
#             if not date_col or not num_col:
#                 return jsonify({'error': 'Need a date column and numeric column'})
#             df_t = q.q_mom_change(conn, date_col, num_col).to_pandas()
#             return jsonify(c.chart_mom_change(df_t, num_col))
 
#         if section == 'time_dow':
#             if not date_col or not num_col:
#                 return jsonify({'error': 'Need a date column and numeric column'})
#             df_t = q.q_day_of_week(conn, date_col, num_col).to_pandas()
#             return jsonify(c.chart_day_of_week(df_t, num_col))
 
#         if section == 'time_season':
#             if not date_col or not num_col:
#                 return jsonify({'error': 'Need a date column and numeric column'})
#             df_t = q.q_seasonality(conn, date_col, num_col).to_pandas()
#             return jsonify(c.chart_seasonality(df_t, num_col))
 
#         return jsonify({'error': f'Unknown section: {section}'}), 404
 
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         return jsonify({'error': str(e)}), 500
 
 
# if __name__ == '__main__':
#     app.run(debug=True, port=5000)

# server.py
# server.py
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

import db
import queries as q
import charts as c
import neo4j_writer as nw

app = Flask(__name__)
CORS(app)


def _col_types():
    return db.get_col_types() or {}


def _grouped():
    ct = _col_types()
    grouped = {"numeric": [], "category": [], "date": [], "id": [], "text": []}
    for col, t in ct.items():
        grouped[t].append(col)
    return grouped


def _first(lst):
    return lst[0] if lst else None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ready")
def ready():
    conn = db.get_connection()
    ct   = _col_types()
    if conn is None or not ct:
        return jsonify({"ready": False, "error": "No data loaded yet"}), 503

    df = db.get_df()
    if df is None:
        return jsonify({"ready": False, "error": "No data loaded yet"}), 503

    # Get REAL row count from PostgreSQL — not from the 5000-row sample
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM data")
        total_rows = cur.fetchone()[0]
        cur.close()
    except Exception:
        total_rows = len(df)

    return jsonify({
        "ready":     True,
        "rows":      total_rows,        # real count from PostgreSQL
        "columns":   list(df.columns),  # column names from sample
        "col_types": ct,
        "grouped":   _grouped(),
    })


@app.route("/chart/<section>", methods=["POST"])
def chart(section):
    conn = db.get_connection()
    if conn is None:
        return jsonify({"error": "No data loaded"}), 400

    data      = request.json or {}
    grouped   = _grouped()
    ct        = _col_types()
    top_n     = int(data.get("top_n", 10))
    agg       = data.get("agg", "SUM").upper()
    period    = data.get("period", "Month")
    x_col     = data.get("x_col")    or _first(grouped["numeric"])
    y_col     = data.get("y_col")    or _first([c2 for c2 in grouped["numeric"] if c2 != x_col])
    cat_col   = data.get("cat_col")  or _first(grouped["category"])
    num_col   = data.get("num_col")  or _first(grouped["numeric"])
    date_col  = data.get("date_col") or _first(grouped["date"])
    color_col = data.get("color_col") or None
    size_col  = data.get("size_col")  or None

    try:
        if section == "summary_types":
            return jsonify(c.chart_column_types_pie(ct))
        if section == "summary_nulls":
            return jsonify(c.chart_null_bar(
                q.q_column_summary(conn, ct).to_pandas()))
        if section == "summary_stats":
            df_s = q.q_numeric_stats(conn, grouped["numeric"])
            if df_s.is_empty():
                return jsonify({"error": "No numeric columns"})
            return jsonify(df_s.fill_null("").to_dicts())
        if section == "cat_bar":
            return jsonify(c.chart_bar_counts(
                q.q_category_counts(conn, cat_col, top_n).to_pandas(),
                cat_col, top_n))
        if section == "cat_pie":
            return jsonify(c.chart_pie(
                q.q_category_counts(conn, cat_col, top_n).to_pandas(),
                cat_col))
        if section == "cat_hbar":
            if not num_col:
                return jsonify({"error": "No numeric column"})
            return jsonify(c.chart_horizontal_bar(
                q.q_category_aggregate(
                    conn, cat_col, num_col, agg, top_n).to_pandas(),
                cat_col, num_col, agg))
        if section == "cat_grouped":
            if not num_col:
                return jsonify({"error": "No numeric column"})
            return jsonify(c.chart_grouped_bar(
                q.q_category_aggregate(
                    conn, cat_col, num_col, agg, top_n).to_pandas(),
                cat_col, num_col))
        if section == "cat_avg":
            if not num_col or not cat_col:
                return jsonify({"error": "Need category and numeric column"})
            return jsonify(c.chart_avg_by_category(
                q.q_category_aggregate(
                    conn, cat_col, num_col, "AVG", top_n).to_pandas(),
                cat_col, num_col))
        if section == "dist_hist":
            return jsonify(c.chart_histogram(
                q.q_histogram_data(conn, num_col).to_pandas(), num_col))
        if section == "dist_box":
            return jsonify(c.chart_box_single(
                q.q_histogram_data(conn, num_col).to_pandas(), num_col))
        if section == "dist_outliers":
            return jsonify(
                q.q_outliers_iqr(conn, num_col).head(50).to_dicts())
        if section == "corr_scatter":
            return jsonify(c.chart_scatter(
                q.q_scatter_data(
                    conn, x_col, y_col, color_col, None).to_pandas(),
                x_col, y_col, color_col))
        if section == "corr_bubble":
            return jsonify(c.chart_bubble(
                q.q_scatter_data(
                    conn, x_col, y_col, None, size_col).to_pandas(),
                x_col, y_col, size_col or ""))
        if section == "time_line":
            if not date_col or not num_col:
                return jsonify({"error": "Need a date and numeric column"})
            return jsonify(c.chart_line(
                q.q_time_series(
                    conn, date_col, num_col, agg, period).to_pandas(),
                date_col, num_col, period, agg))
        if section == "time_mom":
            if not date_col or not num_col:
                return jsonify({"error": "Need a date and numeric column"})
            return jsonify(c.chart_mom_change(
                q.q_mom_change(conn, date_col, num_col).to_pandas(), num_col))
        if section == "time_dow":
            if not date_col or not num_col:
                return jsonify({"error": "Need a date and numeric column"})
            return jsonify(c.chart_day_of_week(
                q.q_day_of_week(conn, date_col, num_col).to_pandas(), num_col))
        if section == "time_season":
            if not date_col or not num_col:
                return jsonify({"error": "Need a date and numeric column"})
            return jsonify(c.chart_seasonality(
                q.q_seasonality(conn, date_col, num_col).to_pandas(), num_col))
        return jsonify({"error": f"Unknown section: {section}"}), 404

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/graph/summary")
def graph_summary():
    try:
        return jsonify(nw.get_graph_summary())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/graph/files")
def graph_files():
    try:
        return jsonify(nw.get_source_files())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/graph/explore", methods=["POST"])
def graph_explore():
    data     = request.json or {}
    col_name = data.get("col_name", "")
    value    = data.get("value", "")
    limit    = int(data.get("limit", 60))
    if not col_name or not value:
        return jsonify({"error": "col_name and value required"}), 400
    try:
        return jsonify(nw.query_graph_for_category(col_name, value, limit))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(
        debug=True,
        port=5000,
        use_reloader=False  # prevents mid-write restarts
    )