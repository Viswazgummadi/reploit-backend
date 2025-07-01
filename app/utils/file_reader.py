# backend/app/utils/file_reader.py
import os
import shutil
import git
from flask import current_app
from app.models.models import db, DataSource

def read_file_from_repo(data_source_id: str, file_path: str) -> str:
    """
    Clones a repository on-demand to a temporary location, reads the content
    of a specific file, and then deletes the temporary clone.
    """
    data_source = db.session.get(DataSource, data_source_id)
    if not data_source:
        return f"Error: Data source with ID {data_source_id} not found."

    repo_full_name = data_source.connection_details.get('repo_full_name')
    if not repo_full_name:
        return "Error: Could not determine the repository name from the data source."

    # Define a temporary path for this specific on-demand clone
    temp_clone_path = os.path.join(current_app.config['REPO_CLONE_PATH'], f"temp_{data_source_id}")
    
    try:
        # Construct the clone URL
        clone_url = f"https://{current_app.config.get('GITHUB_PAT')}@github.com/{repo_full_name}.git"

        # If the folder already exists, remove it for a clean clone
        if os.path.exists(temp_clone_path):
            shutil.rmtree(temp_clone_path)
        
        current_app.logger.info(f"File Reader: Cloning '{repo_full_name}' to '{temp_clone_path}'...")
        git.Repo.clone_from(clone_url, temp_clone_path, depth=1) # depth=1 for a shallow clone, which is faster
        current_app.logger.info(f"File Reader: Cloning successful.")

        # Construct the full path to the target file
        full_file_path = os.path.join(temp_clone_path, file_path)

        if not os.path.exists(full_file_path):
            return f"Error: File '{file_path}' not found in the repository."

        # Read the file content
        with open(full_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return content

    except Exception as e:
        current_app.logger.error(f"File Reader: Error processing repo {data_source_id}: {e}", exc_info=True)
        return f"An error occurred while trying to read the file: {e}"
    finally:
        # VERY IMPORTANT: Always clean up the temporary clone
        if os.path.exists(temp_clone_path):
            shutil.rmtree(temp_clone_path)
            current_app.logger.info(f"File Reader: Cleaned up temporary clone at {temp_clone_path}")