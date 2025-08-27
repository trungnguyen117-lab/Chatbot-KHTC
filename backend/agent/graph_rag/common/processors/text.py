from typing import Dict, Any, List
from langchain_community.graphs.graph_document import GraphDocument, Node, Relationship
from langchain_core.documents import Document
from ..utils.helpers import load_json

def build_graph_documents(payload: Dict[str, Any]) -> List[GraphDocument]:
    """Build GraphDocuments for Text schema"""
    nodes: Dict[str, Node] = {}
    rels: List[Relationship] = []

    # Helper tạo node
    def add_nodes(label: str, items: list, props_map: Dict[str,str]):
        for it in items:
            nid = it["id"]
            props = {pname: it.get(jname) for pname, jname in props_map.items()}
            nodes[nid] = Node(type=label, id=nid, properties=props)

    # Tạo các loại node
    add_nodes("Document", payload.get("Documents", []), {
        "name": "Name", 
        "number_of_pages": "Number_of_Pages", 
        "number_of_chapter": "Number_of_Chapter"
    })
    add_nodes("Chapter", payload.get("Chapters", []), {
        "name": "Name", 
        "number": "Number"
    })
    add_nodes("Section", payload.get("Sections", []), {
        "name": "Name", 
        "number": "Number"
    })

    # Tạo quan hệ
    for rel in payload.get("Relationships", []):
        src = nodes.get(rel["from"])
        tgt = nodes.get(rel["to"])
        if src and tgt:
            rels.append(Relationship(source=src, target=tgt, type=rel["type"], properties={}))

    src_doc = Document(page_content="Text Import", metadata={})
    return [GraphDocument(nodes=list(nodes.values()), relationships=rels, source=src_doc)]