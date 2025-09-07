from typing import Dict, Any, List, Optional
import re

from unidecode import unidecode  # pip install Unidecode
from docling.document_converter import DocumentConverter
from langchain_community.graphs.graph_document import GraphDocument, Node, Relationship
from langchain_core.documents import Document

from ..utils.helpers import (
    is_roman,
    is_digit,
    is_letter,
    ROMAN,
    DIGIT,
    clean_text,
    split_docs,
    split_title,
    save_json,
)

# ============================================================
# Regex patterns để bắt tiêu đề quy trình
# ============================================================

PROCEDURE_PATTERNS = [
    # Pattern 1: QUY TRÌNH X. TITLE
    re.compile(
        r"^(?:QUY\s+TRÌNH|HƯỚNG\s+DẪN)\s+(\d+)[\s.:\-]*([^.]+(?:\.[^.]+)*)\s*$",
        flags=re.IGNORECASE | re.MULTILINE,
    ),
    # Pattern 2: QUY TRÌNH: TITLE
    re.compile(
        r"(?:QUY\s+TRÌNH|HƯỚNG\s+DẪN)\s*[:：]\s*([^.]+(?:\.[^.]+)*)\s*$",
        flags=re.IGNORECASE | re.MULTILINE,
    ),
    # Pattern 3: CHƯƠNG X. QUY TRÌNH TITLE
    re.compile(
        r"^(?:CHƯƠNG|PHẦN)\s+(\d+)[.\s]*(?:QUY\s+TRÌNH|HƯỚNG\s+DẪN)\s+([^.]+(?:\.[^.]+)*)\s*$",
        flags=re.IGNORECASE | re.MULTILINE,
    ),
]

# ============================================================
# Keyword để nhận diện type tổng (chỉ dùng cho JSON tổng)
# ============================================================

TYPE_KEYWORDS = {
    "domestic": [
        "trong nước",
        "trong nước",
        "nội địa",
        "nội địa",
        "công tác phí trong nước",
    ],
    "foreign": [
        "nước ngoài",
        "nước ngoài",
        "quốc tế",
        "quốc tế",
        "công tác phí nước ngoài",
        "công tác phí nước ngoài",
    ],
}


def detect_procedure_type(*texts: str) -> str:
    """
    Trả về 'domestic' hoặc 'foreign' dựa vào từ khóa trong text (mục đích: type tổng trong JSON).
    Ưu tiên foreign nếu có cả hai. Nếu không thấy gì -> 'domestic'.
    """
    haystack = " ".join([t or "" for t in texts]).lower()
    if any(k in haystack for k in TYPE_KEYWORDS["foreign"]):
        return "foreign"
    if any(k in haystack for k in TYPE_KEYWORDS["domestic"]):
        return "domestic"
    return "domestic"


# ============================================================
# Tìm tiêu đề quy trình trong text rời rạc
# ============================================================

def find_procedure_in_text(text: str) -> Optional[Dict[str, str]]:
    """
    Tìm các định dạng quy trình trong text:
    - QUY TRÌNH X. TITLE
    - QUY TRÌNH: TITLE
    - CHƯƠNG X. QUY TRÌNH TITLE
    """
    if not text:
        return None

    normalized = " ".join(line.strip() for line in text.splitlines() if line.strip())

    for pattern in PROCEDURE_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue

        if len(match.groups()) == 2:
            code = match.group(1).strip()
            title = match.group(2).strip()
        elif len(match.groups()) == 1:
            code = "0"
            title = match.group(1).strip()
        else:  # >= 2
            code = match.group(1).strip()
            title = match.group(2).strip()

        full = f"QUY TRÌNH {code}. {title}"
        return {"code": code, "title": title.upper(), "full": full}

    return None


# ============================================================
# Chuyển bảng ➜ schema trung gian sections -> groups -> items
# ============================================================

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
            "Ghichu": clean_text(notes),
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
                if not extra and (docs or "").strip():
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


# ============================================================
# Xử lý docling ➜ JSON cấu trúc (type tổng)
# ============================================================

def process_docling_document(doc_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Process raw docling output into structured data"""
    text_blocks: List[str] = []

    # 1) Thu thập text/heading
    title = (doc_dict.get("title") or "").strip()
    if title:
        text_blocks.append(title)

    doc_text = (doc_dict.get("text") or "").strip()
    if doc_text:
        text_blocks.append(doc_text)

    for block in doc_dict.get("blocks", []) or []:
        if isinstance(block, dict):
            text = (block.get("text") or "").strip()
            if text:
                text_blocks.append(text)
            style = (block.get("style") or "").strip().lower()
            if ("heading" in style or "title" in style) and text:
                text_blocks.append(text)

    for page in doc_dict.get("pages", []) or []:
        if isinstance(page, dict):
            p_text = (page.get("text") or "").strip()
            if p_text:
                text_blocks.append(p_text)
            for element in page.get("elements", []) or []:
                if isinstance(element, dict):
                    e_text = (element.get("text") or "").strip()
                    style = (element.get("style") or "").lower()
                    if e_text:
                        text_blocks.append(e_text)
                        if "heading" in style or "title" in style:
                            text_blocks.append(e_text)

    # 2) Tìm tiêu đề quy trình
    procedure = None
    for t in text_blocks:
        proc = find_procedure_in_text(t)
        if proc:
            procedure = proc
            break

    # 3) Process tables -> schema
    structured_all: List[Dict[str, Any]] = []
    for tb in doc_dict.get("tables", []) or []:
        grid = tb.get("data", {}).get("grid", [])
        if not grid:
            continue
        header = [c.get("text", "").strip() for c in grid[0]]
        rows = [[c.get("text", "").strip() for c in r] for r in grid[1:]]
        schema = table_to_schema(header, rows)
        structured_all.append(schema)

    # 4) Xác định type tổng (for JSON)
    all_text_for_type = " ".join(text_blocks + [title, doc_text])
    proc_type = detect_procedure_type(
        (procedure or {}).get("full", ""),
        (procedure or {}).get("title", ""),
        all_text_for_type,
    )

    # 5) Build result JSON
    return {
        "Quytrinh": {
            "title": (procedure or {}).get("title") or "QUY TRÌNH KIỂM SOÁT CHI VÀ THANH TOÁN",
            "code": (procedure or {}).get("code") or "1",
            "full_title": (procedure or {}).get("full") or "QUY TRÌNH 1. KIỂM SOÁT CHI VÀ THANH TOÁN",
            "original_title": title,
            "type": proc_type,  # type tổng (tham khảo)
            "tables_structured": structured_all,
        }
    }


def convert_docx_to_json(input_path: str, output_path: str) -> Dict[str, Any]:
    """Convert DOCX to structured JSON using Docling"""
    converter = DocumentConverter()
    result = converter.convert(input_path)
    doc_dict = result.document.model_dump()
    structured_data = process_docling_document(doc_dict)
    save_json(structured_data, output_path)
    return structured_data


# ============================================================
# Build GraphDocuments & gán type cho từng node
# ============================================================

def build_graph_documents(payload: Dict[str, Any]) -> List[GraphDocument]:
    """
    Build GraphDocuments từ JSON Docling
    - Gán field 'type': 'domestic', 'foreign' hoặc 'other'
      + 'foreign': chỉ có 'nước ngoài'
      + 'domestic': chỉ có 'trong nước'
      + 'other': có cả 'trong nước' và 'nước ngoài'
      + nếu không phát hiện gì -> 'domestic'
    """

    # Hàm phụ: xác định type từ tiêu đề (bỏ dấu + lower)
    def detect_type_from_title(title: str) -> str:
        s = unidecode((title or "").strip()).lower()
        has_foreign = bool(re.search(r"\bnuoc ngoai\b", s))
        has_domestic = bool(re.search(r"\btrong nuoc\b", s))
        if has_foreign and has_domestic:
            return "other"
        if has_foreign:
            return "foreign"
        if has_domestic:
            return "domestic"
        return "domestic"

    root = payload.get("Quytrinh", {}) or {}
    proc_title = root.get("title", "Unknown")
    proc_code = root.get("code", "0")
    proc_full = root.get("full_title", proc_title)
    tables = root.get("tables_structured", []) or []

    nodes: Dict[tuple, Node] = {}
    rels: List[Relationship] = []

    # Node Quytrinh (mặc định domestic)
    q_id = f"Quytrinh|{proc_code}"
    q_node = Node(
        type="Quytrinh",
        id=q_id,
        properties={
            "title": proc_title,
            "code": proc_code,
            "full_title": proc_full,
            "type": "domestic",
        },
    )
    nodes[(q_node.type, q_node.id)] = q_node

    for tbl_idx, tbl in enumerate(tables):
        for sec in (tbl.get("sections") or []):
            sec_code = (sec.get("code") or "").strip().upper()
            sec_title = sec.get("title") or "Chưa rõ"
            sec_label = sec.get("label") or "Phamvi"

            if not ROMAN.match(sec_code):
                continue

            # Gán type cho Section
            sec_type = detect_type_from_title(sec_title)

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
                    "type": sec_type,
                },
            )
            nodes[(s_node.type, s_node.id)] = s_node
            rels.append(Relationship(source=q_node, target=s_node, type="HAS_SECTION", properties={}))

            for grp in (sec.get("groups") or []):
                grp_code = (grp.get("code") or "").strip()
                grp_title = grp.get("title") or "Chưa rõ"

                if not DIGIT.match(grp_code):
                    continue

                # Group ưu tiên tự detect; nếu không rõ thì kế thừa từ Section
                grp_type_detected = detect_type_from_title(grp_title)
                if grp_type_detected == "domestic" and sec_type in ("foreign", "other"):
                    grp_type = sec_type
                elif grp_type_detected == "foreign" and sec_type in ("domestic", "other"):
                    grp_type = sec_type
                elif grp_type_detected == "other":
                    grp_type = "other"
                else:
                    # grp_type_detected == 'domestic' và sec_type == 'domestic' hoặc không xác định thêm
                    grp_type = grp_type_detected or sec_type or "domestic"

                # Node Group (Thutuc)
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
                        "type": grp_type,
                    },
                )
                nodes[(t_node.type, t_node.id)] = t_node
                rels.append(Relationship(source=s_node, target=t_node, type="HAS_ITEM", properties={}))

                for itm in (grp.get("items") or []):
                    item_code = (itm.get("code") or "").strip().lower()
                    if not item_code:
                        continue

                    # Node Thanhphandutoan
                    for name in (itm.get("Thanhphandutoan") or []):
                        name = (name or "").strip()
                        if not name:
                            continue
                        tp_id = f"Thanhphandutoan|{name}"
                        tp_node = Node(
                            type="Thanhphandutoan",
                            id=tp_id,
                            properties={"name": name, "type": grp_type},
                        )
                        nodes[(tp_node.type, tp_node.id)] = tp_node
                        rels.append(
                            Relationship(
                                source=t_node,
                                target=tp_node,
                                type="REQUIRES",
                                properties={"item": item_code},
                            )
                        )

                    # Node Hosochungtu
                    for name in (itm.get("Hosochungtu") or []):
                        name = (name or "").strip()
                        if not name:
                            continue
                        hs_id = f"Hosochungtu|{name}"
                        hs_node = Node(
                            type="Hosochungtu",
                            id=hs_id,
                            properties={"name": name, "type": grp_type},
                        )
                        nodes[(hs_node.type, hs_node.id)] = hs_node
                        rels.append(
                            Relationship(
                                source=t_node,
                                target=hs_node,
                                type="REQUIRES",
                                properties={"item": item_code},
                            )
                        )

                    # Node Ghichu
                    note_text = (itm.get("Ghichu") or "").strip()
                    if note_text and note_text not in {"-", "—", "N/A", "n/a", "None", "null"}:
                        gh_id = f"Ghichu|{proc_title}|{tbl_idx}|{sec_code}|{grp_code}|{item_code}|{note_text}"
                        gh_node = Node(
                            type="Ghichu",
                            id=gh_id,
                            properties={"text": note_text, "type": grp_type},
                        )
                        nodes[(gh_node.type, gh_node.id)] = gh_node
                        rels.append(
                            Relationship(
                                source=t_node,
                                target=gh_node,
                                type="NOTE",
                                properties={"item": item_code},
                            )
                        )

    src_doc = Document(page_content="Docling Import", metadata={})
    return [GraphDocument(nodes=list(nodes.values()), relationships=rels, source=src_doc)]