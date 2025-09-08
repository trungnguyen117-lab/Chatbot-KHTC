import os
from dotenv import load_dotenv

load_dotenv()

# Neo4j configurations
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# File paths
DOCLING_INPUT_PATH = "E:/Github/Chatbot-KHTC/backend/upload_file/22.4.2024 UET Quy che chi tieu noi bo TV.docx"
DOCLING_OUTPUT_PATH = "E:/Github/Chatbot-KHTC/backend/json_output/chapter_3.json"
TEXT_JSON_PATH = "D:/KHTC/Chatbot-KHTC/backend/json_text/quytrinh.json"

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