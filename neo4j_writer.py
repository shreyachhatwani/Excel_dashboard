# neo4j_writer.py  — writes data to Neo4j AuraDB and answers graph queries
import pandas as pd
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

_driver = None


def _get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        )
    return _driver


def write_incremental(df: pd.DataFrame, col_types: dict):
    """
    Appends only the rows in df to Neo4j — never rewrites existing nodes.
    Each row  → :Row node
    Each unique category value → :Category node  +  :HAS_CATEGORY edge
    Each source filename       → :SourceFile node +  :FROM_FILE edge
    """
    if df is None or df.empty:
        return

    driver        = _get_driver()
    numeric_cols  = [c for c, t in col_types.items() if t == "numeric"]
    category_cols = [c for c, t in col_types.items() if t == "category"]
    date_cols     = [c for c, t in col_types.items() if t == "date"]
    rows          = df.to_dict("records")
    batch_size    = 500

    with driver.session() as session:
        # Create indexes once — safe to re-run
        session.run("CREATE INDEX row_id_idx IF NOT EXISTS FOR (r:Row) ON (r._row_id)")
        session.run("CREATE INDEX cat_idx    IF NOT EXISTS FOR (c:Category) ON (c.col_name, c.value)")
        session.run("CREATE INDEX src_idx    IF NOT EXISTS FOR (s:SourceFile) ON (s.name)")

        # Find current max _row_id so we never duplicate
        result = session.run(
            "MATCH (r:Row) RETURN coalesce(max(r._row_id), -1) AS max_id"
        )
        offset = result.single()["max_id"] + 1

        for start in range(0, len(rows), batch_size):
            batch = rows[start: start + batch_size]

            # ── 1. Build Row node properties (numerics + dates only)
            node_batch = []
            for i, row in enumerate(batch):
                props = {"_row_id": offset + start + i}
                if "_source_file" in row and row["_source_file"]:
                    props["_source_file"] = str(row["_source_file"])
                for col in numeric_cols:
                    val = row.get(col)
                    if val is not None and val == val:   # skip NaN
                        try:
                            props[col] = float(val)
                        except Exception:
                            pass
                for col in date_cols:
                    val = row.get(col)
                    if val is not None:
                        props[col] = str(val)[:10]
                node_batch.append(props)

            session.run(
                "UNWIND $batch AS p CREATE (r:Row) SET r = p",
                batch=node_batch,
            )

            # ── 2. SourceFile nodes + FROM_FILE edges
            src_batch = [
                {
                    "row_id": offset + start + i,
                    "src":    str(row.get("_source_file", "unknown")),
                }
                for i, row in enumerate(batch)
                if row.get("_source_file")
            ]
            if src_batch:
                session.run(
                    """
                    UNWIND $batch AS item
                    MATCH  (r:Row {_row_id: item.row_id})
                    MERGE  (s:SourceFile {name: item.src})
                    CREATE (r)-[:FROM_FILE]->(s)
                    """,
                    batch=src_batch,
                )

            # ── 3. Category nodes + HAS_CATEGORY edges
            for col in category_cols:
                cat_batch = [
                    {
                        "row_id":   offset + start + i,
                        "col_name": col,
                        "value":    str(row.get(col, "")).strip(),
                    }
                    for i, row in enumerate(batch)
                    if row.get(col) is not None and str(row.get(col, "")).strip()
                ]
                if cat_batch:
                    session.run(
                        """
                        UNWIND $batch AS item
                        MATCH  (r:Row {_row_id: item.row_id})
                        MERGE  (c:Category {col_name: item.col_name, value: item.value})
                        CREATE (r)-[:HAS_CATEGORY {col: item.col_name}]->(c)
                        """,
                        batch=cat_batch,
                    )

    print(f"[neo4j] ✓ Appended {len(rows)} rows starting at _row_id={offset}")


def query_graph_for_category(col_name: str, value: str, limit: int = 60) -> dict:
    """Return all Row nodes connected to a given category value, as vis.js-ready dicts."""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (r:Row)-[:HAS_CATEGORY]->(c:Category {col_name: $col, value: $val})
            OPTIONAL MATCH (r)-[:FROM_FILE]->(s:SourceFile)
            RETURN r, c, s LIMIT $limit
            """,
            col=col_name, val=value, limit=limit,
        )
        nodes, edges, seen = [], [], set()
        for record in result:
            r, c, s = record["r"], record["c"], record.get("s")
            rid, cid = r.element_id, c.element_id
            if rid not in seen:
                seen.add(rid)
                nodes.append({"id": rid, "label": "Row",      "props": dict(r)})
            if cid not in seen:
                seen.add(cid)
                nodes.append({"id": cid, "label": "Category", "props": dict(c)})
            edges.append({"from": rid, "to": cid})
            if s:
                sid = s.element_id
                if sid not in seen:
                    seen.add(sid)
                    nodes.append({"id": sid, "label": "SourceFile", "props": dict(s)})
                edges.append({"from": rid, "to": sid})
    return {"nodes": nodes, "edges": edges}


def get_graph_summary() -> list:
    """Category nodes with row counts — used to populate the graph-tab dropdowns."""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (c:Category)<-[:HAS_CATEGORY]-(r:Row)
            RETURN c.col_name AS col, c.value AS value, count(r) AS row_count
            ORDER BY row_count DESC LIMIT 120
            """
        )
        return [dict(r) for r in result]


def get_source_files() -> list:
    """SourceFile nodes with row counts."""
    driver = _get_driver()
    with driver.session() as session:
        result = session.run(
            """
            MATCH (s:SourceFile)<-[:FROM_FILE]-(r:Row)
            RETURN s.name AS file, count(r) AS row_count
            ORDER BY row_count DESC
            """
        )
        return [dict(r) for r in result]