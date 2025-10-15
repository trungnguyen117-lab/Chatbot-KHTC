import os
from dotenv import load_dotenv

load_dotenv()

# Neo4j configurations
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7688")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# File paths
# DOCLING_INPUT_PATH = "upload_file/Quy trinh Kiem soat chi va Thanh toan cua UET (03.01.2021).docx"
# DOCLING_OUTPUT_PATH = "json_output/chapter_3.json"
# TEXT_JSON_PATH = "json_text/quytrinh.json"

# LLM configurations
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "AIzaSyCs1XRT1wkGIXGj-1XvV4nYCCpQj4PfhIk")

# Cypher queries
WIPE_ALL_CYPHER = "MATCH (n) DETACH DELETE n"
CLEANUP_REMOVE_ID = """
MATCH (n)
WHERE any(l IN labels(n) WHERE l IN [
    'Quytrinh','Phamvi','Thutuc','Thanhphandutoan','Hosochungtu','Ghichu'
])
REMOVE n.id
"""