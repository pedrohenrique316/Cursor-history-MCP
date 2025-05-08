<table>
  <tr>
    <td align="center" width="150">
      <img src="https://github.com/user-attachments/assets/8a135358-41e0-4a63-9c60-7b0364c9d277" alt="Cursor Logo" width="100"/>
    </td>
    <td align="center" width="150">
      <img src="https://github.com/user-attachments/assets/df93abc6-4c62-4526-b19b-17dd627b9341" alt="MCP Logo" width="100"/>
    </td>
    <td align="center" width="150">
      <img src="https://lancedb.com/images/lancedb-logo.svg" alt="LanceDB Logo" width="100"/>
    </td>
  </tr>
</table>

# Cursor Chat History Vectorizer & Dockerized Search API

Vectorize your Cursor chat history and serve it via a simple search API.

This project provides tools to:
1.  Extract chat history from local Cursor IDE data (`state.vscdb` files within workspace storage).
2.  Generate text embeddings for user prompts using a local Ollama instance (`nomic-embed-text`).
3.  Store the extracted prompts and their embeddings in a LanceDB vector database.
4.  Include a Dockerized **FastAPI application (referred to as an "MCP server" in this context)** to search this LanceDB database via a simple API endpoint.

## ✨ Project Goal

The primary goal is to make your Cursor chat history searchable and usable for Retrieval Augmented Generation (RAG) or other LLM-based analysis by:

*   Converting user prompts into vector embeddings stored efficiently in LanceDB.
*   Providing a simple and accessible API server to perform vector similarity searches against your vectorized history.

## 🚀 Features

*   **Data Extraction:** Scans specified Cursor workspace storage paths for `state.vscdb` SQLite files.
*   **Prompt Extraction:** Extracts user prompts from the `aiService.prompts` key within the database files.
*   **Embedding Generation:** Uses a locally running Ollama instance to generate embeddings for extracted prompts.
    *   **Embedding Model:** `nomic-embed-embed-text:latest` (default dimension 768).
*   **Vector Database Storage:** Stores original text, source file, role, and vector embeddings in a LanceDB database.
    *   **LanceDB URI:** `./cursor_chat_history.lancedb` (for the extractor) / `/data/cursor_chat_history.lancedb` (inside Docker container)
    *   **Table Name:** `chat_history`
*   **Dockerized Search API:** Includes a `Dockerfile` to build a container for the FastAPI search server.
*   **FastAPI Server (`main.py`):** Acts as the "MCP server" for handling search requests.
*   **API Endpoints:**
    *   `/search_chat_history` (POST): Performs vector similarity search.
    *   `/health` (GET): Checks server status and connections (Ollama, LanceDB).

## 📋 Requirements

**For Running the Extraction Script (`cursor_history_extractor.py`):**

*   **Python 3.7+**
*   **Ollama:** Ensure Ollama is installed and running on your local machine. Pull the `nomic-embed-text` model:
    ```bash
    ollama pull nomic-embed-text:latest
    ```
*   **Python Packages:** Install required packages:
    ```bash
    pip install ollama lancedb pyarrow pandas python-dotenv
    ```
*   **File Access:** Read access to your Cursor workspace storage directory (default: `C:\Users\<name>\AppData\Roaming\Cursor\User\workspaceStorage`).

**For Running the Search API (`main.py`) via Docker:**

*   **Docker Desktop** (Windows/Mac) or **Docker Engine** (Linux).
*   An **accessible Ollama instance** from the Docker container's network.
*   The **LanceDB database directory** (`./cursor_chat_history.lancedb`) already created by the extraction script.

## ⚙️ Setup & Configuration

The process involves two main steps:

1.  **Run the extraction script** to create or update the LanceDB database on your host machine.
2.  **Build and run the Docker container** for the search API, mounting the database created in Step 1.

### Step 1: Extract & Create Database (Host Machine)

1.  **Clone/Download the Project:**
    ```bash
    git clone https://github.com/markelaugust74/Cursor-history-API.git
    cd Cursor-history-API
    ```
2.  **Install Python dependencies** for the extractor:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Verify Paths (if necessary):**
    *   Update the `WORKSPACE_STORAGE_PATH` variable in `cursor_history_extractor.py` if your Cursor data is not in the default location.
    *   Ensure you have write permissions in the directory where you run the script, as `./cursor_chat_history.lancedb` will be created here.
4.  **Ensure Ollama is Running:** Start your Ollama server and confirm `nomic-embed-text:latest` is available (`ollama list`).
5.  **Execute the extraction script:**
    ```bash
    python cursor_history_extractor.py
    ```
    This script will print progress and, if successful, create the `./cursor_chat_history.lancedb` directory containing your vectorized history.

### Step 2: Build & Run API Docker Container

1.  **Navigate** to the project directory containing the `Dockerfile`, `main.py`, and the `./cursor_chat_history.lancedb` directory created in Step 1.
2.  **Build the Docker image:**
    ```bash
    docker build -t cursor-chat-search-api .
    ```
3.  **Run the Docker container:**
    ```bash
    docker run -p 8001:8001 \
        -v /path/to/your/cursor_chat_history.lancedb:/data/cursor_chat_history.lancedb \
        -e OLLAMA_HOST="http://host.docker.internal:11434" \
        cursor-chat-search-api
    ```
    *   `-p 8001:8001`: Maps port 8001 on your host machine to port 8001 inside the container (where the FastAPI app runs).
    *   `-v /path/to/your/cursor_chat_history.lancedb:/data/cursor_chat_history.lancedb`: **This is CRUCIAL.** Replace `/path/to/your/cursor_chat_history.lancedb` with the **absolute path** on your host machine to the `cursor_chat_history.lancedb` directory created by the extraction script. This mounts your host database into the container at `/data/cursor_chat_history.lancedb`, the location expected by `main.py`. (Use forward slashes for paths even on Windows in Docker commands, or ensure proper escaping/configuration).
    *   `-e OLLAMA_HOST="..."`: Sets the `OLLAMA_HOST` environment variable inside the container. `http://host.docker.internal:11434` is common for Docker Desktop to reach the host. For Linux, you might need a different approach (e.g., host network mode, or using the host's IP accessible from the container).
4.  The FastAPI application (your "MCP server") should now be running and accessible via `http://localhost:8001`.

## ▶️ How to Run

The overall workflow is:

1.  Execute `python cursor_history_extractor.py` periodically on your host machine to create/update `./cursor_chat_history.lancedb`.
2.  Run the `docker run` command from the project root (where the `.lancedb` directory exists) to start the API server. This server will access the LanceDB database via the volume mount.

## 📁 Output

*   `./cursor_chat_history.lancedb`: A directory created by the extraction script containing the LanceDB vector database. Its schema includes `vector` (float list), `text` (string), `source_db` (string), and `role` (string).
*   A running API server inside the Docker container, accessible externally via the mapped port (default 8001), providing the defined API endpoints.

## 🔌 API Usage

Once the Docker container is running and the API is accessible (e.g., at `http://localhost:8001`), you can interact with it.

### Health Check (`GET /health`)

Checks the server's status and its connections to Ollama and LanceDB.

```bash
curl http://localhost:8001/health
```


## Example Response:
{
  "status": "healthy",
  "ollama_connection": "Connected",
  "lancedb_connection": "Connected and table open"
}



## Search History (POST /search_chat_history)
Performs a vector similarity search against the LanceDB chat history.
curl -X POST http://localhost:8001/search_chat_history \
-H "Content-Type: application/json" \
-d '{"query_text": "How do I use Python with data analysis?", "top_k": 5}'




## 🔍 Direct Database Inspection
After running the cursor_history_extractor.py script, you can inspect the LanceDB database file directly using Python (outside the Docker container).
import lancedb
import ollama # Required if you want to perform searches

# Connect to the DB where the extractor created it
db = lancedb.connect("./cursor_chat_history.lancedb")

try:
    # Open the table
    table = db.open_table("chat_history")

    # Inspect the table schema and content
    print("Table Schema:")
    print(table.schema)
    print(f"\nTotal rows: {len(table)}")
    print("\nFirst 3 rows:")
    print(table.limit(3).to_pandas())

    # --- Example: Perform a search using this direct connection ---
    # Requires Ollama running on the host where this script is executed
    # try:
    #     query_text = "How do I use Python with data analysis?"
    #     ollama_model_name = "nomic-embed-text:latest"
    #     response = ollama.embeddings(model=ollama_model_name, prompt=query_text)
    #     query_vector = response["embedding"]
    #     search_results = table.search(query_vector).limit(5).to_pandas()
    #     print("\nSearch Results (Direct Access):")
    #     print(search_results)
    # except Exception as e:
    #     print(f"Error during direct query or search (Is Ollama running?): {e}")

except Exception as e:
    print(f"Error opening or inspecting LanceDB table: {e}")

This direct access method is useful for debugging, verifying the database content, or performing operations separate from the API.
## ⚠️ Troubleshooting & Notes
Ollama Connectivity: Both the extraction script and the API server depend on a running and accessible Ollama instance with the nomic-embed-text:latest model pulled. Ensure OLLAMA_HOST is correctly configured for your Docker environment.
LanceDB Mounting: The Docker container must have the LanceDB database directory mounted correctly using the -v flag in docker run. Ensure the host path is correct and that the container user has read/write permissions if needed (write permission is mainly for the extractor, read is sufficient for the API search).
Database Path: The extractor creates the DB at ./cursor_chat_history.lancedb relative to where you run the script. The Docker container expects it mounted at /data/cursor_chat_history.lancedb. These paths are important.
Empty Prompts: The extraction script adds placeholder zero vectors for empty or whitespace-only prompts to maintain vector column size consistency.
AI Model Responses: This project currently only extracts user prompts from aiService.prompts. AI model responses and other conversation details are not currently extracted or stored.
Windows Paths: Be mindful of path formats when specifying the host path for the -v flag in docker run on Windows. Use absolute paths.
✨ Future Enhancements (Potential)
Extract and store AI model responses, associating them with user prompts.
Extract and store timestamps for ordering conversations.
Add more metadata to stored documents (workspace ID, conversation ID, etc.).
Implement configuration via a .env file for both the extractor and the API server.
Add filtering options to the search API (e.g., filter by source database, date range).
