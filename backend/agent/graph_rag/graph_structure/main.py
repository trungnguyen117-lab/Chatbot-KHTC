from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import os
import json
from ..common.config import *
from ..common.processors.text import build_graph_documents
from ..common.utils.helpers import load_json
from ..common.graph_builder import GraphBuilder
from ..common.llm_helper import *
from ..common.schema.text_schema import TEXT_SCHEMA, FEW_SHOT_EXAMPLES

router = APIRouter()
UPLOAD_DIRECTORY = "backend/uploaded_files"   # Directory to store uploaded files

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Endpoint for uploading a file.
    Checks if the file already exists, and returns an error message if it does.
    """
    file_path = os.path.join(UPLOAD_DIRECTORY, file.filename)
































    if os.path.exists(file_path):
        # File already exists
        return JSONResponse(
            status_code=409,  # Conflict
            content={"message": f"File '{file.filename}' already exists. Do you want to replace it?"}
        )

    # Save the file if it doesn't exist
    with open(file_path, "wb") as f:
        f.write(await file.read())

    return {"filename": file.filename, "message": "File uploaded successfully."}

@router.put("/upload/{filename}")
async def replace_file(filename: str, file: UploadFile = File(...)):
    """
    Endpoint to replace an existing file.
    """
    file_path = os.path.join(UPLOAD_DIRECTORY, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Replace the file
    with open(file_path, "wb") as f:
        f.write(await file.read())

    return {"filename": filename, "message": "File replaced successfully."}

@router.post("/upload/keep/{filename}")
async def keep_file(filename: str, file: UploadFile = File(...)):
    """
    Endpoint to save a file with a new name if the existing file exists.
    """
    base_name, ext = os.path.splitext(filename)
    new_filename = filename   # New filename, initially the old one

    counter = 1
    while os.path.exists(os.path.join(UPLOAD_DIRECTORY, new_filename)):
        # Create a new filename by adding a number to the end
        new_filename = f"{base_name}_{counter}{ext}"
        counter += 1

    file_path = os.path.join(UPLOAD_DIRECTORY, new_filename)

    # Save the file with a new name
    with open(file_path, "wb") as f:
        f.write(await file.read())

    return {"filename": new_filename, "message": "File saved with a new name successfully."}
```
Please note that this code block is similar to the previous one but it's wrapped in an APIRouter and includes additional functionality for handling file uploads using FastAPI. The main functions `process_text`, `query_knowledge`, and `chat_loop` have not been changed as they were already compatible with the FastAPI setup.
