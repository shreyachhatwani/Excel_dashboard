# test_pg.py
import psycopg2

try:
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=5433,
        user="postgres",
        password="87654321@",
        dbname="dashboard_db",
    )
    print("✓ Connected successfully")
    conn.close()
except Exception as e:
    print("✗ Failed:", e)