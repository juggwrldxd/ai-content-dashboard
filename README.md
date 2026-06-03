# AI Content Business Dashboard
FastAPI dashboard with Google Drive storage. Deploy on Railway.

## Setup
1. Set env var `GOOGLE_TOKEN_PATH` to your Google OAuth token JSON path
2. Or place token at `~/.hermes/google_token.json`
3. Deploy to Railway

## Run locally
```bash
pip install -r requirements.txt
python railway_app.py
```