# backend/force_update_admin.py

from app import create_app, db, bcrypt
from app.models.models import AdminUser

# --- Configuration ---
# Put the username and new password you want right here.
username_to_manage = "admin"
password_to_set = "123" # This will be the initial or updated password
# ---------------------

app = create_app()

with app.app_context():
    # 1. Try to find the user
    admin_user = db.session.query(AdminUser).filter_by(username=username_to_manage).first()

    if not admin_user:
        # User not found, so create a new one
        print(f"Info: Admin user '{username_to_manage}' not found. Creating a new user...")
        admin_user = AdminUser(username=username_to_manage, is_admin=True)
        db.session.add(admin_user) # Add the new user to the session

    # Set or update the password for the found/new user
    admin_user.set_password(password_to_set)
    
    # 3. Commit the change
    try:
        db.session.commit()
        print(f"✅ Success! Admin user '{username_to_manage}' created/updated with password '{password_to_set}'.")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error: Could not create/update admin user in the database. {e}")