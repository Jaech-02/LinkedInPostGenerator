"""
LinkedIn Auth - Simple Python Script
=====================================
Saves credentials and begins the LinkedIn OAuth authentication flow.

Prerequisites:
1. Create a LinkedIn Developer App at https://developer.linkedin.com/
2. Add products: "Share on LinkedIn" and "Sign In with LinkedIn using OpenID Connect"
3. Set redirect URL to: http://localhost:8000/callback
4. Get your Client ID and Client Secret from the app settings

Author: Jasi
"""

import os
import requests
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
from dotenv import load_dotenv

load_dotenv()

# ============== CONFIGURATION ==============
# Replace these with your LinkedIn App credentials
CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/callback"

# Scopes needed for posting
SCOPES = "openid profile w_member_social"

# File to store tokens
TOKEN_FILE = "linkedin_tokens.json"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler to capture OAuth callback"""

    def do_GET(self):
        """Handle the OAuth callback"""
        parsed = urlparse(self.path)

        if parsed.path == "/callback":
            query_params = parse_qs(parsed.query)

            if "code" in query_params:
                self.server.auth_code = query_params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                    <html>
                    <body style="font-family: Arial; text-align: center; padding: 50px;">
                        <h1>Authorization Successful!</h1>
                        <p>You can close this window and return to the terminal.</p>
                    </body>
                    </html>
                """)
            else:
                error = query_params.get("error", ["Unknown error"])[0]
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"<html><body><h1>Error: {error}</h1></body></html>".encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress server logs"""
        pass


def save_tokens(tokens: dict):
    """Save tokens to file"""
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    print(f"✅ Tokens saved to {TOKEN_FILE}")


def load_tokens() -> dict | None:
    """Load tokens from file"""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return None


def get_authorization_url() -> str:
    """Generate LinkedIn OAuth authorization URL"""
    auth_url = (
        f"https://www.linkedin.com/oauth/v2/authorization?"
        f"response_type=code&"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"scope={SCOPES}&"
        f"state=linkedin_post_state"
    )
    return auth_url


def get_authorization_code() -> str:
    """Open browser for authorization and capture the code"""
    print("\n🔐 Starting LinkedIn Authorization...")
    print("=" * 50)

    auth_url = get_authorization_url()
    print(f"\n📎 Opening browser for authorization...")
    print(f"   If browser doesn't open, visit this URL:\n   {auth_url}\n")

    # Open browser
    webbrowser.open(auth_url)

    # Start local server to capture callback
    server = HTTPServer(("localhost", 8000), OAuthCallbackHandler)
    server.auth_code = None

    print("⏳ Waiting for authorization callback...")

    # Wait for callback
    while server.auth_code is None:
        server.handle_request()

    print("✅ Authorization code received!")
    return server.auth_code


def exchange_code_for_token(auth_code: str) -> dict:
    """Exchange authorization code for access token"""
    print("\n🔄 Exchanging code for access token...")

    token_url = "https://www.linkedin.com/oauth/v2/accessToken"

    payload = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    response = requests.post(token_url, data=payload, headers=headers)

    if response.status_code == 200:
        tokens = response.json()
        print("✅ Access token obtained!")
        print(f"   Token expires in: {tokens.get('expires_in', 'N/A')} seconds")
        return tokens
    else:
        print(f"❌ Error getting token: {response.status_code}")
        print(f"   Response: {response.text}")
        raise Exception("Failed to get access token")


def get_user_info(access_token: str) -> dict:
    """Get user info including the person URN"""
    print("\n👤 Fetching user info...")

    url = "https://api.linkedin.com/v2/userinfo"

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        user_info = response.json()
        print(f"✅ Logged in as: {user_info.get('name', 'Unknown')}")
        return user_info
    else:
        print(f"❌ Error getting user info: {response.status_code}")
        print(f"   Response: {response.text}")
        raise Exception("Failed to get user info")


def authenticate() -> tuple[str, str]:
    """Complete authentication flow and return access_token and person_urn"""

    # Check for existing tokens
    tokens = load_tokens()

    if tokens and "access_token" in tokens:
        print("📂 Found existing tokens, attempting to use them...")
        access_token = tokens["access_token"]

        # Verify token is still valid by getting user info
        try:
            user_info = get_user_info(access_token)
            person_urn = f"urn:li:person:{user_info['sub']}"
            return access_token, person_urn
        except Exception:
            print("⚠️ Existing token expired, re-authenticating...")

    # Start fresh authentication
    auth_code = get_authorization_code()
    tokens = exchange_code_for_token(auth_code)
    save_tokens(tokens)

    access_token = tokens["access_token"]
    user_info = get_user_info(access_token)
    person_urn = f"urn:li:person:{user_info['sub']}"

    # Save person_urn to tokens file for future use
    tokens["person_urn"] = person_urn
    tokens["user_name"] = user_info.get("name", "Unknown")
    save_tokens(tokens)

    return access_token, person_urn


if __name__ == "__main__":
    # Check if credentials are set
    if not CLIENT_ID or not CLIENT_SECRET:
        print("\n❌ ERROR: LinkedIn credentials not found!")
        print("\nAsegurate de tener un archivo .env con:")
        print("   LINKEDIN_CLIENT_ID=tu_client_id")
        print("   LINKEDIN_CLIENT_SECRET=tu_client_secret")
        print("\nO configura las variables de entorno:")
        print("   $env:LINKEDIN_CLIENT_ID='tu_client_id'")
        print("   $env:LINKEDIN_CLIENT_SECRET='tu_client_secret'")
    else:
        print("\n" + "=" * 60)
        print("🔵 LinkedIn Auth Flow")
        print("=" * 60)
        print(f"\n📋 Redirect URI configurado: {REDIRECT_URI}")
        print("\n⚠️ IMPORTANTE: Asegurate de que esta URL exacta este registrada")
        print("   en tu aplicacion de LinkedIn Developers:")
        print("   1. Ve a https://developer.linkedin.com/")
        print("   2. Abre tu aplicacion")
        print("   3. Ve a la pestaña 'Auth'")
        print(f"   4. En 'Redirect URLs' debe estar: {REDIRECT_URI}")
        print("   5. Si no esta, agregala y guarda los cambios\n")
        print("=" * 60)
        access_token, person_urn = authenticate()
        print("\n" + "=" * 60)
        print("🎉 Authentication complete! Tokens saved.")
        print("=" * 60)
