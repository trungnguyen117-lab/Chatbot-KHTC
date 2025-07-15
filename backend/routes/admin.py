from fastapi import APIRouter



router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/")

def get_admin():
    return "Admin"
