from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from api import auth, chat
from database import engine
from models import Base
from config import settings
import logging
from agent.graph_rag.graph_knowledge.main import process_docling
# Create database tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global rag_agent, indexing_service
    process_docling() 
    logging.info("Graph docs done")
    try:
        await chat.initialize_rag()
        logging.info("API started successfully")
    except Exception as e:
        logging.error(f"Startup error: {e}")
    
    yield
    
    # Shutdown
    logging.info("API shutting down")
# from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv

from api.dashboard_api import router as dashboard_router
from api.procedure_details import router as procedure_details_router 

# Create FastAPI app
app = FastAPI(
    title="Fin Agent API",
    description="Financial Agent Backend API",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(dashboard_router)             # /dashboard/procedures
app.include_router(procedure_details_router)  # /procedure-details/{procedure_id}

@app.get("/")
async def root():
    return {"message": "Fin Agent API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=settings.debug
    )
