# Kukule Ganga Inflow Forecast

## 1. Backend (runs the LightGBM models)
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

## 2. Frontend (React + Vite + Tailwind)
cd frontend
npm install
npm run dev          # http://localhost:5173  (proxies /api -> localhost:8000)

Production: set VITE_API_URL in frontend/.env and add your origin to CORS in backend/main.py.
