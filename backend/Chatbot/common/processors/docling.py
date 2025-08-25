from typing import Dict, Any, List
from docling.document_converter import DocumentConverter
from langchain_community.graphs.graph_document import GraphDocument, Node, Relationship
from langchain_core.documents import Document
from ..utils.helpers import (
    is_roman, is_digit, ROMAN, DIGIT, clean_text, 
    split_docs, split_title, save_json
)

def table_to_schema(header: list, rows: list) -> Dict[str, Any]:
    schema: Dict[str, Any] = {"sections": []}
    current_section = None
    current_group = None
    current_item = None

    def new_section(code, title):
        nonlocal current_section, current_group, current_item
        current_section = {"code": code, "title": title, "label": "Phamvi", "groups": []}
        schema["sections"].append(current_section)
        current_group = None
        current_item = None

    def new_group(code, title):
        nonlocal current_group, current_item
        current_group = {"code": code, "title": title, "label": "Thutuc", "items": []}
        current_section["groups"].append(current_group)
        current_item = None

    def new_item(code, title, docs, notes):
        nonlocal current_item
        current_item = {
            "code": code,
            "Thanhphandutoan": split_title(title),
            "label": "Thutuc",
            "Hosochungtu": split_docs(docs),
            "Ghichu": clean_text(notes)
        }
        current_group["items"].append(current_item)

    def append_to_last(content=None, docs=None, notes=None):
        nonlocal current_item, current_group
        if current_item is not None:
            if content:
                more = split_title(content)
                if more:
                    current_item["Thanhphandutoan"].extend(more)
            if docs:
                extra = split_docs(docs)
                if not extra and docs.strip():
                    extra = [clean_text(docs)]
                current_item["Hosochungtu"].extend(extra)
            if notes:
                cur = current_item.get("Ghichu", "")
                current_item["Ghichu"] = (cur + " " + clean_text(notes)).strip() if cur else clean_text(notes)
        elif current_group is not None and content:
            current_group["title"] = (current_group["title"] + " " + content).strip()

    for row in rows:
        cells = [c if isinstance(c, str) else str(c) for c in row]

        if len(cells) < 4:
            cells = cells + [""] * (4 - len(cells))
        elif len(cells) > 4:
            stt = cells[0]
            content = " ".join(cells[1:-2]) if len(cells) > 3 else cells[1]
            docs = cells[-2]
            notes = cells[-1]
            cells = [stt, content, docs, notes]

        stt, content, docs, notes = cells
        stt = (stt or "").strip()
        content = clean_text(content)
        docs = (docs or "").strip()
        notes = (notes or "").strip()

        if is_roman(stt):
            new_section(stt, content)
        elif is_digit(stt):
            if current_section is None:
                new_section("I", "Chưa rõ")
            new_group(stt, content)
        elif is_letter(stt) or stt == "-":
            if current_section is None:
                new_section("I", "Chưa rõ")
            if current_group is None:
                new_group("1", "Chưa rõ")
            new_item(stt, content, docs, notes)
        elif stt == "":
            append_to_last(content=content, docs=docs, notes=notes)
        else:
            if current_section is None:
                new_section("I", "Chưa rõ")
            if current_group is None:
                new_group("1", "Chưa rõ")
            new_item(stt, content, docs, notes)

    return schema


def process_docling_document(doc_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Process raw docling output into structured data"""
    structured_all = []
    for tb in doc_dict.get("tables", []):
        grid = tb.get("data", {}).get("grid", [])
        if not grid:
            continue
            
        header = [c.get("text", "").strip() for c in grid[0]]
        rows = [[c.get("text", "").strip() for c in r] for r in grid[1:]]
        schema = table_to_schema(header, rows)
        structured_all.append(schema)

    return {
        "Quytrinh": {
            "title": doc_dict.get("title", "Unknown"),
            "tables_structured": structured_all
        }
    }


def convert_docx_to_json(input_path: str, output_path: str) -> Dict[str, Any]:
    """Convert DOCX to structured JSON using Docling"""
    converter = DocumentConverter()
    result = converter.convert(input_path)
    
    # Process the conversion result
    doc_dict = result.document.model_dump()
    structured_data = process_docling_document(doc_dict)
    
    # Save to JSON file
    save_json(structured_data, output_path)
    return structured_data

def build_graph_documents(payload: Dict[str, Any]) -> List[GraphDocument]:
    """Build GraphDocuments for Docling schema"""
    root = payload.get("Quytrinh", {})
    proc_title = root.get("title", "Unknown")
    tables = root.get("tables_structured", [])

    nodes: Dict[tuple, Node] = {}
    rels: List[Relationship] = []

    # Node Quytrinh
    q_id = f"Quytrinh|{proc_title}"
    q_node = Node(type="Quytrinh", id=q_id, properties={"title": proc_title})
    nodes[(q_node.type, q_node.id)] = q_node

    for tbl_idx, tbl in enumerate(tables):
        for sec in (tbl.get("sections") or []):
            sec_code = (sec.get("code") or "").strip().upper()
            sec_title = sec.get("title") or "Chưa rõ"
            sec_label = sec.get("label") or "Phamvi"

            if not ROMAN.match(sec_code):
                continue

            # Node Phamvi
            s_id = f"Phamvi|{proc_title}|{tbl_idx}|{sec_code}"
            s_node = Node(
                type="Phamvi",
                id=s_id,
                properties={
                    "proc": proc_title,
                    "tableIdx": tbl_idx,
                    "code": sec_code,
                    "title": sec_title,
                    "label": sec_label,
                },
            )
            nodes[(s_node.type, s_node.id)] = s_node
            rels.append(Relationship(source=q_node, target=s_node, type="HAS_SECTION", properties={}))

            for grp in (sec.get("groups") or []):
                grp_code = (grp.get("code") or "").strip()
                grp_title = grp.get("title") or "Chưa rõ"

                if not DIGIT.match(grp_code):
                    continue

                # Node Thutuc
                t_id = f"Thutuc|{proc_title}|{tbl_idx}|{sec_code}|{grp_code}"
                t_node = Node(
                    type="Thutuc",
                    id=t_id,
                    properties={
                        "proc": proc_title,
                        "tableIdx": tbl_idx,
                        "sectionCode": sec_code,
                        "code": grp_code,
                        "title": grp_title,
                        "label": "Thutuc",
                        "level": "group",
                    },
                )
                nodes[(t_node.type, t_node.id)] = t_node
                rels.append(Relationship(source=s_node, target=t_node, type="HAS_ITEM", properties={}))

                for itm in (grp.get("items") or []):
                    item_code = (itm.get("code") or "").strip().lower()
                    if not item_code:
                        continue

                    # Thanhphandutoan
                    for name in (itm.get("Thanhphandutoan") or []):
                        name = (name or "").strip()
                        if not name:
                            continue
                        tp_id = f"Thanhphandutoan|{name}"
                        tp_node = Node(type="Thanhphandutoan", id=tp_id, properties={"name": name})
                        nodes[(tp_node.type, tp_node.id)] = tp_node
                        rels.append(
                            Relationship(source=t_node, target=tp_node, type="REQUIRES", properties={"item": item_code})
                        )

                    # Hosochungtu
                    for name in (itm.get("Hosochungtu") or []):
                        name = (name or "").strip()
                        if not name:
                            continue
                        hs_id = f"Hosochungtu|{name}"
                        hs_node = Node(type="Hosochungtu", id=hs_id, properties={"name": name})
                        nodes[(hs_node.type, hs_node.id)] = hs_node
                        rels.append(
                            Relationship(source=t_node, target=hs_node, type="REQUIRES", properties={"item": item_code})
                        )

                    # Ghichu
                    note_text = (itm.get("Ghichu") or "").strip()
                    if note_text and note_text not in {"-", "—", "N/A", "n/a", "None", "null"}:
                        gh_id = f"Ghichu|{proc_title}|{tbl_idx}|{sec_code}|{grp_code}|{item_code}|{note_text}"
                        gh_node = Node(type="Ghichu", id=gh_id, properties={"text": note_text})
                        nodes[(gh_node.type, gh_node.id)] = gh_node
                        rels.append(
                            Relationship(source=t_node, target=gh_node, type="NOTE", properties={"item": item_code})
                        )

    src_doc = Document(page_content="Docling Import", metadata={})
    return [GraphDocument(nodes=list(nodes.values()), relationships=rels, source=src_doc)]