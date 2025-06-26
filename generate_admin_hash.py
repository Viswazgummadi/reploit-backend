# backend/generate_admin_hash.py
from flask_bcrypt import Bcrypt

# You don't need a Flask app instance to just use Bcrypt's hashing
bcrypt_standalone = Bcrypt()

# The password you want to hash (from your .env or just type it here for this one-time script)
admin_password_to_hash = "supersecretpassword"

# Generate the hash
# Bcrypt stores the salt within the hash string itself
hashed_password = bcrypt_standalone.generate_password_hash(admin_password_to_hash).decode('utf-8')

print(f"Original Password: {admin_password_to_hash}")
print(f"Hashed Password: {hashed_password}")
print("\nCopy the Hashed Password (starting with $2b$) and put it in your .env file as ADMIN_PASSWORD_HASH_ENV")