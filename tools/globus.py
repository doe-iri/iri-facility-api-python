import globus_sdk
import datetime
import time
import os

GLOBUS_APP_ID = os.environ.get("GLOBUS_APP_ID")
GLOBUS_APP_SECRET = os.environ.get("GLOBUS_APP_SECRET")
GLOBUS_RS_ID = os.environ.get("GLOBUS_RS_ID")
GLOBUS_RS_SCOPE_SUFFIX = os.environ.get("GLOBUS_RS_SCOPE_SUFFIX")
GLOBUS_SCOPE = f"https://auth.globus.org/scopes/{GLOBUS_RS_ID}/{GLOBUS_RS_SCOPE_SUFFIX}"

# Create a confidential client
client = globus_sdk.ConfidentialAppAuthClient(GLOBUS_APP_ID, GLOBUS_APP_SECRET)

# Start the OAuth flow
client.oauth2_start_flow(
    redirect_uri="http://localhost:5000/callback",  # or your registered redirect URI
    requested_scopes=["openid", "profile", "email", GLOBUS_SCOPE]
)

# Get the authorization URL
authorize_url = client.oauth2_get_authorize_url()
print(f"Visit this URL in your browser:\n{authorize_url}\n")

# After visiting the URL and authorizing, you'll be redirected to a URL with a code parameter
auth_code = input("Paste the 'code' parameter from the redirect URL: ")

# Exchange the code for tokens
token_response = client.oauth2_exchange_code_for_tokens(auth_code)

# Print all resource servers and their tokens
print("\n=== ALL TOKENS ===")
for resource_server, token_data in token_response.by_resource_server.items():
    print(f"\nResource Server: {resource_server}")
    print(f"  Access Token: {token_data['access_token'][:50]}...")
    print(f"  Scope: {token_data.get('scope', 'N/A')}")
    print(f"  Expires at: {datetime.datetime.fromtimestamp(token_data['expires_at_seconds'])}")

# Extract the IRI API token to send to the API
if GLOBUS_RS_ID in token_response.by_resource_server:
    iri_token_data = token_response.by_resource_server[GLOBUS_RS_ID]
    iri_token = iri_token_data['access_token']
    expires_at = iri_token_data['expires_at_seconds']

    # Convert to human-readable time
    expiration_time = datetime.datetime.fromtimestamp(expires_at)
    print(f"\nIRI API token expires at: {expiration_time}")

    # Calculate how long until expiration
    seconds_until_expiration = expires_at - time.time()
    hours_until_expiration = seconds_until_expiration / 3600
    print(f"Token expires in {hours_until_expiration:.2f} hours")

    print(f"\n=== USE THIS IRI API TOKEN ===")
    print(f"IMPORTANT: You must log in with your NERSC-linked Globus identity")
    print(f"\n{iri_token}")
else:
    print(f"\nERROR: No IRI API token found. Make sure you requested the correct scope.")
