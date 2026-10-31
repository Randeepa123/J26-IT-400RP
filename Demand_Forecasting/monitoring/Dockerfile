FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.12 uvicorn==0.34.2 numpy==2.2.5 scikit-learn==1.6.1 river==0.22.0
COPY src/live_demo.py /app/src/live_demo.py
CMD ["python", "-m", "uvicorn", "src.live_demo:app", "--host", "0.0.0.0", "--port", "8010"]
