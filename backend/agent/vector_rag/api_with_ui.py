from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Optional  # Thêm dòng này
import os
import uuid
from datetime import datetime
import logging
import uvicorn

# Import existing modules
from backend.agent.vector_rag.rag import RAGAgent
from indexing import QdrantIndexing  
from document_pre_processing import process_single_file, append_nodes_to_json

# Global objects
rag_agent = None
indexing_service = None
upload_status = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global rag_agent, indexing_service
    
    try:
        rag_agent = RAGAgent()
        indexing_service = QdrantIndexing()
        indexing_service.client_collection()
        logging.info("API started successfully")
    except Exception as e:
        logging.error(f"Startup error: {e}")
    
    yield
    
    # Shutdown
    logging.info("API shutting down")

app = FastAPI(
    title="Hybrid RAG API with UI", 
    description="RAG system with web interface",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str
    filename: Optional[str] = ""  # Sửa dòng này - thêm Optional

class QueryResponse(BaseModel):
    response: str
    processing_time: float
    sources: list = []

@app.get("/", response_class=HTMLResponse)
async def get_main_page():
    """Main page with chat interface"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Hybrid RAG Chat</title>
        
        <!-- Marked.js for markdown parsing -->
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <!-- Highlight.js for code syntax highlighting -->
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/default.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
        
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                background-color: #f7f7f8;
                height: 100vh;
                display: flex;
            }
            
            .sidebar {
                width: 300px;
                background: white;
                border-right: 1px solid #e5e5e5;
                padding: 20px;
                overflow-y: auto;
            }
            
            .main-content {
                flex: 1;
                display: flex;
                flex-direction: column;
                height: 100vh;
            }
            
            .chat-header {
                background: white;
                padding: 20px;
                border-bottom: 1px solid #e5e5e5;
                text-align: center;
            }
            
            .chat-messages {
                flex: 1;
                padding: 20px;
                overflow-y: auto;
                background: #f7f7f8;
            }
            
            .chat-input {
                background: white;
                padding: 20px;
                border-top: 1px solid #e5e5e5;
                display: flex;
                gap: 10px;
                align-items: center;
            }
            
            .message {
                margin-bottom: 20px;
                max-width: 80%;
                animation: fadeInUp 0.3s ease-out;
            }
            
            @keyframes fadeInUp {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            .message.user {
                margin-left: auto;
                background: #007bff;
                color: white;
                padding: 12px 16px;
                border-radius: 18px;
                word-wrap: break-word;
            }
            
            .message.bot {
                background: white;
                padding: 16px;
                border-radius: 12px;
                border: 1px solid #e5e5e5;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            
            /* Markdown styling for bot messages */
            .message.bot h1,
            .message.bot h2,
            .message.bot h3,
            .message.bot h4,
            .message.bot h5,
            .message.bot h6 {
                color: #333;
                margin: 16px 0 8px 0;
                font-weight: 600;
            }
            
            .message.bot h1 { font-size: 1.5em; border-bottom: 2px solid #e5e5e5; padding-bottom: 8px; }
            .message.bot h2 { font-size: 1.3em; }
            .message.bot h3 { font-size: 1.2em; }
            
            .message.bot p {
                margin: 8px 0;
                line-height: 1.6;
                color: #444;
            }
            
            .message.bot ul, .message.bot ol {
                margin: 8px 0 8px 20px;
                color: #444;
            }
            
            .message.bot li {
                margin: 4px 0;
                line-height: 1.5;
            }
            
            .message.bot blockquote {
                border-left: 4px solid #007bff;
                margin: 12px 0;
                padding: 8px 16px;
                background: #f8f9fa;
                color: #555;
                font-style: italic;
            }
            
            .message.bot code {
                background: #f1f3f4;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: 'Monaco', 'Consolas', 'Courier New', monospace;
                font-size: 0.9em;
                color: #d73a49;
            }
            
            .message.bot pre {
                background: #f6f8fa;
                border: 1px solid #e1e4e8;
                border-radius: 6px;
                padding: 16px;
                margin: 12px 0;
                overflow-x: auto;
            }
            
            .message.bot pre code {
                background: none;
                padding: 0;
                color: #24292e;
                font-size: 0.85em;
                line-height: 1.45;
            }
            
            .message.bot table {
                border-collapse: collapse;
                margin: 12px 0;
                width: 100%;
            }
            
            .message.bot th,
            .message.bot td {
                border: 1px solid #e1e4e8;
                padding: 8px 12px;
                text-align: left;
            }
            
            .message.bot th {
                background: #f6f8fa;
                font-weight: 600;
            }
            
            .message.bot a {
                color: #007bff;
                text-decoration: none;
            }
            
            .message.bot a:hover {
                text-decoration: underline;
            }
            
            .message.bot hr {
                border: none;
                border-top: 2px solid #e1e4e8;
                margin: 16px 0;
            }
            
            .message.bot strong {
                color: #333;
                font-weight: 600;
            }
            
            .message.bot em {
                color: #555;
                font-style: italic;
            }
            
            .upload-section {
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 1px solid #e5e5e5;
            }
            
            .upload-area {
                border: 2px dashed #ccc;
                border-radius: 8px;
                padding: 20px;
                text-align: center;
                background: #f9f9f9;
                margin-bottom: 15px;
                cursor: pointer;
                transition: border-color 0.3s;
            }
            
            .upload-area:hover {
                border-color: #007bff;
                background: #f0f8ff;
            }
            
            .upload-area.dragover {
                border-color: #007bff;
                background: #f0f8ff;
            }
            
            input[type="text"], input[type="file"] {
                width: 100%;
                padding: 12px;
                border: 1px solid #ddd;
                border-radius: 6px;
                font-size: 14px;
                transition: border-color 0.3s;
            }
            
            input[type="text"]:focus {
                outline: none;
                border-color: #007bff;
                box-shadow: 0 0 0 2px rgba(0,123,255,0.25);
            }
            
            button {
                background: #007bff;
                color: white;
                border: none;
                padding: 12px 20px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                transition: all 0.3s;
                font-weight: 500;
            }
            
            button:hover {
                background: #0056b3;
                transform: translateY(-1px);
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            
            button:disabled {
                background: #6c757d;
                cursor: not-allowed;
                transform: none;
                box-shadow: none;
            }
            
            .status {
                margin-top: 10px;
                padding: 10px;
                border-radius: 4px;
                font-size: 12px;
                animation: fadeIn 0.3s ease-out;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            
            .status.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .status.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .status.info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
            
            .loading {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #007bff;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            .sidebar h2 {
                margin-bottom: 15px;
                color: #333;
                font-size: 18px;
            }
            
            .sidebar h3 {
                margin-bottom: 10px;
                color: #555;
                font-size: 16px;
            }
            
            .processing-info {
                font-size: 11px;
                color: #6c757d;
                margin-top: 8px;
                font-style: italic;
            }
            
            /* Scrollbar styling */
            .chat-messages::-webkit-scrollbar {
                width: 6px;
            }
            
            .chat-messages::-webkit-scrollbar-track {
                background: #f1f1f1;
            }
            
            .chat-messages::-webkit-scrollbar-thumb {
                background: #c1c1c1;
                border-radius: 3px;
            }
            
            .chat-messages::-webkit-scrollbar-thumb:hover {
                background: #a8a8a8;
            }
        </style>
    </head>
    <body>
        <div class="sidebar">
            <div class="upload-section">
                <h2>📁 Upload Document</h2>
                
                <div class="upload-area" onclick="document.getElementById('fileInput').click()">
                    <p>📄 Click or drag files here</p>
                    <small>Supports: PDF, TXT, DOCX</small>
                </div>
                
                <input type="file" id="fileInput" accept=".pdf,.txt,.docx" style="display: none;">
                <button onclick="uploadFile()" id="uploadBtn">Upload & Process</button>
                
                <div id="uploadStatus"></div>
            </div>
            
            <div class="query-settings">
                <h3>🎯 Query Settings</h3>
                <input type="text" id="filenameInput" placeholder="Filename filter (optional)" style="margin-bottom: 10px;">
                <small>Leave empty to search all documents</small>
                
                <div class="processing-info">
                    💡 <strong>Tips:</strong><br>
                    • Use specific filenames for targeted search<br>
                    • Try questions like "summarize", "explain", "compare"<br>
                    • Responses support full Markdown formatting
                </div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="chat-header">
                <h1>🤖 Hybrid RAG Chat Assistant</h1>
                <p>Ask questions about your documents - Markdown supported!</p>
            </div>
            
            <div class="chat-messages" id="chatMessages">
                <div class="message bot">
                    <div class="bot-response">
                        <h3>👋 Welcome to Hybrid RAG Assistant!</h3>
                        
                        <p>I can help you analyze and understand your documents using advanced AI. Here's what I can do:</p>
                        
                        <ul>
                            <li><strong>📄 Document Analysis</strong> - Deep understanding of your content</li>
                            <li><strong>🔍 Smart Search</strong> - Find relevant information across documents</li>
                            <li><strong>📝 Summarization</strong> - Get concise summaries of key points</li>
                            <li><strong>❓ Q&A</strong> - Ask specific questions about your documents</li>
                        </ul>
                        
                        <blockquote>
                            <strong>Getting Started:</strong><br>
                            1. Upload documents using the sidebar<br>
                            2. Wait for processing to complete<br>
                            3. Start asking questions!
                        </blockquote>
                        
                        <p>Try questions like:</p>
                        <ul>
                            <li>"What are the main topics in this document?"</li>
                            <li>"Summarize the key findings"</li>
                            <li>"Find information about [specific topic]"</li>
                            <li>"Compare different sections"</li>
                        </ul>
                    </div>
                </div>
            </div>
            
            <div class="chat-input">
                <input type="text" id="messageInput" placeholder="Ask a question about your documents..." 
                       onkeypress="handleKeyPress(event)">
                <button onclick="sendMessage()" id="sendBtn">Send</button>
            </div>
        </div>
        
        <script>
            let currentUploadId = null;
            
            // Configure marked options
            marked.setOptions({
                highlight: function(code, lang) {
                    if (lang && hljs.getLanguage(lang)) {
                        try {
                            return hljs.highlight(code, { language: lang }).value;
                        } catch (__) {}
                    }
                    return hljs.highlightAuto(code).value;
                },
                langPrefix: 'hljs language-',
                breaks: true,
                gfm: true
            });
            
            // File upload handling
            const uploadArea = document.querySelector('.upload-area');
            const fileInput = document.getElementById('fileInput');
            
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            
            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });
            
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                fileInput.files = e.dataTransfer.files;
            });
            
            async function uploadFile() {
                const file = fileInput.files[0];
                if (!file) {
                    showStatus('Please select a file first', 'error');
                    return;
                }
                
                const formData = new FormData();
                formData.append('file', file);
                
                const uploadBtn = document.getElementById('uploadBtn');
                uploadBtn.disabled = true;
                uploadBtn.innerHTML = '<div class="loading"></div> Processing...';
                
                try {
                    const response = await fetch('/upload', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        currentUploadId = result.file_id;
                        showStatus(`File uploaded! Processing... (ID: ${result.file_id.substring(0, 8)}...)`, 'info');
                        checkUploadStatus(result.file_id);
                    } else {
                        showStatus(`Upload failed: ${result.detail}`, 'error');
                    }
                    
                } catch (error) {
                    showStatus(`Error: ${error.message}`, 'error');
                } finally {
                    uploadBtn.disabled = false;
                    uploadBtn.innerHTML = 'Upload & Process';
                }
            }
            
            async function checkUploadStatus(fileId) {
                try {
                    const response = await fetch(`/upload/${fileId}/status`);
                    const status = await response.json();
                    
                    if (status.status === 'completed') {
                        showStatus(`✅ Successfully processed <strong>${status.filename}</strong>! Indexed ${status.indexed_chunks} chunks.`, 'success');
                        fileInput.value = '';
                        
                        // Add success message to chat
                        addBotMessage(`📄 **Document Processed Successfully!**
                        
**File:** ${status.filename}
**Chunks:** ${status.indexed_chunks}
**Status:** Ready for queries

You can now ask questions about this document!`);
                        
                    } else if (status.status === 'error') {
                        showStatus(`❌ Error: ${status.error}`, 'error');
                    } else if (status.status === 'processing') {
                        showStatus(`⏳ Processing <strong>${status.filename}</strong>...`, 'info');
                        setTimeout(() => checkUploadStatus(fileId), 2000);
                    }
                } catch (error) {
                    showStatus(`Status check error: ${error.message}`, 'error');
                }
            }
            
            function showStatus(message, type) {
                const statusDiv = document.getElementById('uploadStatus');
                statusDiv.innerHTML = `<div class="status ${type}">${message}</div>`;
                
                if (type === 'success') {
                    setTimeout(() => {
                        statusDiv.innerHTML = '';
                    }, 8000);
                }
            }
            
            // Chat functionality
            async function sendMessage() {
                const messageInput = document.getElementById('messageInput');
                const query = messageInput.value.trim();
                const filename = document.getElementById('filenameInput').value.trim();
                
                if (!query) return;
                
                addMessage(query, 'user');
                messageInput.value = '';
                
                const sendBtn = document.getElementById('sendBtn');
                sendBtn.disabled = true;
                sendBtn.innerHTML = '<div class="loading"></div>';
                
                // Show typing indicator
                const typingIndicator = addTypingIndicator();
                
                try {
                    const response = await fetch('/query', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            query: query,
                            filename: filename
                        })
                    });
                    
                    const result = await response.json();
                    
                    // Remove typing indicator
                    typingIndicator.remove();
                    
                    if (response.ok) {
                        let botResponse = result.response;
                        if (result.processing_time) {
                            botResponse += `\n\n---\n*⏱️ Processed in ${result.processing_time.toFixed(2)}s*`;
                        }
                        addBotMessage(botResponse);
                    } else {
                        addBotMessage(`**Error:** ${result.detail}`);
                    }
                    
                } catch (error) {
                    typingIndicator.remove();
                    addBotMessage(`**Network Error:** ${error.message}`);
                } finally {
                    sendBtn.disabled = false;
                    sendBtn.innerHTML = 'Send';
                }
            }
            
            function addMessage(text, sender) {
                const messagesContainer = document.getElementById('chatMessages');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${sender}`;
                messageDiv.textContent = text;
                messagesContainer.appendChild(messageDiv);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
            
            function addBotMessage(markdownText) {
                const messagesContainer = document.getElementById('chatMessages');
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message bot';
                
                // Parse markdown and set HTML
                const htmlContent = marked.parse(markdownText);
                messageDiv.innerHTML = htmlContent;
                
                messagesContainer.appendChild(messageDiv);
                
                // Highlight code blocks
                messageDiv.querySelectorAll('pre code').forEach((block) => {
                    hljs.highlightElement(block);
                });
                
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
            
            function addTypingIndicator() {
                const messagesContainer = document.getElementById('chatMessages');
                const typingDiv = document.createElement('div');
                typingDiv.className = 'message bot typing-indicator';
                typingDiv.innerHTML = '<div class="loading"></div> Thinking...';
                messagesContainer.appendChild(typingDiv);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
                return typingDiv;
            }
            
            function handleKeyPress(event) {
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    sendMessage();
                }
            }
            
            // Focus on message input
            document.getElementById('messageInput').focus();
            
            // Initialize highlight.js
            hljs.highlightAll();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """Query using RAGAgent"""
    try:
        import time
        start_time = time.time()
        
        # Chỉ cần sửa đoạn này - convert empty string thành None
        filename = request.filename if request.filename and request.filename.strip() else None
            
        logging.info(f"Query: {request.query}")
        logging.info(f"Filename filter: {filename if filename else 'All documents'}")
        
        response = rag_agent.run(request.query, filename)  # Pass None khi không có filename
        processing_time = time.time() - start_time
        
        return QueryResponse(
            response=response,
            processing_time=processing_time,
            sources=[]
        )
    except Exception as e:
        logging.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload and process new file"""
    try:
        file_id = str(uuid.uuid4())
        upload_dir = "../data/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, f"{file_id}_{file.filename}")
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        upload_status[file_id] = {
            "status": "uploaded",
            "filename": file.filename,
            "created_at": datetime.now().isoformat()
        }
        
        background_tasks.add_task(process_file_background, file_id, file_path, file.filename)
        
        return {
            "file_id": file_id,
            "status": "processing",
            "message": "File uploaded successfully. Processing in background."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def process_file_background(file_id: str, file_path: str, filename: str):
    """Background processing"""
    try:
        upload_status[file_id]["status"] = "processing"
        
        metadata = {
            "file_name": filename,
            "upload_date": datetime.now().isoformat()
        }
        nodes = process_single_file(file_path, add_metadata=metadata)
        
        if nodes:
            json_file = "../data/nodes.json"
            append_nodes_to_json(nodes, json_file)
            
            documents = [node.text for node in nodes]
            metadata_list = [node.metadata for node in nodes]
            
            indexing_service.load_new_documents(documents, metadata_list)
            indexed_count = indexing_service.documents_insertion_incremental()
            
            upload_status[file_id].update({
                "status": "completed",
                "indexed_chunks": indexed_count,
                "completed_at": datetime.now().isoformat()
            })
        else:
            upload_status[file_id]["status"] = "error"
            upload_status[file_id]["error"] = "No nodes created"
        
        os.remove(file_path)
        
    except Exception as e:
        logging.error(f"Error processing file {file_id}: {e}")
        upload_status[file_id]["status"] = "error"
        upload_status[file_id]["error"] = str(e)

@app.get("/upload/{file_id}/status")
async def get_upload_status(file_id: str):
    """Check upload status"""
    if file_id not in upload_status:
        raise HTTPException(status_code=404, detail="File ID not found")
    
    return upload_status[file_id]

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API is running"}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Remove reload=True to avoid the warning
    uvicorn.run("api_with_ui:app", host="0.0.0.0", port=8000, reload=True)