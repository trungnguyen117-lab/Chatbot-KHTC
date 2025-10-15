# dashboard_api.py
from __future__ import annotations

from data_interaction.neo4j_handler import Neo4jHandler

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
import jwt
import os
from database import get_db
from sqlalchemy.orm import Session
from config import settings
import re
from collections import defaultdict

# Router
router = APIRouter()

# Security
security = HTTPBearer()

# =========================
# Pydantic Models
# =========================
class SubItem(BaseModel):
    id: str
    title: str
    label: Optional[str] = None
    children: List["SubItem"] = Field(default_factory=list)

class Procedure(BaseModel):
    id: str
    title: str
    description: str
    date: str
    parent: Optional[str] = None
    subItems: List[SubItem] = Field(default_factory=list)

class ProceduresResponse(BaseModel):
    success: bool
    data: List[Procedure]

class SearchResult(BaseModel):
    id: int
    title: str
    description: str
    type: str

class SearchResponse(BaseModel):
    success: bool
    data: dict

class ErrorResponse(BaseModel):
    success: bool
    message: str

# Pydantic v1/v2 compat cho đệ quy
try:
    SubItem.model_rebuild()  # Pydantic v2
except Exception:
    try:
        SubItem.update_forward_refs()  # Pydantic v1
    except Exception:
        pass

# =========================
# Neo4j client
# =========================
neo4j = Neo4jHandler(
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    user=os.getenv("NEO4J_USER", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "12345678"),
)

# =========================
# Auth helpers
# =========================
def verify_token(token: str):
    """Verify JWT token"""
    try:
        alg = settings.algorithm
        algorithms = [alg] if isinstance(alg, str) else alg
        return jwt.decode(token, settings.secret_key, algorithms=algorithms)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    payload = verify_token(token)
    return payload

# =========================
# Utilities
# =========================
def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-]", "", s)
    return s

def _sanitize_leaf(item: Dict[str, Any], default_label: Optional[str] = None) -> Dict[str, Any]:
    """Chuẩn hoá 1 item lá: id, title, label (nếu có)."""
    return {
        "id": str(item.get("id", "")),
        "title": (item.get("title") or "").strip(),
        "label": item.get("label", default_label)
    }

def _to_hier_subitems(payload: Union[List[Dict[str, Any]], Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Chuẩn hóa danh sách subItems (list hoặc dict) sang định dạng chuẩn cho API dashboard."""
    out: List[Dict[str, Any]] = []

    # ========================
    # CASE A: payload là LIST
    # ========================
    if isinstance(payload, list):
        flat_budgets: List[Dict[str, Any]] = []

        for it in payload:
            if not isinstance(it, dict):
                continue
            label = it.get("label")
            title = (it.get("title") or "").strip()
            _id = str(it.get("id", "")) or f"group:{_slug(title)}"

            # --- CASE 1: CODE BLOCK (mới)
            if label == "code":
                children_clean = _to_hier_subitems(it.get("children") or [])
                if title:
                    out.append({
                        "id": _id,
                        "title": title,
                        "label": "code",
                        "children": children_clean
                    })
                continue

            # --- CASE 2: DOCS
            if label == "docs":
                leaf = _sanitize_leaf(it, default_label="docs")
                if leaf["id"] and leaf["title"]:
                    out.append(leaf)
                continue

            # --- CASE 3: BUDGETS
            if label == "budgets":
                # category-block: có children
                if "children" in it and isinstance(it.get("children"), list):
                    children_clean = []
                    for ch in it.get("children") or []:
                        leaf = _sanitize_leaf(ch, default_label="budgets")
                        if leaf["id"] and leaf["title"]:
                            children_clean.append(leaf)
                    if title:
                        out.append({
                            "id": _id,
                            "title": title,
                            "label": "budgets",
                            "children": children_clean
                        })
                else:
                    # budget phẳng
                    leaf = _sanitize_leaf(it, default_label="budgets")
                    if leaf["id"] and leaf["title"]:
                        flat_budgets.append(leaf)
                continue

            # --- CASE 4: NOTE
            if label == "note":
                leaf = _sanitize_leaf(it, default_label="note")
                if leaf["title"]:
                    out.append(leaf)
                continue

        # --- CASE 5: Gom nhóm budgets phẳng (ví dụ “Phí di chuyển: Taxi”)
        if flat_budgets:
            from collections import defaultdict
            groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            standalone: List[Dict[str, Any]] = []
            for b in flat_budgets:
                title = b["title"]
                if ":" in title:
                    parent, child = title.split(":", 1)
                    parent = parent.strip()
                    child = child.strip()
                    if child:
                        groups[parent].append({
                            "id": b["id"],
                            "title": child,
                            "label": "budgets"
                        })
                    else:
                        standalone.append(b)
                else:
                    standalone.append(b)

            # render ra group
            for parent_title, children in groups.items():
                out.append({
                    "id": f"group:{_slug(parent_title)}",
                    "title": parent_title,
                    "label": "budgets",
                    "children": children
                })
            out.extend(standalone)

        return out

    # ========================
    # CASE B: payload là DICT (định dạng cũ)
    # ========================
    if not isinstance(payload, dict):
        return out

    # DOCS
    for d in payload.get("docs", []) or []:
        leaf = _sanitize_leaf(d, default_label="docs")
        if leaf["id"] and leaf["title"]:
            out.append(leaf)

    # BUDGETS
    budgets = payload.get("budgets", []) or []
    has_category_blocks = any(isinstance(b, dict) and "children" in b for b in budgets)

    if has_category_blocks:
        for b in budgets:
            if not isinstance(b, dict):
                continue
            title = (b.get("title") or "").strip()
            _id = str(b.get("id", "")) or f"group:{_slug(title)}"
            if not title:
                continue
            children_clean = []
            for ch in (b.get("children") or []):
                leaf = _sanitize_leaf(ch, default_label="budgets")
                if leaf["id"] and leaf["title"]:
                    children_clean.append(leaf)
            out.append({
                "id": _id,
                "title": title,
                "label": "budgets",
                "children": children_clean
            })
    else:
        from collections import defaultdict
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        standalone: List[Dict[str, Any]] = []
        for b in budgets:
            if not isinstance(b, dict):
                continue
            leaf = _sanitize_leaf(b, default_label="budgets")
            if not (leaf["id"] and leaf["title"]):
                continue
            title = leaf["title"]
            if ":" in title:
                parent, child = title.split(":", 1)
                parent = parent.strip()
                child = child.strip()
                if child:
                    groups[parent].append({"id": leaf["id"], "title": child, "label": "budgets"})
                else:
                    standalone.append(leaf)
            else:
                standalone.append(leaf)

        for parent_title, children in groups.items():
            out.append({
                "id": f"group:{_slug(parent_title)}",
                "title": parent_title,
                "label": "budgets",
                "children": children
            })
        out.extend(standalone)

    return out


def _to_subitem_model(d: Dict[str, Any]) -> SubItem:
    """Chuyển dict {id,title,label?,children?} sang SubItem (đệ quy)."""
    return SubItem(
        id=str(d.get("id", "")),
        title=str(d.get("title", "")),
        label=d.get("label"),
        children=[_to_subitem_model(c) for c in (d.get("children") or [])]
    )

# =========================
# Endpoints
# =========================
@router.get("/dashboard/procedures", response_model=ProceduresResponse)
async def get_available_procedures(
    current_user: dict = Depends(get_current_user),
):
    """
    Lấy danh sách các thủ tục có sẵn.
    Hỗ trợ cả 2 định dạng subItems: list (mới, có label) hoặc dict (cũ).
    """
    try:
        procedures = neo4j.get_root_with_subitems(label="Thutuc")
    except AttributeError as e:
        raise HTTPException(status_code=500, detail=f"Neo4j handler missing method: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j error: {e}")

    result: List[Procedure] = []
    for proc in procedures or []:
        # subItems có thể là LIST (mới) hoặc DICT (cũ)
        raw_sub = proc.get("subItems")
        sub_items_hier = _to_hier_subitems(raw_sub if raw_sub is not None else [])

        result.append(Procedure(
            id=str(proc.get("id", "")),
            title=str(proc.get("title", "")),
            description=str(proc.get("description", "")) if proc.get("description") is not None else "",
            date=str(proc.get("date", "")) if proc.get("date") is not None else "",
            parent=str(proc.get("parent", "")) if proc.get("parent") is not None else "",
            subItems=[_to_subitem_model(si) for si in sub_items_hier],
        ))

    return ProceduresResponse(success=True, data=result)

@router.get("/dashboard/search", response_model=SearchResponse)
async def search_procedures(
    q: str = Query(..., min_length=1, description="Từ khóa tìm kiếm"),
    mode: int = Query(0, ge=0, le=1, description="0 (thường) hoặc 1 (thông minh)"),
    current_user: dict = Depends(get_current_user),
):
    """
    Tìm kiếm thủ tục trong Graph Database
    - q: Từ khóa tìm kiếm
    - mode: 0 = tìm kiếm thường, 1 = tìm kiếm thông minh
    """
    try:
        search_data = neo4j.search_procedures_in_graph(q.strip(), mode)
        return SearchResponse(success=True, data=search_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tìm kiếm: {str(e)}")