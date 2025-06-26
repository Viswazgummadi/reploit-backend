# backend/app/routes/google_routes.py
import os
# from flask import Blueprint, request, jsonify, current_app, redirect # Original line
from flask import Blueprint, request, jsonify, current_app, redirect, session # ✅ Add `session`

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import requests # ✅ Import requests for creds.refresh(requests.Request())

from ..models import db, APIKey
from ..utils.auth import token_required, encrypt_value, decrypt_value

google_bp = Blueprint('google_routes', __name__)

SCOPES = ['https://www.googleapis.com/auth/userinfo.profile', 'https://www.googleapis.com/auth/drive.readonly']

def get_google_flow():
    """
    Helper function to create the Google OAuth Flow object
    by reading client ID and secret from app.config (environment variables).
    """
    # ✅ IMPORTANT CHANGE: Use client_config instead of from_client_secrets_file
    client_config = {
        "web": {
            "client_id": current_app.config['GOOGLE_CLIENT_ID'],
            "client_secret": current_app.config['GOOGLE_CLIENT_SECRET'],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            # Add any other fields Google requires from client_secret.json if applicable
        }
    }
    
    return Flow.from_client_config(
        client_config=client_config,
        scopes=SCOPES,
        redirect_uri=current_app.config['GOOGLE_REDIRECT_URI']
    )

@google_bp.route('/connect/google/auth-url/', methods=['GET'])
@token_required
def get_google_auth_url(current_admin_username):
    flow = get_google_flow()
    # ✅ Store state in session, crucial for callback verification
    authorization_url, state = flow.authorization_url(access_type='offline', prompt='consent')
    session['google_oauth_state'] = state # Store state in Flask session
    return jsonify({'authorization_url': authorization_url})

@google_bp.route('/connect/google/callback', methods=['GET'])
def google_callback():
    # ✅ Verify state to prevent CSRF attacks
    expected_state = session.pop('google_oauth_state', None)
    if not expected_state or expected_state != request.args.get('state'):
        current_app.logger.error("Google OAuth state mismatch or missing.")
        # Make sure the frontend redirect path is correct
        return redirect(f"{current_app.config['CORS_ORIGINS'].split(',')[0]}/admin/repos?gauth=error&reason=state_mismatch")

    try:
        flow = get_google_flow()
        flow.fetch_token(authorization_response=request.url)
    except Exception as e:
        current_app.logger.error(f"Failed to fetch Google token: {e}", exc_info=True)
        # Make sure the frontend redirect path is correct
        return redirect(f"{current_app.config['CORS_ORIGINS'].split(',')[0]}/admin/repos?gauth=error&reason=token_fetch_failed")

    credentials = flow.credentials
    
    try:
        # Check if refresh_token exists, it's only given on first authorization with access_type='offline'
        if credentials.refresh_token:
            encrypted_refresh_token = encrypt_value(credentials.refresh_token)
            refresh_token_entry = db.session.query(APIKey).filter_by(service_name='GOOGLE_REFRESH_TOKEN').first()
            if refresh_token_entry:
                refresh_token_entry.key_value_encrypted = encrypted_refresh_token
            else:
                db.session.add(APIKey(service_name='GOOGLE_REFRESH_TOKEN', key_value_encrypted=encrypted_refresh_token))
        else:
            current_app.logger.info("No new refresh token provided by Google (user already granted offline access).")
            # If no new refresh token, try to re-use an existing one if available.
            # This logic might need refinement if you rely solely on refresh token always being present.

        # Always update access token
        encrypted_access_token = encrypt_value(credentials.token)
        access_token_entry = db.session.query(APIKey).filter_by(service_name='GOOGLE_ACCESS_TOKEN').first()
        if access_token_entry:
            access_token_entry.key_value_encrypted = encrypted_access_token
        else:
            db.session.add(APIKey(service_name='GOOGLE_ACCESS_TOKEN', key_value_encrypted=encrypted_access_token))

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"DB Error saving Google tokens: {e}", exc_info=True)
        # Make sure the frontend redirect path is correct
        return redirect(f"{current_app.config['CORS_ORIGINS'].split(',')[0]}/admin/repos?gauth=dberror")

    # Make sure the frontend redirect path is correct
    return redirect(f"{current_app.config['CORS_ORIGINS'].split(',')[0]}/admin/repos?gauth=success")


@google_bp.route('/connect/google/available-files/', methods=['GET'])
@token_required
def get_available_google_files(current_admin_username):
    refresh_token_entry = db.session.query(APIKey).filter_by(service_name='GOOGLE_REFRESH_TOKEN').first()
    if not refresh_token_entry:
        return jsonify({"error": "Google Drive not authenticated. Please connect via Admin Settings."}), 401
    
    decrypted_refresh_token = decrypt_value(refresh_token_entry.key_value_encrypted)

    creds = Credentials(
        token=None,
        refresh_token=decrypted_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=current_app.config['GOOGLE_CLIENT_ID'], # Use configured client ID
        client_secret=current_app.config['GOOGLE_CLIENT_SECRET'] # Use configured client secret
    )

    try:
        # If the access token needs refreshing, this will use the refresh token
        # Ensure 'requests' library is imported at the top for requests.Request()
        creds.refresh(requests.Request()) 
        service = build('drive', 'v3', credentials=creds)
        results = service.files().list(
            q="mimeType='application/vnd.google-apps.folder'",
            pageSize=50,
            fields="nextPageToken, files(id, name, webViewLink)"
        ).execute()
        
        items = results.get('files', [])
        return jsonify(items)
    except Exception as e:
        current_app.logger.error(f"Google Drive API error: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch files from Google Drive. Please try re-authenticating."}), 500