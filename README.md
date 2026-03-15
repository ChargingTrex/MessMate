# MessMate

A college mess food review web app.

## Setup Instructions

### Google Cloud Service Account Setup
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or select an existing one.
3. Enable the **Google Sheets API** and **Google Drive API** for the project.
4. Go to **IAM & Admin > Service Accounts** and create a new service account.
5. Create a new JSON key for this service account and download it.
6. The contents of this JSON file must be saved into a file named `credentials.json` (do not commit this to Git) or configured as the `GOOGLE_CREDENTIALS_JSON` environment variable.
7. Create a new Google Sheet.
8. Share the Google Sheet with the email address of the new service account, giving it "Editor" permissions.
9. Note the Google Spreadsheet ID from the URL of your new Google Sheet and configure it as the `SPREADSHEET_ID` environment variable.

### Local Development
1. Create a virtual environment and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
2. Set environment variables:
```bash
export GOOGLE_CREDENTIALS_JSON='{... full JSON string here ...}'
export SPREADSHEET_ID='your-spreadsheet-id'
export FLASK_SECRET_KEY='your-secret-key'
```
3. Run the development server locally:
```bash
python app.py
```
