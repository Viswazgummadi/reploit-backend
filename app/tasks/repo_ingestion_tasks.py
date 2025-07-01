# backend/app/tasks/repo_ingestion_tasks.py
import os
import shutil
import git
from datetime import datetime
from flask import current_app
from .. import celery_app
from ..models.models import db, DataSource
from ..knowledge_graph.kg_manager import KnowledgeGraphManager
from ..code_parser.python_parser import parse_python_file
from ..vector_db.vector_store_manager import VectorStoreManager

@celery_app.task(bind=True)
def process_data_source_for_ai(self, data_source_id: str):
    current_app.logger.info(f"🚀 Task {self.request.id}: Starting processing for data source: {data_source_id}")
    data_source = db.session.get(DataSource, data_source_id)
    if not data_source:
        current_app.logger.error(f"Task failed: Data source {data_source_id} not found.")
        return {"status": "failed", "message": "Data source not found"}

    kg_manager = None
    vector_store_manager = None
    local_repo_path = os.path.join(current_app.config['REPO_CLONE_PATH'], data_source_id)

    try:
        # --- 1. Setup Phase ---
        kg_manager = KnowledgeGraphManager()
        vector_store_manager = VectorStoreManager()
        current_app.logger.info(f"Clearing any existing data for data source {data_source_id}...")
        kg_manager.clear_data_source_data(data_source_id)
        vector_store_manager.clear_data_source_data(data_source_id)
        current_app.logger.info(f"✅ Data cleared.")

        # --- 2. Code Fetching Phase ---
        repo_full_name = data_source.connection_details.get('repo_full_name')
        if not repo_full_name:
            raise ValueError("GitHub repo_full_name not found in connection_details.")
        clone_url = f"https://{current_app.config.get('GITHUB_PAT')}@github.com/{repo_full_name}.git"
        if os.path.exists(local_repo_path):
            shutil.rmtree(local_repo_path)
        current_app.logger.info(f"Cloning '{repo_full_name}'...")
        git.Repo.clone_from(clone_url, local_repo_path)
        current_app.logger.info(f"✅ Cloning successful.")
        
        # --- 3. Parsing & Data Preparation Phase ---
        current_app.logger.info(f"Starting code parsing...")
        all_functions_data = []
        for root, _, files in os.walk(local_repo_path):
            if any(d in root.split(os.sep) for d in ['.git', '__pycache__', 'node_modules', 'venv']):
                continue
            for file_name in files:
                if file_name.endswith('.py'):
                    file_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(file_path, local_repo_path)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            parsed_data = parse_python_file(content)
                            if parsed_data and parsed_data.get("functions"):
                                for func_data in parsed_data["functions"]:
                                    func_data["file_path"] = relative_path
                                    all_functions_data.append(func_data)
                    except Exception as parse_error:
                        current_app.logger.warning(f"Could not read or parse file {relative_path}: {parse_error}")
        current_app.logger.info(f"✅ Finished parsing. Found {len(all_functions_data)} total functions.")

        # --- 4. AI Docstring Generation Phase ---
        functions_with_docstrings = [f for f in all_functions_data if f.get("docstring")]
        functions_without_docstrings = [f for f in all_functions_data if not f.get("docstring")]
        
        if current_app.config.get('ENABLE_AI_DOCSTRING_GENERATION') and functions_without_docstrings:
            current_app.logger.info(f"Found {len(functions_without_docstrings)} functions without docstrings. Generating with AI...")
            generated_docs = vector_store_manager.generate_docstrings_in_batch(functions_without_docstrings)
            for i, func in enumerate(functions_without_docstrings):
                func["docstring"] = generated_docs[i]
        
        final_functions_list = functions_with_docstrings + functions_without_docstrings

        # --- 5. KG & Vector DB Population Phase ---
        current_app.logger.info(f"Starting KG population and embedding data preparation...")
        text_chunks_for_embedding = []
        metadatas_for_embedding = []
        for func_data in final_functions_list:
            kg_manager.add_file_node(data_source_id, func_data["file_path"])
            kg_manager.add_function_node(data_source_id, func_data["file_path"], func_data["name"])
            
            text_chunk = (
                f"Function: {func_data['name']}\n"
                f"File: {func_data['file_path']}\n"
                f"Arguments: {', '.join(func_data['args']) if func_data['args'] else 'None'}\n"
                f"Documentation:\n{func_data['docstring']}"
            )
            text_chunks_for_embedding.append(text_chunk)
            metadatas_for_embedding.append({"file_path": func_data["file_path"], "function_name": func_data["name"]})
        
        if text_chunks_for_embedding:
            vector_store_manager.generate_and_store_embeddings(
                text_chunks=text_chunks_for_embedding,
                metadatas=metadatas_for_embedding,
                data_source_id=data_source_id
            )

        # --- 6. Finalize and Update Status ---
        data_source.status = 'indexed'
        data_source.last_indexed_at = datetime.utcnow()
        db.session.add(data_source)
        db.session.commit()
        current_app.logger.info(f"✅ Set data source {data_source_id} status to 'indexed'.")
        return {"status": "completed", "message": f"Data source {data_source.name} processed successfully."}

    except Exception as e:
        current_app.logger.error(f"❌ Task failed for data source {data_source_id}: {e}", exc_info=True)
        data_source_to_fail = db.session.get(DataSource, data_source_id)
        if data_source_to_fail:
            data_source_to_fail.status = 'failed'
            db.session.add(data_source_to_fail)
            db.session.commit()
        raise e
    finally:
        if kg_manager:
            kg_manager.close()
        if os.path.exists(local_repo_path):
            shutil.rmtree(local_repo_path)
            current_app.logger.info(f"Cleaned up cloned repo at {local_repo_path}")