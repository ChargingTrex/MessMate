# MessMate Startup Guide

## Prerequisites
- Python 3.9+
- Google Cloud Service Account credentials (`credentials.json`)
- Google Sheet with `responses` and `daily_summary` tabs

## Setup Instructions

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone <repository_url>
   cd MessMate
   ```

2. **Create and Activate a Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   # (On Windows use: `venv\Scripts\activate`)
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables Configuration**:
   Create a `.env` file in the root directory (or ensure the existing one is configured). Typically it should include:
   ```env
   SPREADSHEET_ID=your_google_spreadsheet_id_here
   FLASK_SECRET_KEY=your_secret_key_here
   ```
   *Note: If testing locally, place your `credentials.json` directly in the root folder. If hosting on platforms like Render or Railway, pass the credentials JSON as an environment variable `GOOGLE_CREDENTIALS_JSON`.*

## Running the Application

**To start the local webserver**:
```bash
python app.py
```
*The default port is usually 5000. Open `http://localhost:5000` in your browser.*

## Testing

To run end-to-end tests or scripts in the `test/` directory, simply use `pytest`:
```bash
pytest test/
```
Or execute the local testing scripts individually:
```bash
python test/submit_dummy.py
python test/test_update_daily.py
```
