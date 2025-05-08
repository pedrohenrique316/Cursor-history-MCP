from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import lancedb
import ollama
import os
from dotenv import load_dotenv

# Load environment variables from .env file at the start
load_dotenv()

# --- Configuration ---
# LanceDB Configuration - Path inside the container where the DB will be mounted
LANCEDB_URI = os.getenv("LANCEDB_URI", "/data/cursor_chat_history.lancedb")
LANCEDB_TABLE_NAME = "chat_history"

# Ollama Configuration
OLLAMA_EMBED_MODEL = "nomic-embed-text:latest"
# For Docker Desktop (Windows/Mac), host.docker.internal usually works for host services.
# For Linux, you might need to use the host's actual IP accessible from Docker, 
# or set up a user-defined Docker network if Ollama is also in Docker.
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Cursor Chat History Search API",
    description="An API to search vectorized Cursor chat history stored in LanceDB.",
    version="0.1.0",
)

# --- CORS Middleware Configuration ---
# This allows requests from any origin. For production, you might want to restrict this.
# For example, if Open WebUI is served from http://localhost:3000, you'd use:
# origins = ["http://localhost:3000"]
origins = ["*"]  # Allows all origins for now, for simplicity

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, # Allows cookies if you were to use them
    allow_methods=["GET", "POST", "OPTIONS"], # Allow OPTIONS method for preflight
    allow_headers=["*"]  # Allow all headers
)

# --- Pydantic Models for Request/Response Typing ---
class SearchQuery(BaseModel):
    query_text: str
    top_k: int = 15

class SearchResultItem(BaseModel):
    text: str
    source_db: str
    # score: float # LanceDB search results include a _score field

class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    message: str = "Success"

# --- Global Variables for Clients (managed by startup/shutdown events) ---
db_connection = None
chat_table = None
ollama_client = None

# --- FastAPI Startup Event --- 
@app.on_event("startup")
async def startup_event():
    global db_connection, chat_table, ollama_client
    
    # Initialize Ollama Client
    try:
        print(f"Attempting to initialize Ollama client with host: {OLLAMA_HOST}")
        ollama_client = ollama.Client(host=OLLAMA_HOST)
        ollama_client.list()  # Test connection by listing models
        print(f"Successfully connected to Ollama at {OLLAMA_HOST}")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to connect to Ollama on startup at {OLLAMA_HOST}. Error: {e}")
        ollama_client = None # Ensure client is None if connection failed

    # Initialize LanceDB Connection
    # Check if the LanceDB directory exists before attempting to connect
    if not os.path.exists(LANCEDB_URI) or not os.path.isdir(LANCEDB_URI):
        print(f"CRITICAL ERROR: LanceDB database directory not found at {LANCEDB_URI}. Please ensure it's correctly mounted or the path is valid.")
        # db_connection and chat_table will remain None
        return
    
    try:
        print(f"Attempting to connect to LanceDB at: {LANCEDB_URI}")
        db_connection = lancedb.connect(LANCEDB_URI)
        chat_table = db_connection.open_table(LANCEDB_TABLE_NAME)
        print(f"Successfully connected to LanceDB and opened table: '{LANCEDB_TABLE_NAME}'")
        print(f"LanceDB table schema: {chat_table.schema}")
        print(f"Number of rows in table: {len(chat_table)}")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to connect to LanceDB or open table '{LANCEDB_TABLE_NAME}' on startup. Error: {e}")
        db_connection = None # Ensure these are None if setup fails
        chat_table = None

# --- API Endpoints ---
@app.post("/search_chat_history", response_model=SearchResponse)
async def search_chat_history_endpoint(query: SearchQuery):
    global ollama_client, chat_table

    if ollama_client is None:
        raise HTTPException(status_code=503, detail="Ollama client not available. Check server logs.")
    if chat_table is None:
        raise HTTPException(status_code=503, detail="LanceDB table not available. Check server logs and DB path.")

    try:
        # 1. Generate embedding for the query
        print(f"Generating embedding for query: '{query.query_text[:50]}...'")
        response = ollama_client.embeddings(model=OLLAMA_EMBED_MODEL, prompt=query.query_text)
        query_vector = response["embedding"]
        print(f"Embedding generated successfully.")

        # 2. Search LanceDB
        print(f"Searching LanceDB table '{LANCEDB_TABLE_NAME}' for top {query.top_k} results.")
        search_results_df = chat_table.search(query_vector).limit(query.top_k).to_pandas()
        print(f"Found {len(search_results_df)} results from LanceDB.")
        
        # 3. Format results
        formatted_results = []
        for _, row in search_results_df.iterrows():
            # Assuming your table has 'text' and 'source_db' columns from the previous script
            formatted_results.append(
                SearchResultItem(text=row.get('text', ''), source_db=row.get('source_db', ''))
            )
        
        return SearchResponse(results=formatted_results)

    except ollama.ResponseError as e_ollama:
        print(f"Ollama API Error during search: {e_ollama}")
        raise HTTPException(status_code=500, detail=f"Ollama API Error: {e_ollama.error} (status code: {e_ollama.status_code})")
    except Exception as e:
        print(f"General Error during search: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/health")
async def health_check():
    # Basic health check to see if the server is running
    ollama_status = "Connected" if ollama_client else "Error (Not Connected)"
    lancedb_status = "Connected and table open" if chat_table else "Error (Not Connected or table not open)"
    return {
        "status": "healthy", 
        "ollama_connection": ollama_status, 
        "lancedb_connection": lancedb_status
    }

# To run this application (after saving as main.py):
# 1. Ensure Ollama is running and accessible.
# 2. Ensure your cursor_chat_history.lancedb directory is correctly placed for Docker volume mounting.
# 3. Build the Docker image: docker build -t cursor-chat-search-api .
# 4. Run the Docker container: 
#    docker run -p 8001:8001 -v /path/to/your/db_data/cursor_chat_history.lancedb:/data/cursor_chat_history.lancedb cursor-chat-search-api
#    (Adjust the volume path -v as needed) 