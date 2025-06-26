# backend/run.py
from dotenv import load_dotenv # ✅ 1. IMPORT load_dotenv
load_dotenv() # ✅ 2. LOAD .ENV FILE AT THE VERY TOP

from app import create_app, db, bcrypt 
from app.models.models import AdminUser
import os

app = create_app() # This line is what Gunicorn will import and run for production

# --- Flask CLI Commands (these are fine to keep, they won't run automatically on server start) ---
@app.cli.command("create-admin")
def create_admin_command():
    """Creates or updates the admin user based on .env configuration."""
    
    default_username = app.config.get('INITIAL_ADMIN_USERNAME')
    default_password = app.config.get('INITIAL_ADMIN_PASSWORD')

    if not default_username or not default_password:
        print("Error: Set INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD in your .env file or config.")
        return

    with app.app_context(): 
        admin_user = db.session.query(AdminUser).filter_by(username=default_username).first()
        hashed_password = bcrypt.generate_password_hash(default_password).decode('utf-8')
        
        if admin_user:
            admin_user.password_hash = hashed_password
            action_message = f"Admin user '{default_username}' password updated."
        else:
            admin_user = AdminUser(username=default_username, password_hash=hashed_password)
            db.session.add(admin_user)
            action_message = f"Admin user '{default_username}' created."
        try:
            db.session.commit()
            print(action_message)
            if "created" in action_message:
                print(f"IMPORTANT: Initial password for '{default_username}' is '{default_password}'.")
        except Exception as e:
            db.session.rollback()
            print(f"Error during create-admin: {e}")

# The `if __name__ == '__main__':` block is removed/commented out for production deployment.
# Gunicorn will import `app` directly from this file.