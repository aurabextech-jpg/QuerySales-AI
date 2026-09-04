import os
import sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv

# Add the parent directory to sys.path to find the .env file if running from scripts/
base_dir = Path(__file__).resolve().parent.parent
load_dotenv(base_dir / ".env")

def get_refresh_token():
    client_id = os.getenv("GOOGLE_CALENDAR_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Error: GOOGLE_CALENDAR_CLIENT_ID and GOOGLE_CALENDAR_CLIENT_SECRET must be set in your .env file.")
        sys.exit(1)

    # Scopes required for the Calendar API
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    print("\n1. A browser window will open for authentication.")
    print("2. Log in with the Google account you added as a 'Test User' in GCP.")
    print("3. After granting permissions, return to this terminal.\n")

    try:
        flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
        creds = flow.run_local_server(port=0)

        print("\n" + "="*60)
        print("SUCCESS! COPY THE REFRESH TOKEN BELOW:")
        print("="*60)
        print(f"\nGOOGLE_CALENDAR_REFRESH_TOKEN={creds.refresh_token}\n")
        print("="*60)
        print("Paste this value into your .env file and restart the backend.\n")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    get_refresh_token()
