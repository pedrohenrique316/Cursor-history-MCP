# Cursor Chat History Extractor & Vectorizer

This project extracts chat history from local Cursor IDE an C:\Users\<name>\AppData\Roaming\Cursor\User\workspaceStorage, generates text embeddings for user prompts using a local Ollama instance with the `nomic-embed-text` model, and stores these prompts along with their embeddings in a LanceDB vector database.

## Project Goal

The primary goal is to make your Cursor chat history searchable and usable for Retrieval Augmented Generation (RAG) or other LLM-based analysis by converting user prompts into vector embeddings.

## Features

- Scans specified Cursor workspace storage paths for `state.vscdb` SQLite files.
- Extracts user prompts from the `aiService.prompts` key within these database files.
- Uses a locally running Ollama instance to generate embeddings for the extracted prompts.
  - **Embedding Model:** `nomic-embed-text:latest` (default dimension 768).
- Stores the original prompt text, source database file, user role, and the generated vector embedding in a LanceDB database.
  - **LanceDB URI:** `./cursor_chat_history.lancedb`
  - **Table Name:** `chat_history`

## Requirements

1.  **Python 3.7+**
2.  **Ollama:**
    - Ensure Ollama is installed and running.
    - Pull the `nomic-embed-text` model: `ollama pull nomic-embed-text:latest`
3.  **Python Packages:**
    ```bash
    pip install ollama lancedb pyarrow
    ```
    (Note: `sqlite3` and `json` are part of the Python standard library.)

## Setup & Configuration

1.  **Clone/Download the Project:**
    - git clone https://github.com/markelaugust74/Cursor-history-API.git
2.  **Verify Paths (if necessary):**
    - The script is hardcoded to look for Cursor data in `C:\\Users\\<name>\\AppData\\Roaming\\Cursor\\User\\workspaceStorage`. If your path is different, you'll need to update the `WORKSPACE_STORAGE_PATH` variable at the top of the `cursor_history_extractor.py` script.
3.  **Ensure Ollama is Running:**
    - Start your Ollama application/server.
    - Verify the `nomic-embed-text:latest` model is available (e.g., run `ollama list` in your terminal).

## How to Run

1.  Navigate to the directory containing `cursor_history_extractor.py` in your terminal.
2.  Execute the script:
    ```bash
    python cursor_history_extractor.py
    ```
3.  The script will output its progress to the console, including:
    - Workspace folders found.
    - Database files found.
    - Schema exploration of the first database.
    - Inspection of target keys in each database.
    - Number of prompts extracted.
    - Progress of embedding generation.
    - Status of LanceDB storage.

## Output

-   **`./cursor_chat_history.lancedb`**: A directory created in the same location where the script is run. This is the LanceDB vector database containing the `chat_history` table.
    The table schema includes:
    - `vector`: The 768-dimension embedding (list of floats).
    - `text`: The original user prompt text (string).
    - `source_db`: The name of the `state.vscdb` file from which the prompt was extracted (string).
    - `role`: Currently hardcoded to "user" (string).

## Using the LanceDB Database

Once the script has run successfully, you can interact with the LanceDB database in other Python scripts:

```python
import lancedb
import ollama # For generating query embeddings

# Connect to the DB and open the table
db = lancedb.connect("./cursor_chat_history.lancedb")
table = db.open_table("chat_history")

# Example: Perform a similarity search
query_text = "How do I use Python with data analysis?"

# Generate embedding for the query using the SAME model
ollama_model_name = "nomic-embed-text:latest" # Make sure this matches
try:
    response = ollama.embeddings(model=ollama_model_name, prompt=query_text)
    query_vector = response["embedding"]

    # Search the table
    search_results = table.search(query_vector).limit(5).to_pandas()
    print("Search Results:")
    print(search_results)

except Exception as e:
    print(f"Error during query or search: {e}")

# You can also inspect the table
# print(table.schema)
# print(f"Total rows: {len(table)}")
# print(table.limit(3).to_pandas())
```

## Troubleshooting & Notes

-   **Ollama Not Running:** If Ollama isn't running or the model isn't available, the embedding step will fail.
-   **LanceDB Errors:**
    - Ensure you have write permissions in the directory where the script is run, as `./cursor_chat_history.lancedb` will be created there.
    - If you encounter persistent LanceDB errors, deleting the `./cursor_chat_history.lancedb` directory and re-running the script can sometimes help.
-   **Empty Prompts:** The script identifies and skips empty or whitespace-only prompts, adding placeholder zero vectors for them. This is noted in the console output.
-   **AI Model Responses:** This script currently only extracts *user prompts*. The mechanism for reliably extracting corresponding AI model responses from the `state.vscdb` files has not been identified yet.

## Future Enhancements (Potential)

-   Identify and extract AI model responses.
-   Extract timestamps for conversation ordering.
-   Add more metadata to the stored documents (e.g., workspace ID).
-   Allow configuration of paths and model names via command-line arguments or a .env file.


---

This README provides a guide to understanding, setting up, and running the Cursor chat history extractor. 
