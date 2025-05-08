import os
import sqlite3
import json
import ollama # Uncommented
import lancedb # Uncommented
import pyarrow # Added for LanceDB
# import ollama # We'll uncomment this when we integrate Ollama
# import lancedb # We'll uncomment this when we integrate LanceDB

# Configuration
WORKSPACE_STORAGE_PATH = r"C:\Users\<username>\AppData\Roaming\Cursor\User\workspaceStorage"
DB_NAME = "state.vscdb"
OLLAMA_MODEL = "nomic-embed-text:latest" # Uncommented
LANCEDB_TABLE_NAME = "chat_history" # Uncommented
LANCEDB_URI = "./cursor_chat_history.lancedb" # Added LanceDB URI
EMBEDDING_DIMENSION = 768 # Added embedding dimension for nomic-embed-text

def list_workspace_folders(base_path):
    """Lists all subdirectories in the given base_path."""
    folders = []
    if not os.path.exists(base_path):
        print(f"Error: Base path {base_path} does not exist.")
        return folders
    for item in os.listdir(base_path):
        item_path = os.path.join(base_path, item)
        if os.path.isdir(item_path):
            folders.append(item_path)
    return folders

def find_db_files(workspace_folders):
    """Finds state.vscdb files in the list of workspace folders."""
    db_files = []
    for folder in workspace_folders:
        db_path = os.path.join(folder, DB_NAME)
        if os.path.exists(db_path):
            db_files.append(db_path)
        else:
            print(f"Warning: {DB_NAME} not found in {folder}")
    return db_files

def explore_db_schema(db_path):
    """Connects to an SQLite DB and lists its tables and their schemas."""
    print(f"\nExploring schema for: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # List tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Tables found:", [table[0] for table in tables])

        # Print schema for each table
        for table_name_tuple in tables:
            table_name = table_name_tuple[0]
            print(f"\nSchema for table '{table_name}':")
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            for column in columns:
                # cid, name, type, notnull, dflt_value, pk
                print(f"  Column: {column[1]} | Type: {column[2]} | Not Null: {column[3]} | PK: {column[5]}")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"SQLite error while exploring {db_path}: {e}")

def search_json_for_keywords(json_data, keywords, path=""):
    """Recursively searches a JSON object for keywords in its keys or string values."""
    hits = []
    if isinstance(json_data, dict):
        for k, v in json_data.items():
            current_path = f"{path}.{k}" if path else k
            if any(keyword in k.lower() for keyword in keywords):
                hits.append((current_path, v))
            if isinstance(v, str) and any(keyword in v.lower() for keyword in keywords):
                hits.append((current_path, v))
            hits.extend(search_json_for_keywords(v, keywords, current_path))
    elif isinstance(json_data, list):
        for i, item in enumerate(json_data):
            current_path = f"{path}[{i}]"
            hits.extend(search_json_for_keywords(item, keywords, current_path))
    elif isinstance(json_data, str):
        if any(keyword in json_data.lower() for keyword in keywords):
            hits.append((path, json_data))
    return hits

def inspect_item_table_data(db_path):
    """Connects to SQLite DB, specifically looks for chat-related keys, and prints their JSON values."""
    print(f"\nInspecting specific chat keys in: {db_path}")
    
    target_keys = ["aiService.prompts", "workbench.panel.aichat.view.aichat.chatdata"]
    # Keywords for deeper inspection if the primary keys' structure isn't immediately obvious for chat messages
    secondary_keywords = ["chat", "conversation", "messages", "interaction", "prompt", "response", "user", "assistant", "model"]

    found_anything_at_all = False
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for target_key in target_keys:
            print(f"  Querying for key: '{target_key}'")
            cursor.execute("SELECT value FROM ItemTable WHERE key = ?", (target_key,))
            row = cursor.fetchone()

            if row:
                found_anything_at_all = True
                print(f"    Found key: '{target_key}'")
                value_data = row[0]
                text_value = None

                if isinstance(value_data, bytes):
                    try:
                        text_value = value_data.decode('utf-8')
                    except UnicodeDecodeError:
                        print(f"      Value: Could not decode BLOB as UTF-8. Length: {len(value_data)} bytes.")
                        continue # Next target_key
                elif isinstance(value_data, str):
                    text_value = value_data
                else:
                    print(f"      Value: Unexpected data type ({type(value_data)}). Value: {value_data}")
                    continue # Next target_key

                if text_value:
                    try:
                        json_object = json.loads(text_value)
                        print("      Value (JSON parsed):")
                        print(json.dumps(json_object, indent=2, ensure_ascii=False)) # ensure_ascii=False for better readability
                        
                        # Perform a quick keyword search within this specific JSON 
                        # to highlight potentially interesting parts for chat messages
                        internal_hits = search_json_for_keywords(json_object, secondary_keywords)
                        if internal_hits:
                            print(f"      --- Contains relevant keywords within its JSON structure ({len(internal_hits)} hits found):")
                            for hit_path, hit_value in internal_hits[:5]: # Print first 5 internal hits
                                print(f"        Path: {hit_path} -> Preview: {str(hit_value)[:150]}{'...' if len(str(hit_value)) > 150 else ''}")
                            if len(internal_hits) > 5:
                                print(f"        ... and {len(internal_hits) - 5} more keyword hits within this JSON.")
                        else:
                            print("      --- No secondary keywords (like 'prompt', 'response') found directly within this JSON structure during quick scan.")
                            
                    except json.JSONDecodeError:
                        print("      Value (Text, but not valid JSON):")
                        print(text_value[:1000] + "... (truncated)" if len(text_value) > 1000 else text_value)
            else:
                print(f"    Key '{target_key}' not found in this database.")
        
        conn.close()
        if not found_anything_at_all:
            print(f"  Neither '{target_keys[0]}' nor '{target_keys[1]}' found in {db_path}.")
        return found_anything_at_all

    except sqlite3.Error as e:
        print(f"SQLite error while inspecting ItemTable in {db_path}: {e}")
        return False

# --- Functions for data extraction, embedding, and storage ---
def extract_chat_data(db_path):
    """Extracts user prompts from the 'aiService.prompts' key in the DB."""
    # print(f"\nAttempting to extract chat data from: {db_path}")
    prompts = []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM ItemTable WHERE key = ?", ("aiService.prompts",))
        row = cursor.fetchone()

        if row:
            value_data = row[0]
            text_value = None
            if isinstance(value_data, bytes):
                try:
                    text_value = value_data.decode('utf-8')
                except UnicodeDecodeError:
                    print(f"Warning: Could not decode 'aiService.prompts' BLOB in {db_path}")
                    return prompts # Return empty if problematic
            elif isinstance(value_data, str):
                text_value = value_data
            
            if text_value:
                try:
                    json_data = json.loads(text_value)
                    if isinstance(json_data, list):
                        for item in json_data:
                            if isinstance(item, dict) and 'text' in item:
                                prompts.append(item['text'])
                            # else: # Potentially log unexpected structure within the list
                            #     print(f"Warning: Unexpected item structure in 'aiService.prompts' list in {db_path}: {item}")
                    # else: # Potentially log unexpected top-level structure
                    #    print(f"Warning: 'aiService.prompts' was not a list in {db_path}: {type(json_data)}")
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse 'aiService.prompts' JSON in {db_path}")
        # else: # Key not found, which is fine, just no prompts from this DB for this key
            # print(f"Key 'aiService.prompts' not found in {db_path}")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"SQLite error while extracting chat data from {db_path}: {e}")
    
    return prompts

def get_embeddings(text_data_list):
    """Generates embeddings using Ollama."""
    if not text_data_list:
        print("No text data provided to get_embeddings.")
        return []
    
    embeddings = []
    print(f"Attempting to generate embeddings for {len(text_data_list)} text items using Ollama model: {OLLAMA_MODEL}")
    for i, text in enumerate(text_data_list):
        try:
            # Ensure text is not empty or just whitespace
            if not text or not text.strip():
                print(f"Warning: Skipping empty or whitespace-only text item at index {i}.")
                # Add a placeholder or decide how to handle empty strings if they need to be stored
                embeddings.append([0.0] * EMBEDDING_DIMENSION) # Placeholder for empty/invalid text
                continue

            response = ollama.embeddings(model=OLLAMA_MODEL, prompt=text)
            embeddings.append(response["embedding"])
            if (i + 1) % 100 == 0: # Log progress every 100 embeddings
                print(f"  Generated {i+1}/{len(text_data_list)} embeddings...")
        except Exception as e:
            print(f"Error generating embedding for text item at index {i}: '{text[:100]}...'. Error: {e}")
            # Append a placeholder embedding or handle error as appropriate
            embeddings.append([0.0] * EMBEDDING_DIMENSION) # Placeholder for error
    print(f"Finished generating embeddings. Total generated: {len(embeddings)}")
    return embeddings

def store_in_lancedb(data_with_embeddings):
    """Stores data and embeddings in LanceDB."""
    if not data_with_embeddings:
        print("No data with embeddings provided to store_in_lancedb.")
        return

    print(f"Attempting to store {len(data_with_embeddings)} items in LanceDB table '{LANCEDB_TABLE_NAME}' at '{LANCEDB_URI}'.")
    
    try:
        db = lancedb.connect(LANCEDB_URI)
        
        schema = pyarrow.schema([
            pyarrow.field("vector", pyarrow.list_(pyarrow.float32(), list_size=EMBEDDING_DIMENSION)),
            pyarrow.field("text", pyarrow.string()),
            pyarrow.field("source_db", pyarrow.string()),
            pyarrow.field("role", pyarrow.string())
        ])

        table_to_use = None # Initialize

        try:
            table_to_use = db.open_table(LANCEDB_TABLE_NAME)
            print(f"Opened existing LanceDB table: '{LANCEDB_TABLE_NAME}'.")
        except Exception as e_open:
            error_msg_lower = str(e_open).lower()
            is_not_found_error = "not found" in error_msg_lower or \
                                 "does not exist" in error_msg_lower or \
                                 "no such table" in error_msg_lower or \
                                 isinstance(e_open, FileNotFoundError)

            if is_not_found_error:
                print(f"LanceDB table '{LANCEDB_TABLE_NAME}' not found (or error opening: {type(e_open).__name__}: {e_open}). Attempting to create.")
                table_to_use = db.create_table(LANCEDB_TABLE_NAME, schema=schema, mode="overwrite")
                print(f"Call to create_table for '{LANCEDB_TABLE_NAME}' completed.")
                print(f"DEBUG (post-create): Type of table_to_use: {type(table_to_use)}")
                print(f"DEBUG (post-create): Value of table_to_use: {table_to_use}")
            else:
                print(f"Unexpected error opening table '{LANCEDB_TABLE_NAME}': {type(e_open).__name__}: {e_open}")
                raise

        print(f"DEBUG (pre-check): Type of table_to_use: {type(table_to_use)}")
        print(f"DEBUG (pre-check): Value of table_to_use: {table_to_use}")

        # Explicitly check if table_to_use is an instance of LanceTable
        if isinstance(table_to_use, lancedb.table.LanceTable):
            print(f"Proceeding to add data to table (verified type): {table_to_use}")
            table_to_use.add(data_with_embeddings)
            print(f"Successfully added {len(data_with_embeddings)} items to LanceDB table '{LANCEDB_TABLE_NAME}'.")
            print(f"LanceDB table info: {table_to_use}")
        else:
            print(f"CRITICAL ERROR: table_to_use is not a valid LanceTable object after open/create attempts. Type was: {type(table_to_use)}. Data not added.")

    except Exception as e:
        print(f"Error during LanceDB operations: {type(e).__name__}: {e}")
        print("Make sure you have run 'pip install lancedb pyarrow' and have write permissions to the path.")


def main():
    print("Starting Cursor history extraction process...")
    workspace_folders = list_workspace_folders(WORKSPACE_STORAGE_PATH)
    if not workspace_folders:
        print("No workspace folders found. Exiting.")
        return

    print(f"Found {len(workspace_folders)} workspace folders.")
    
    db_files = find_db_files(workspace_folders)
    if not db_files:
        print(f"No {DB_NAME} files found. Exiting.")
        return

    print(f"Found {len(db_files)} database files.")

    # For now, let's explore the schema of the first DB file found
    # to understand its structure.
    if db_files:
        explore_db_schema(db_files[0]) # Keep exploring schema of the first one for reference
        
        inspected_count = 0
        found_any_chat_data = False
        for i, db_file_to_inspect in enumerate(db_files):
            print(f"\n--- Inspecting DB {i+1}/{len(db_files)}: {db_file_to_inspect} ---")
            if inspect_item_table_data(db_file_to_inspect):
                found_any_chat_data = True
            
        if not found_any_chat_data:
            print("\nNo potential chat-related data found in ANY of the inspected DB files using target keys.")
        else:
            print("\nPotential chat-related data found. Please review the output above.")

    # --- Full pipeline (to be enabled later) ---
    all_extracted_prompts = []
    print("\nStarting data extraction from all database files...")
    for i, db_file in enumerate(db_files):
        # print(f"Processing DB {i+1}/{len(db_files)}: {db_file}") # Can be verbose
        prompts_from_db = extract_chat_data(db_file)
        if prompts_from_db:
            all_extracted_prompts.extend([{"text": p, "source_db": os.path.basename(db_file), "role": "user"} for p in prompts_from_db])
    
    if not all_extracted_prompts:
        print("No prompts found in any database under 'aiService.prompts'.")
        return

    print(f"\nExtracted a total of {len(all_extracted_prompts)} user prompts.")
    print("First 3 extracted prompts (for verification):")
    for i, p_data in enumerate(all_extracted_prompts[:3]):
        print(f"  {i+1}. From {p_data['source_db']}: {p_data['text'][:100]}...")

    # --- Embedding and LanceDB storage ---
    print("\nPreparing to generate embeddings...")
    texts_to_embed = [item['text'] for item in all_extracted_prompts]
    
    if not texts_to_embed:
        print("No texts extracted to embed. Exiting.")
        return

    embeddings = get_embeddings(texts_to_embed) 
    
    if not embeddings or len(embeddings) != len(all_extracted_prompts):
        print("Error generating embeddings or mismatch in count. Cannot proceed to LanceDB.")
        # Further inspect why embeddings might be empty if texts_to_embed was not
        if not embeddings and texts_to_embed:
            print("  get_embeddings returned an empty list even though there were texts to embed.")
        elif len(embeddings) != len(all_extracted_prompts):
            print(f"  Mismatch: {len(texts_to_embed)} texts, {len(embeddings)} embeddings.")
        return

    print(f"Successfully generated {len(embeddings)} embeddings.")

    data_for_lancedb = []
    for i, prompt_data in enumerate(all_extracted_prompts):
        if i < len(embeddings): # Ensure we have an embedding for this prompt
            data_for_lancedb.append({
                "vector": embeddings[i],
                "text": prompt_data['text'],
                "source_db": prompt_data['source_db'],
                "role": prompt_data['role']
            })
        else:
            print(f"Warning: Missing embedding for prompt data at index {i}. Skipping this item for LanceDB.")
    
    if not data_for_lancedb:
        print("No data prepared for LanceDB. This might be due to embedding errors or mismatches.")
        return

    print(f"Storing {len(data_for_lancedb)} items in LanceDB...")
    store_in_lancedb(data_for_lancedb)
    print(f"Successfully processed and attempted to store data from {len(db_files)} database files.")

    print("Process finished.")

if __name__ == "__main__":
    main() 