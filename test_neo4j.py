# test_neo4j.py
from neo4j import GraphDatabase

URI      = "neo4j+s://f0629c74.databases.neo4j.io"
USER     = "neo4j"
PASSWORD = "Z0KaSjUb8rKCdFECzV-onQ7E0XRrZMLzrrpABrHSIrs"

try:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    driver.verify_connectivity()
    print("✓ Connected successfully")
    driver.close()
except Exception as e:
    print("✗ Failed:", e)