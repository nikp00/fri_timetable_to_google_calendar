from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import pickle
import os
import sys

SCOPES = ['https://www.googleapis.com/auth/calendar']

CSV_FILE = "events_ids.csv"


def build_service():
    """
    Builds the google API service (code from google docs)
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)

    return service


service = build_service()

try:
    with open(CSV_FILE, "r") as file:
        event_ids = file.read()[:-1].split(",")

except (FileNotFoundError):
    print("File with the event id's is not found.")
    sys.exit(1)

for event_id in event_ids:
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
    except (HttpError):
        print(f"Event: {event_id} doesnt exist")

os.remove(CSV_FILE)
