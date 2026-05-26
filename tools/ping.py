import requests
import urllib.parse
import secrets
import json
import os

# Configuration
CLIENT_ID = os.environ.get("PING_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PING_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:5000/callback"
OIDC_CONFIG_URL = os.environ.get("PING_CONFIG_URL", "https://identity.dev.amsc.ornl.gov/am/oauth2/.well-known/openid-configuration")
SCOPES = "openid profile email address phone"

# Fetch OIDC configuration
print("Fetching OIDC configuration...")
config_response = requests.get(OIDC_CONFIG_URL)
config = config_response.json()

# print("\n=== OIDC Configuration ===")
# print(json.dumps(config, indent=2))

authorization_endpoint = config["authorization_endpoint"]
token_endpoint = config["token_endpoint"]
userinfo_endpoint = config.get("userinfo_endpoint")
introspection_endpoint = config.get("introspection_endpoint")

# Generate state and PKCE parameters for security
state = secrets.token_urlsafe(32)

# Build authorization URL
auth_params = {
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "response_type": "code",
    "scope": SCOPES,
    "state": state,
}

authorize_url = f"{authorization_endpoint}?{urllib.parse.urlencode(auth_params)}"
print(f"\n=== Authorization ===")
print(f"Visit this URL in your browser:\n{authorize_url}\n")

# After visiting the URL and authorizing, you'll be redirected to a URL with a code parameter
auth_code = input("Paste the 'code' parameter from the redirect URL: ")

# Exchange the code for tokens
print("\nExchanging authorization code for tokens...")
token_data = {
    "grant_type": "authorization_code",
    "code": auth_code,
    "redirect_uri": REDIRECT_URI,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
}

token_response = requests.post(token_endpoint, data=token_data)

if token_response.status_code == 200:
    tokens = token_response.json()

    print("\n=== TOKEN RESPONSE ===")
    print(json.dumps(tokens, indent=2))

    # Decode and print ID token claims if present
    if "id_token" in tokens:
        print("\n=== ID TOKEN ===")
        print(tokens["id_token"])

        # Try to decode the ID token (basic decoding without verification)
        import base64
        try:
            # ID tokens are JWTs with format: header.payload.signature
            parts = tokens["id_token"].split(".")
            if len(parts) >= 2:
                # Add padding if needed
                payload = parts[1]
                payload += "=" * (4 - len(payload) % 4)
                decoded_payload = base64.urlsafe_b64decode(payload)
                claims = json.loads(decoded_payload)

                print("\n=== ID TOKEN CLAIMS ===")
                print(json.dumps(claims, indent=2))
        except Exception as e:
            print(f"Could not decode ID token: {e}")

    if "access_token" in tokens:
        print("\n=== ACCESS TOKEN ===")
        print(tokens["access_token"])

    if "refresh_token" in tokens:
        print("\n=== REFRESH TOKEN ===")
        print(tokens["refresh_token"])

    # Call userinfo endpoint if available
    if userinfo_endpoint and "access_token" in tokens:
        print("\n=== CALLING USERINFO ENDPOINT ===")
        headers = {
            "Authorization": f"Bearer {tokens['access_token']}"
        }
        userinfo_response = requests.get(userinfo_endpoint, headers=headers)

        if userinfo_response.status_code == 200:
            userinfo = userinfo_response.json()
            print(json.dumps(userinfo, indent=2))
        else:
            print(f"UserInfo request failed with status {userinfo_response.status_code}")
            print(userinfo_response.text)

    # Call introspection endpoint if available
    if introspection_endpoint and "access_token" in tokens:
        print("\n=== CALLING INTROSPECTION ENDPOINT ===")
        introspection_data = {
            "token": tokens["access_token"],
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
        introspection_response = requests.post(introspection_endpoint, data=introspection_data)

        if introspection_response.status_code == 200:
            introspection_result = introspection_response.json()
            print(json.dumps(introspection_result, indent=2))
        else:
            print(f"Introspection request failed with status {introspection_response.status_code}")
            print(introspection_response.text)

    print("\n=== SUCCESS ===")
    print("OIDC handshake completed successfully!")
else:
    print(f"\n=== ERROR ===")
    print(f"Token exchange failed with status {token_response.status_code}")
    print(token_response.text)
