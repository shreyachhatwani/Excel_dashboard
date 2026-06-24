import os
from dotenv import load_dotenv

# This looks for the .env file and loads its variables into your system memory
load_dotenv()

# ── Neo4j AuraDB cloud credentials (from console.neo4j.io)
NEO4J_URI  = "neo4j+s://f0629c74.databases.neo4j.io"
NEO4J_USER = "neo4j"
# Fetched securely from your local .env file
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# ── PostgreSQL local credentials
POSTGRES_HOST     = "127.0.0.1"
POSTGRES_PORT     = 5433
POSTGRES_USER     = "postgres"
# Fetched securely from your local .env file
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB       = "dashboard_db"

# ── Input source — set ONE
EXCEL_FILE_PATH   = r""
EXCEL_FOLDER_PATH = r"C:\Users\Shreya\Downloads\Monthly Item Wise Sales report\Monthly Item Wise Sales report"

# ── Cache file
CACHE_FILE = "cache.json"