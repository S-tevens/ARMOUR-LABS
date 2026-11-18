"""Entry point: `uvicorn main:app --reload` from the backend/ folder."""
from api.app import create_app

app = create_app()
