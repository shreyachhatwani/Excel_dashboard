# config.py

# ── Neo4j AuraDB cloud credentials (from console.neo4j.io)
NEO4J_URI      = "neo4j+s://f0629c74.databases.neo4j.io"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "Z0KaSjUb8rKCdFECzV-onQ7E0XRrZMLzrrpABrHSIrs"

# ── PostgreSQL local credentials
# These are the values you set during PostgreSQL installation
POSTGRES_HOST     = "127.0.0.1"
POSTGRES_PORT     = 5433
POSTGRES_USER     = "postgres"
POSTGRES_PASSWORD = "87654321@"   # what you set during install
POSTGRES_DB       = "dashboard_db"               # the DB you created in pgAdmin

# ── Input source — set ONE
EXCEL_FILE_PATH   = r""
EXCEL_FOLDER_PATH = r"C:\Users\Shreya\Downloads\Monthly Item Wise Sales report\Monthly Item Wise Sales report"

# ── Cache file
CACHE_FILE = "cache.json"
