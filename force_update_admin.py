# backend/force_update_admin.py

from app import create_app, db, bcrypt
from app.models.models import AdminUser

# --- Configuration ---
# Put the username and new password you want right here.
username_to_update = "admin"
new_password = "123"
# ---------------------

app = create_app()

with app.app_context():
    # 1. Find the user
    admin_user = db.session.query(AdminUser).filter_by(username=username_to_update).first()

    if not admin_user:
        print(f"Error: Admin user '{username_to_update}' not found in the database.")
    else:
        # 2. Generate a new hash for the new password
        new_hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        
        # 3. Update the user's password hash in the database
        admin_user.password_hash = new_hashed_password
        
        # 4. Commit the change
        try:
            db.session.commit()
            print(f"✅ Success! Password for '{username_to_update}' has been updated to '{new_password}'.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error: Could not update password in the database. {e}")