

# """
# charts.py  —  All Plotly chart builders.

# Fixes in this version:
#   - legend bgcolor uses rgba(0,0,0,0) NOT 'transparent' (Plotly rejects the string)
#   - chart_avg_by_category: query returns 'value' col, chart uses y='value' (not 'avg_val')
#   - chart_pie: no label+percent on slices; names in legend only → no overlap
#   - chart_bar_counts / chart_horizontal_bar: use correct fixed col names
#   - Smart tick limiting for big datasets
# """
# import json
# import math

# import pandas as pd
# import plotly.express as px
# import plotly.graph_objects as go

# TEMPLATE  = "plotly_dark"
# COLORS    = px.colors.qualitative.Vivid
# _TRANSP   = "rgba(0,0,0,0)"   # Plotly rejects the CSS word 'transparent'
# _MAX_CHARS = 18                # label truncation threshold


# def _fig_to_json(fig):
#     return json.loads(fig.to_json())


# def _trim(series: pd.Series, n: int = _MAX_CHARS) -> pd.Series:
#     return series.astype(str).apply(lambda x: x[:n] + "…" if len(x) > n else x)


# def _cat_axis(fig, n: int, axis: str = 'xaxis'):
#     angle = -45 if n > 8 else -30 if n > 5 else 0
#     size  = 9   if n > 12 else 10 if n > 8 else 11
#     fig.update_layout(**{axis: dict(tickangle=angle, tickfont=dict(size=size))})
#     return fig


# # ── SUMMARY ──────────────────────────────────────────────────────────────────

# def chart_column_types_pie(col_types: dict):
#     from collections import Counter
#     counts = Counter(col_types.values())
#     fig = px.pie(
#         names=list(counts.keys()),
#         values=list(counts.values()),
#         title="Column types in your dataset",
#         template=TEMPLATE,
#         color_discrete_sequence=COLORS,
#         hole=0.45,
#     )
#     fig.update_traces(
#         textinfo='percent',
#         textposition='inside',
#         insidetextorientation='horizontal',
#     )
#     fig.update_layout(
#         legend=dict(bgcolor=_TRANSP, font=dict(size=11)),
#         margin=dict(t=40, b=20, l=20, r=20),
#     )
#     return _fig_to_json(fig)


# def chart_null_bar(df_summary: pd.DataFrame):
#     df = df_summary[df_summary['nulls'] > 0].copy()
#     if df.empty:
#         df = df_summary.copy()
#     df['column_name'] = _trim(df['column_name'])
#     fig = px.bar(
#         df, x='column_name', y='nulls',
#         title="Missing values per column",
#         template=TEMPLATE,
#         color='nulls',
#         color_continuous_scale='Reds',
#         text='nulls',
#     )
#     fig.update_traces(textposition='outside')
#     fig.update_layout(coloraxis_showscale=False)
#     _cat_axis(fig, len(df))
#     return _fig_to_json(fig)


# # ── CATEGORIES ───────────────────────────────────────────────────────────────

# def chart_bar_counts(df: pd.DataFrame, cat_col: str, top_n: int):
#     """df cols: 'category', 'count', 'pct'"""
#     df = df.copy()
#     df['category'] = _trim(df['category'])
#     fig = px.bar(
#         df, x='category', y='count',
#         title=f"Records per {cat_col} (top {top_n})",
#         template=TEMPLATE,
#         text='count',
#         color_discrete_sequence=COLORS,
#     )
#     fig.update_traces(textposition='outside', marker_color=COLORS[0])
#     fig.update_layout(showlegend=False)
#     _cat_axis(fig, len(df))
#     return _fig_to_json(fig)


# def chart_pie(df: pd.DataFrame, cat_col: str):
#     """df cols: 'category', 'count' — legend-only labels, no on-slice text overlap"""
#     df   = df.copy()
#     n    = len(df)
#     df['label'] = _trim(df['category'], 22)

#     fig = px.pie(
#         df, names='label', values='count',
#         title=f"Share by {cat_col}",
#         template=TEMPLATE,
#         color_discrete_sequence=COLORS,
#         hole=0.45,
#     )
#     fig.update_traces(
#         textinfo='percent',
#         textposition='inside',
#         insidetextorientation='horizontal',
#         pull=[0.04] + [0.0] * (n - 1),
#         hovertemplate='<b>%{label}</b><br>Count: %{value:,}<br>%{percent}<extra></extra>',
#     )
#     if n > 10:
#         leg = dict(orientation='h', x=0.5, y=-0.22, xanchor='center',
#                    font=dict(size=9), bgcolor=_TRANSP)
#         fig.update_layout(legend=leg, margin=dict(t=40,b=100,l=20,r=20), height=420)
#     else:
#         leg = dict(orientation='v', x=1.02, y=0.5, xanchor='left',
#                    font=dict(size=10), bgcolor=_TRANSP)
#         fig.update_layout(legend=leg, margin=dict(t=40,b=20,l=20,r=20), height=360)
#     return _fig_to_json(fig)


# def chart_horizontal_bar(df: pd.DataFrame, cat_col: str, num_col: str, agg: str):
#     """df cols: 'category', 'value'"""
#     df = df.copy()
#     df['category'] = _trim(df['category'])
#     fig = px.bar(
#         df, y='category', x='value', orientation='h',
#         title=f"{agg} of {num_col} by {cat_col}",
#         template=TEMPLATE,
#         text='value',
#         color_discrete_sequence=COLORS,
#     )
#     fig.update_traces(
#         texttemplate='%{text:,.0f}',
#         textposition='outside',
#         marker_color=COLORS[2],
#     )
#     fig.update_layout(yaxis={'categoryorder': 'total ascending'})
#     n = len(df)
#     fig.update_layout(height=max(320, n * max(22, min(40, 400 // max(n,1))) + 80))
#     return _fig_to_json(fig)


# def chart_grouped_bar(df: pd.DataFrame, cat_col: str, num_col: str):
#     """df cols: 'category', 'value' — top N vs bottom N"""
#     if len(df) < 2:
#         return chart_horizontal_bar(df, cat_col, num_col, 'SUM')
#     half    = min(5, len(df) // 2)
#     top     = df.head(half).copy();  top['rank']    = f'Top {half}'
#     bottom  = df.tail(half).copy();  bottom['rank'] = f'Bottom {half}'
#     combined = pd.concat([top, bottom])
#     combined['category'] = _trim(combined['category'])
#     cmap = {f'Top {half}': '#2dd4a0', f'Bottom {half}': '#f56060'}
#     fig = px.bar(
#         combined, x='category', y='value',
#         color='rank', barmode='group',
#         title=f"Top {half} vs Bottom {half} — {cat_col} by {num_col}",
#         template=TEMPLATE,
#         color_discrete_map=cmap,
#         text='value',
#     )
#     fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
#     _cat_axis(fig, len(combined))
#     return _fig_to_json(fig)


# def chart_avg_by_category(df: pd.DataFrame, cat_col: str, num_col: str):
#     """df cols: 'category', 'value'  (AVG query returns 'value' not 'avg_val')"""
#     df = df.copy()
#     df['category'] = _trim(df['category'])
#     fig = px.bar(
#         df, x='category', y='value',
#         title=f"Average {num_col} per {cat_col}",
#         template=TEMPLATE,
#         text='value',
#         color_discrete_sequence=COLORS,
#     )
#     fig.update_traces(
#         texttemplate='%{text:,.1f}',
#         textposition='outside',
#         marker_color=COLORS[4],
#     )
#     fig.update_layout(coloraxis_showscale=False)
#     _cat_axis(fig, len(df))
#     return _fig_to_json(fig)


# # ── DISTRIBUTIONS ─────────────────────────────────────────────────────────────

# def chart_histogram(df: pd.DataFrame, num_col: str):
#     """df col: 'value'"""
#     n     = len(df)
#     nbins = min(50, max(10, int(math.sqrt(n))))
#     fig   = px.histogram(
#         df, x='value', nbins=nbins,
#         title=f"Distribution of {num_col}",
#         template=TEMPLATE,
#         color_discrete_sequence=['#5b7cff'],
#         marginal='rug',
#     )
#     fig.update_layout(bargap=0.05)
#     return _fig_to_json(fig)


# def chart_box_single(df: pd.DataFrame, num_col: str):
#     """df col: 'value'"""
#     fig = px.box(
#         df, y='value',
#         title=f"Spread of {num_col}",
#         template=TEMPLATE,
#         color_discrete_sequence=['#9d7dfa'],
#         points='outliers',
#     )
#     fig.update_layout(annotations=[dict(
#         text="Box = middle 50% | Line = median | Dots = outliers",
#         xref="paper", yref="paper", x=0.5, y=-0.15,
#         showarrow=False, font=dict(size=10, color='#8890a8'),
#     )])
#     return _fig_to_json(fig)


# # ── RELATIONSHIPS ─────────────────────────────────────────────────────────────

# def chart_scatter(df: pd.DataFrame, x_col: str, y_col: str, color_col: str = None):
#     """df cols: 'x', 'y' [, 'color']"""
#     kwargs = dict(
#         x='x', y='y',
#         title=f"{x_col} vs {y_col}",
#         template=TEMPLATE,
#         opacity=0.55,
#         color_discrete_sequence=COLORS,
#         trendline='ols',
#         labels={'x': x_col, 'y': y_col},
#     )
#     if color_col and 'color' in df.columns:
#         kwargs['color'] = 'color'
#     try:
#         fig = px.scatter(df, **kwargs)
#     except Exception:
#         kwargs.pop('trendline', None)
#         fig = px.scatter(df, **kwargs)
#     fig.update_traces(marker=dict(size=5))
#     return _fig_to_json(fig)


# def chart_bubble(df: pd.DataFrame, x_col: str, y_col: str, size_col: str):
#     """df cols: 'x', 'y' [, 'size']"""
#     if 'size' not in df.columns:
#         return chart_scatter(df, x_col, y_col)
#     fig = px.scatter(
#         df, x='x', y='y', size='size',
#         title=f"{x_col} vs {y_col} (size = {size_col})",
#         template=TEMPLATE,
#         color_discrete_sequence=COLORS,
#         size_max=40, opacity=0.65,
#         labels={'x': x_col, 'y': y_col},
#     )
#     return _fig_to_json(fig)


# # ── TIME TRENDS ───────────────────────────────────────────────────────────────

# def chart_line(df: pd.DataFrame, date_col: str, num_col: str, period: str, agg: str):
#     """df cols: 'period', 'value'"""
#     n   = len(df)
#     fig = px.area(
#         df, x='period', y='value',
#         title=f"{agg} of {num_col} over time ({period})",
#         template=TEMPLATE,
#         markers=(n <= 60),
#         color_discrete_sequence=['#5b7cff'],
#         line_shape='spline',
#         labels={'period': date_col, 'value': num_col},
#     )
#     fig.update_traces(fill='tozeroy', fillcolor='rgba(91,124,255,0.15)')
#     fig.update_layout(xaxis=dict(tickangle=-45, nticks=min(24, n),
#                                   tickfont=dict(size=9 if n > 24 else 11)))
#     return _fig_to_json(fig)


# def chart_mom_change(df: pd.DataFrame, num_col: str):
#     """df cols: 'month', 'total', 'pct_change'"""
#     df     = df.dropna(subset=['pct_change']).copy()
#     colors = ['#2dd4a0' if v >= 0 else '#f56060' for v in df['pct_change']]
#     n      = len(df)
#     fig    = go.Figure(go.Bar(
#         x=df['month'], y=df['pct_change'],
#         marker_color=colors,
#         text=[f"{v:+.1f}%" for v in df['pct_change']],
#         textposition='outside',
#     ))
#     fig.update_layout(
#         title=f"Month-over-month % change — {num_col}",
#         template=TEMPLATE,
#         xaxis=dict(tickangle=-45, nticks=min(24,n), tickfont=dict(size=9 if n>24 else 11)),
#         annotations=[dict(
#             text="Green = growth · Red = decline",
#             xref="paper", yref="paper", x=0, y=-0.22,
#             showarrow=False, font=dict(size=10, color='#8890a8'),
#         )],
#     )
#     return _fig_to_json(fig)


# def chart_day_of_week(df: pd.DataFrame, num_col: str):
#     """df cols: 'dow_num', 'day_name', 'avg_value'"""
#     fig = px.bar(
#         df, x='day_name', y='avg_value',
#         title=f"Average {num_col} by day of week",
#         template=TEMPLATE,
#         text='avg_value',
#         color_discrete_sequence=COLORS,
#     )
#     fig.update_traces(texttemplate='%{text:,.1f}', textposition='outside',
#                       marker_color=COLORS[1])
#     return _fig_to_json(fig)


# def chart_seasonality(df: pd.DataFrame, num_col: str):
#     """df cols: 'month_num', 'month_name', 'avg_value'"""
#     fig = px.line(
#         df, x='month_name', y='avg_value',
#         title=f"Monthly seasonality — {num_col}",
#         template=TEMPLATE,
#         markers=True,
#         color_discrete_sequence=['#f97316'],
#         line_shape='spline',
#     )
#     fig.update_traces(fill='tozeroy', fillcolor='rgba(249,115,22,0.1)',
#                       marker=dict(size=8))
#     fig.update_layout(xaxis={
#         'categoryorder': 'array',
#         'categoryarray': ['Jan','Feb','Mar','Apr','May','Jun',
#                           'Jul','Aug','Sep','Oct','Nov','Dec'],
#     })
#     return _fig_to_json(fig)


# # ── TOP TRENDS (§6) ───────────────────────────────────────────────────────────

# def chart_top_bottom_table(df: pd.DataFrame, cat_col: str, num_col: str, n: int = 10):
#     """Ranked table as a Plotly table — top N and bottom N side by side."""
#     top    = df.head(n).copy()
#     bottom = df.tail(n).iloc[::-1].copy()   # reverse so worst is at bottom
#     fig = go.Figure(data=[go.Table(
#         columnwidth=[3, 2, 3, 2],
#         header=dict(
#             values=[f'🏆 Top {n} — {cat_col}', f'{num_col}',
#                     f'⚠ Bottom {n} — {cat_col}', f'{num_col}'],
#             fill_color='#1a1e27',
#             font=dict(color='#8890a8', size=11),
#             line_color='#2c3145',
#             align='left',
#         ),
#         cells=dict(
#             values=[
#                 top['category'].apply(lambda x: str(x)[:22]).tolist(),
#                 [f"{v:,.1f}" for v in top['value']],
#                 bottom['category'].apply(lambda x: str(x)[:22]).tolist(),
#                 [f"{v:,.1f}" for v in bottom['value']],
#             ],
#             fill_color=[['#12151c', '#1a1e27'] * (n // 2 + 1)] * 4,
#             font=dict(color=['#2dd4a0','#eceef5','#f56060','#eceef5'], size=11),
#             line_color='#2c3145',
#             align='left',
#         ),
#     )])
#     fig.update_layout(
#         title=f"Top vs Bottom — {cat_col} by {num_col}",
#         template=TEMPLATE,
#         margin=dict(t=40, b=10, l=10, r=10),
#         height=max(300, n * 32 + 80),
#     )
#     return _fig_to_json(fig)


# def chart_treemap(df: pd.DataFrame, cat_col: str, num_col: str):
#     """df cols: 'category', 'value' — treemap gives size intuition"""
#     df = df.copy()
#     df['category'] = _trim(df['category'], 22)
#     df['value']    = df['value'].abs()          # treemap needs positive sizes
#     fig = px.treemap(
#         df, path=['category'], values='value',
#         title=f"Treemap — {num_col} by {cat_col}",
#         template=TEMPLATE,
#         color='value',
#         color_continuous_scale='Blues',
#     )
#     fig.update_traces(textinfo='label+value+percent root')
#     fig.update_layout(coloraxis_showscale=False, margin=dict(t=40,b=10,l=10,r=10))
#     return _fig_to_json(fig)


# def chart_running_total(df: pd.DataFrame, date_col: str, num_col: str):
#     """df cols: 'day', 'daily_total', 'running_total'"""
#     fig = go.Figure()
#     fig.add_trace(go.Bar(
#         x=df['day'], y=df['daily_total'],
#         name='Daily', marker_color='rgba(91,124,255,0.5)',
#         yaxis='y',
#     ))
#     fig.add_trace(go.Scatter(
#         x=df['day'], y=df['running_total'],
#         name='Cumulative', line=dict(color='#2dd4a0', width=2),
#         yaxis='y2',
#     ))
#     n = len(df)
#     fig.update_layout(
#         title=f"Daily vs Cumulative {num_col}",
#         template=TEMPLATE,
#         yaxis=dict(title='Daily', gridcolor='#2c3145'),
#         yaxis2=dict(title='Cumulative', overlaying='y', side='right',
#                     gridcolor='#2c3145'),
#         legend=dict(bgcolor=_TRANSP),
#         xaxis=dict(tickangle=-45, nticks=min(30,n)),
#         margin=dict(t=40, b=60, l=60, r=60),
#         barmode='overlay',
#     )
#     return _fig_to_json(fig)
"""
charts.py  —  All Plotly chart builders.
"""
import json
import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

TEMPLATE  = "plotly_dark"
COLORS    = px.colors.qualitative.Vivid
_TRANSP   = "rgba(0,0,0,0)"
_MAX_CHARS = 18


def _fig_to_json(fig):
    return json.loads(fig.to_json())


def _trim(series: pd.Series, n: int = _MAX_CHARS) -> pd.Series:
    return series.astype(str).apply(lambda x: x[:n] + "…" if len(x) > n else x)


def _cat_axis(fig, n: int, axis: str = 'xaxis'):
    angle = -45 if n > 8 else -30 if n > 5 else 0
    size  = 9   if n > 12 else 10 if n > 8 else 11
    fig.update_layout(**{axis: dict(tickangle=angle, tickfont=dict(size=size))})
    return fig


# ── SUMMARY ──────────────────────────────────────────────────────────────────

def chart_column_types_pie(col_types: dict):
    from collections import Counter
    counts = Counter(col_types.values())
    fig = px.pie(
        names=list(counts.keys()),
        values=list(counts.values()),
        title="Column types in your dataset",
        template=TEMPLATE,
        color_discrete_sequence=COLORS,
        hole=0.45,
    )
    fig.update_traces(
        textinfo='percent',
        textposition='inside',
        insidetextorientation='horizontal',
    )
    fig.update_layout(
        legend=dict(bgcolor=_TRANSP, font=dict(size=11)),
        margin=dict(t=40, b=20, l=20, r=20),
    )
    return _fig_to_json(fig)


def chart_null_bar(df_summary: pd.DataFrame):
    df = df_summary[df_summary['nulls'] > 0].copy()
    if df.empty:
        df = df_summary.copy()
    df['column_name'] = _trim(df['column_name'])
    fig = px.bar(
        df, x='column_name', y='nulls',
        title="Missing values per column",
        template=TEMPLATE,
        color='nulls',
        color_continuous_scale='Reds',
        text='nulls',
    )
    fig.update_traces(textposition='outside')
    fig.update_layout(coloraxis_showscale=False)
    _cat_axis(fig, len(df))
    return _fig_to_json(fig)


# ── CATEGORIES ───────────────────────────────────────────────────────────────

def chart_bar_counts(df: pd.DataFrame, cat_col: str, top_n: int):
    """df cols: 'category', 'count', 'pct'"""
    df = df.copy()
    df['category'] = _trim(df['category'])
    fig = px.bar(
        df, x='category', y='count',
        title=f"Records per {cat_col} (top {top_n})",
        template=TEMPLATE,
        text='count',
        color_discrete_sequence=COLORS,
    )
    fig.update_traces(textposition='outside', marker_color=COLORS[0])
    fig.update_layout(showlegend=False)
    _cat_axis(fig, len(df))
    return _fig_to_json(fig)


def chart_pie(df: pd.DataFrame, cat_col: str):
    """df cols: 'category', 'count'"""
    df   = df.copy()
    n    = len(df)
    df['label'] = _trim(df['category'], 22)

    fig = px.pie(
        df, names='label', values='count',
        title=f"Share by {cat_col}",
        template=TEMPLATE,
        color_discrete_sequence=COLORS,
        hole=0.45,
    )
    fig.update_traces(
        textinfo='percent',
        textposition='inside',
        insidetextorientation='horizontal',
        pull=[0.04] + [0.0] * (n - 1),
        hovertemplate='<b>%{label}</b><br>Count: %{value:,}<br>%{percent}<extra></extra>',
    )
    if n > 10:
        leg = dict(orientation='h', x=0.5, y=-0.22, xanchor='center',
                   font=dict(size=9), bgcolor=_TRANSP)
        fig.update_layout(legend=leg, margin=dict(t=40,b=100,l=20,r=20), height=420)
    else:
        leg = dict(orientation='v', x=1.02, y=0.5, xanchor='left',
                   font=dict(size=10), bgcolor=_TRANSP)
        fig.update_layout(legend=leg, margin=dict(t=40,b=20,l=20,r=20), height=360)
    return _fig_to_json(fig)


def chart_horizontal_bar(df: pd.DataFrame, cat_col: str, num_col: str, agg: str):
    """df cols: 'category', 'value'"""
    df = df.copy()
    df['category'] = _trim(df['category'])
    fig = px.bar(
        df, y='category', x='value', orientation='h',
        title=f"{agg} of {num_col} by {cat_col}",
        template=TEMPLATE,
        text='value',
        color_discrete_sequence=COLORS,
    )
    fig.update_traces(
        texttemplate='%{text:,.0f}',
        textposition='outside',
        marker_color=COLORS[2],
    )
    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
    n = len(df)
    fig.update_layout(height=max(320, n * max(22, min(40, 400 // max(n,1))) + 80))
    return _fig_to_json(fig)


def chart_grouped_bar(df: pd.DataFrame, cat_col: str, num_col: str):
    """df cols: 'category', 'value' — top N vs bottom N"""
    if len(df) < 2:
        return chart_horizontal_bar(df, cat_col, num_col, 'SUM')
    half    = min(5, len(df) // 2)
    top     = df.head(half).copy();  top['rank']    = f'Top {half}'
    bottom  = df.tail(half).copy();  bottom['rank'] = f'Bottom {half}'
    combined = pd.concat([top, bottom])
    combined['category'] = _trim(combined['category'])
    cmap = {f'Top {half}': '#2dd4a0', f'Bottom {half}': '#f56060'}
    fig = px.bar(
        combined, x='category', y='value',
        color='rank', barmode='group',
        title=f"Top {half} vs Bottom {half} — {cat_col} by {num_col}",
        template=TEMPLATE,
        color_discrete_map=cmap,
        text='value',
    )
    fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside')
    _cat_axis(fig, len(combined))
    return _fig_to_json(fig)


def chart_avg_by_category(df: pd.DataFrame, cat_col: str, num_col: str):
    """df cols: 'category', 'value'"""
    df = df.copy()
    df['category'] = _trim(df['category'])
    fig = px.bar(
        df, x='category', y='value',
        title=f"Average {num_col} per {cat_col}",
        template=TEMPLATE,
        text='value',
        color_discrete_sequence=COLORS,
    )
    fig.update_traces(
        texttemplate='%{text:,.1f}',
        textposition='outside',
        marker_color=COLORS[4],
    )
    fig.update_layout(coloraxis_showscale=False)
    _cat_axis(fig, len(df))
    return _fig_to_json(fig)


# ── DISTRIBUTIONS ─────────────────────────────────────────────────────────────

def chart_histogram(df: pd.DataFrame, num_col: str):
    """df col: 'value'"""
    n     = len(df)
    nbins = min(50, max(10, int(math.sqrt(n))))
    fig   = px.histogram(
        df, x='value', nbins=nbins,
        title=f"Distribution of {num_col}",
        template=TEMPLATE,
        color_discrete_sequence=['#5b7cff'],
        marginal='rug',
    )
    fig.update_layout(bargap=0.05)
    return _fig_to_json(fig)


def chart_box_single(df: pd.DataFrame, num_col: str):
    """df col: 'value'"""
    fig = px.box(
        df, y='value',
        title=f"Spread of {num_col}",
        template=TEMPLATE,
        color_discrete_sequence=['#9d7dfa'],
        points='outliers',
    )
    fig.update_layout(annotations=[dict(
        text="Box = middle 50% | Line = median | Dots = outliers",
        xref="paper", yref="paper", x=0.5, y=-0.15,
        showarrow=False, font=dict(size=10, color='#8890a8'),
    )])
    return _fig_to_json(fig)


# ── RELATIONSHIPS ─────────────────────────────────────────────────────────────

def chart_scatter(df: pd.DataFrame, x_col: str, y_col: str, color_col: str = None):
    """df cols: 'x', 'y' [, 'color']"""
    kwargs = dict(
        x='x', y='y',
        title=f"{x_col} vs {y_col}",
        template=TEMPLATE,
        opacity=0.55,
        color_discrete_sequence=COLORS,
        trendline='ols',
        labels={'x': x_col, 'y': y_col},
    )
    if color_col and 'color' in df.columns:
        kwargs['color'] = 'color'
    try:
        fig = px.scatter(df, **kwargs)
    except Exception:
        kwargs.pop('trendline', None)
        fig = px.scatter(df, **kwargs)
    fig.update_traces(marker=dict(size=5))
    return _fig_to_json(fig)


def chart_bubble(df: pd.DataFrame, x_col: str, y_col: str, size_col: str):
    """df cols: 'x', 'y' [, 'size']"""
    if 'size' not in df.columns:
        return chart_scatter(df, x_col, y_col)
    fig = px.scatter(
        df, x='x', y='y', size='size',
        title=f"{x_col} vs {y_col} (size = {size_col})",
        template=TEMPLATE,
        color_discrete_sequence=COLORS,
        size_max=40, opacity=0.65,
        labels={'x': x_col, 'y': y_col},
    )
    return _fig_to_json(fig)


# ── TIME TRENDS ───────────────────────────────────────────────────────────────

def chart_line(df: pd.DataFrame, date_col: str, num_col: str, period: str, agg: str):
    """df cols: 'period', 'value'"""
    n   = len(df)
    fig = px.area(
        df, x='period', y='value',
        title=f"{agg} of {num_col} over time ({period})",
        template=TEMPLATE,
        markers=(n <= 60),
        color_discrete_sequence=['#5b7cff'],
        line_shape='spline',
        labels={'period': date_col, 'value': num_col},
    )
    fig.update_traces(fill='tozeroy', fillcolor='rgba(91,124,255,0.15)')
    fig.update_layout(xaxis=dict(tickangle=-45, nticks=min(24, n),
                                  tickfont=dict(size=9 if n > 24 else 11)))
    return _fig_to_json(fig)


def chart_mom_change(df: pd.DataFrame, num_col: str):
    """df cols: 'month', 'total', 'pct_change'"""
    df     = df.dropna(subset=['pct_change']).copy()
    colors = ['#2dd4a0' if v >= 0 else '#f56060' for v in df['pct_change']]
    n      = len(df)
    fig    = go.Figure(go.Bar(
        x=df['month'], y=df['pct_change'],
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in df['pct_change']],
        textposition='outside',
    ))
    fig.update_layout(
        title=f"Month-over-month % change — {num_col}",
        template=TEMPLATE,
        xaxis=dict(tickangle=-45, nticks=min(24,n), tickfont=dict(size=9 if n>24 else 11)),
        annotations=[dict(
            text="Green = growth · Red = decline",
            xref="paper", yref="paper", x=0, y=-0.22,
            showarrow=False, font=dict(size=10, color='#8890a8'),
        )],
    )
    return _fig_to_json(fig)


def chart_day_of_week(df: pd.DataFrame, num_col: str):
    """df cols: 'dow_num', 'day_name', 'avg_value'"""
    fig = px.bar(
        df, x='day_name', y='avg_value',
        title=f"Average {num_col} by day of week",
        template=TEMPLATE,
        text='avg_value',
        color_discrete_sequence=COLORS,
    )
    fig.update_traces(texttemplate='%{text:,.1f}', textposition='outside',
                      marker_color=COLORS[1])
    return _fig_to_json(fig)


def chart_seasonality(df: pd.DataFrame, num_col: str):
    """df cols: 'month_num', 'month_name', 'avg_value'"""
    fig = px.line(
        df, x='month_name', y='avg_value',
        title=f"Monthly seasonality — {num_col}",
        template=TEMPLATE,
        markers=True,
        color_discrete_sequence=['#f97316'],
        line_shape='spline',
    )
    fig.update_traces(fill='tozeroy', fillcolor='rgba(249,115,22,0.1)',
                      marker=dict(size=8))
    fig.update_layout(xaxis={
        'categoryorder': 'array',
        'categoryarray': ['Jan','Feb','Mar','Apr','May','Jun',
                          'Jul','Aug','Sep','Oct','Nov','Dec'],
    })
    return _fig_to_json(fig)


# ── TOP TRENDS ───────────────────────────────────────────────────────────────

def chart_top_bottom_table(df: pd.DataFrame, cat_col: str, num_col: str, n: int = 10):
    """Ranked table as a Plotly table — top N and bottom N side by side."""
    top    = df.head(n).copy()
    bottom = df.tail(n).iloc[::-1].copy()
    fig = go.Figure(data=[go.Table(
        columnwidth=[3, 2, 3, 2],
        header=dict(
            values=[f'🏆 Top {n} — {cat_col}', f'{num_col}',
                    f'⚠ Bottom {n} — {cat_col}', f'{num_col}'],
            fill_color='#1a1e27',
            font=dict(color='#8890a8', size=11),
            line_color='#2c3145',
            align='left',
        ),
        cells=dict(
            values=[
                top['category'].apply(lambda x: str(x)[:22]).tolist(),
                [f"{v:,.1f}" for v in top['value']],
                bottom['category'].apply(lambda x: str(x)[:22]).tolist(),
                [f"{v:,.1f}" for v in bottom['value']],
            ],
            fill_color=[['#12151c', '#1a1e27'] * (n // 2 + 1)] * 4,
            font=dict(color=['#2dd4a0','#eceef5','#f56060','#eceef5'], size=11),
            line_color='#2c3145',
            align='left',
        ),
    )])
    fig.update_layout(
        title=f"Top vs Bottom — {cat_col} by {num_col}",
        template=TEMPLATE,
        margin=dict(t=40, b=10, l=10, r=10),
        height=max(300, n * 32 + 80),
    )
    return _fig_to_json(fig)


def chart_treemap(df: pd.DataFrame, cat_col: str, num_col: str):
    """df cols: 'category', 'value' — treemap gives size intuition"""
    df = df.copy()
    df['category'] = _trim(df['category'], 22)
    df['value']    = df['value'].abs()
    fig = px.treemap(
        df, path=['category'], values='value',
        title=f"Treemap — {num_col} by {cat_col}",
        template=TEMPLATE,
        color='value',
        color_continuous_scale='Blues',
    )
    fig.update_traces(textinfo='label+value+percent root')
    fig.update_layout(coloraxis_showscale=False, margin=dict(t=40,b=10,l=10,r=10))
    return _fig_to_json(fig)


def chart_running_total(df: pd.DataFrame, date_col: str, num_col: str):
    """df cols: 'day', 'daily_total', 'running_total'"""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df['day'], y=df['daily_total'],
        name='Daily', marker_color='rgba(91,124,255,0.5)',
        yaxis='y',
    ))
    fig.add_trace(go.Scatter(
        x=df['day'], y=df['running_total'],
        name='Cumulative', line=dict(color='#2dd4a0', width=2),
        yaxis='y2',
    ))
    n = len(df)
    fig.update_layout(
        title=f"Daily vs Cumulative {num_col}",
        template=TEMPLATE,
        yaxis=dict(title='Daily', gridcolor='#2c3145'),
        yaxis2=dict(title='Cumulative', overlaying='y', side='right',
                    gridcolor='#2c3145'),
        legend=dict(bgcolor=_TRANSP),
        xaxis=dict(tickangle=-45, nticks=min(30,n)),
        margin=dict(t=40, b=60, l=60, r=60),
        barmode='overlay',
    )
    return _fig_to_json(fig)