"""
API hiển thị thông tin chi tiết 1 thủ tục
GET /procedures/{id}
"""

from __future__ import annotations

import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path, Depends, FastAPI
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import jwt

from data_interaction.neo4j_handler import Neo4jHandler
from database import get_db
from config import settings

# Router
router = APIRouter()

# Security
security = HTTPBearer()

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
# Models (khớp file JSON KG)
# =========================
class ProcedureDetail(BaseModel):
    id: str                                   # elementId của node Thutuc
    code: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    budgets: List[str] = Field(default_factory=list)
    docs: List[str] = Field(default_factory=list)
    note: Optional[str] = None

class ProcedureDetailResponse(BaseModel):
    success: bool
    data: ProcedureDetail

class ErrorResponse(BaseModel):
    success: bool
    message: str

# =========================
# Neo4j client
# =========================
neo4j = Neo4jHandler(
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    user=os.getenv("NEO4J_USER", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "12345678"),
)

# =========================
# Endpoint
# =========================
@router.get("/procedures/{procedure_id}", response_model=ProcedureDetailResponse)
async def get_procedure_detail(
    procedure_id: str = Path(..., description="ID của thủ tục (internal id, elementId hoặc code, hoặc elementId của sub-item)"),
    current_user: dict = Depends(get_current_user),
):
    """
    Lấy thông tin chi tiết 1 thủ tục theo đúng cấu trúc JSON nguồn:
    - code, title, category
    - budgets: [string]
    - docs:    [string]
    - note:    string

    Hỗ trợ cả trường hợp procedure_id là elementId của 1 sub-item (docs/budgets/category),
    khi đó API tự suy ra Thutuc cha trong phạm vi 1..3 bước quan hệ.
    """

    # Thử parse về số để match id(t)
    pid_int: Optional[int] = None
    try:
        pid_int = int(procedure_id)
    except Exception:
        pid_int = None

    cypher = """
    // --------- Xác định node Thutuc 't' từ nhiều kiểu ID đầu vào ---------
    CALL {
      WITH $pid AS pid, $pidInt AS pidInt
      // a) Match trực tiếp Thutuc theo elementId / code / id(t)
      OPTIONAL MATCH (t1:Thutuc)
      WHERE elementId(t1) = pid
         OR t1.code       = pid
         OR (pidInt IS NOT NULL AND id(t1) = pidInt)
      WITH collect(t1) AS ts
      RETURN CASE WHEN size(ts) > 0 THEN ts[0] ELSE NULL END AS t_direct
    }

    CALL {
      WITH $pid AS pid
      // b) Nếu pid là elementId của 1 node bất kỳ x, lần ngược sang Thutuc trong phạm vi 1..3
      OPTIONAL MATCH (x) WHERE elementId(x) = pid
      OPTIONAL MATCH (t2:Thutuc)-[*1..3]-(x)
      WITH collect(t2) AS t2s
      RETURN CASE WHEN size(t2s) > 0 THEN t2s[0] ELSE NULL END AS t_from_child
    }

    WITH coalesce(t_direct, t_from_child) AS t
    WHERE t IS NOT NULL

    // --------- Thu thập dữ liệu chi tiết theo KG ---------
    OPTIONAL MATCH (t)-[:HAS_CATEGORY]->(c:category)
    OPTIONAL MATCH (c)-[:HAS_ITEM]->(bc:budgets)

    OPTIONAL MATCH (t)-[:HAS_BUDGET]->(bd:budgets)

    OPTIONAL MATCH (t)-[:REQUIRES]->(d:docs)
    OPTIONAL MATCH (t)-[:NOTE]->(n:note)

    WITH t,
         collect(DISTINCT coalesce(c.name, ''))  AS catNames,
         collect(DISTINCT coalesce(bc.name, '')) AS catBudgetNames,
         collect(DISTINCT coalesce(bd.name, '')) AS directBudgetNames,
         collect(DISTINCT coalesce(d.title, '')) AS docTitles,
         head(collect(DISTINCT coalesce(n.description, ''))) AS noteText

    WITH t, docTitles, noteText,
         head([x IN catNames WHERE x <> '']) AS categoryName,
         // Gộp & khử trùng budgets
         reduce(acc = [], x IN [y IN (catBudgetNames + directBudgetNames) WHERE y <> ''] |
           CASE WHEN x IN acc THEN acc ELSE acc + [x] END
         ) AS budgetsAll

    WITH t, noteText, categoryName, budgetsAll,
         // Khử rỗng & khử trùng docs
         reduce(acc = [], x IN [y IN docTitles WHERE y <> ''] |
           CASE WHEN x IN acc THEN acc ELSE acc + [x] END
         ) AS docsAll

    RETURN
      elementId(t)            AS id,
      coalesce(t.code, '')    AS code,
      coalesce(t.title, '')   AS title,
      coalesce(categoryName,'') AS category,
      budgetsAll              AS budgets,
      docsAll                 AS docs,
      coalesce(noteText,'')   AS note
    LIMIT 1
    """

    try:
        with neo4j.driver.session() as session:
            rec = session.run(
                cypher,
                pid=procedure_id.strip(),
                pidInt=pid_int
            ).single()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j error: {e}")

    if not rec:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thủ tục với ID {procedure_id}")

    row = rec.data()  # an toàn hơn so với rec.get(...)
    detail = ProcedureDetail(
        id=str(row.get("id") or ""),
        code=(str(row.get("code") or "") or None),
        title=(str(row.get("title") or "") or None),
        category=(str(row.get("category") or "") or None),
        budgets=[str(x) for x in (row.get("budgets") or [])],
        docs=[str(x) for x in (row.get("docs") or [])],
        note=(str(row.get("note") or "") or None),
    )

    return ProcedureDetailResponse(success=True, data=detail)

