# MVP app — search, review, and export

Single Streamlit UI with sidebar navigation. Requires the API on port 8001.

## Setup

```powershell
cd frontend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
streamlit run app.py
```

Open http://localhost:8501

## Pages

| Sidebar | Purpose |
|---------|---------|
| **Find leads** | Run the search pipeline |
| **Review leads** | Filter and open conferences |
| **Manual crawl** | Sites that blocked auto-crawl (403, etc.) |
| **Conference detail** | Opens when you click Open (breadcrumb + back button) |

Optional: `$env:API_BASE_URL = "http://127.0.0.1:8001"`
