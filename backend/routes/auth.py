import os
from pathlib import Path
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, auth, firestore
from fastapi import Header, HTTPException, status

# Load environment variables from project .env (project root)
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


# Build service account info from environment variables
_service_account_info = {
    "type": "service_account",
    "project_id": os.getenv("GOOGLE_PROJECT_ID"),
    "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("GOOGLE_PRIVATE_KEY") or "",
    "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
    "client_id": os.getenv("GOOGLE_CLIENT_ID"),
    "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
    "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_X509_CERT_URL"),
    "universe_domain": os.getenv("GOOGLE_UNIVERSE_DOMAIN"),
}

if _service_account_info["private_key"]:
    # In .env the private key often contains escaped newlines
    _service_account_info["private_key"] = _service_account_info[
        "private_key"
    ].replace("\\n", "\n")


def init_firebase():
    """Initialize Firebase app (idempotent) and return a Firestore client."""
    if not firebase_admin._apps:
        cred = credentials.Certificate(_service_account_info)
        firebase_admin.initialize_app(cred)
    return firestore.client()


async def get_current_user(authorization: str = Header(...)) -> dict:
    """Verify Firebase Bearer token and ensure a role document exists in Firestore.

    Returns a dict with at least: {'uid', 'email', 'role'}
    Raises HTTPException with 401 on invalid/missing token.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.split(" ", 1)[1]

    # ensure firebase is initialized
    if not firebase_admin._apps:
        init_firebase()

    try:
        decoded_token = auth.verify_id_token(
            token, check_revoked=False, clock_skew_seconds=60
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Firebase token")

    uid = decoded_token.get("uid")
    email = decoded_token.get("email")

    fs = firestore.client()
    doc_ref = fs.collection("role").document(uid)
    doc = doc_ref.get()
    if doc.exists:
        role = doc.to_dict().get("role", "user")
    else:
        role = "user"
        # create minimal role document
        doc_ref.set({"role": role, "email": email})

    return {"uid": uid, "email": email, "role": role}
