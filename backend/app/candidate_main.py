"""Separate application entrypoint; never mutates or imports the team's app instance."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.candidate.accounts import user_router
from app.candidate.router import router as candidate_router
from app.core.config import settings

app = FastAPI(title=f'{settings.APP_NAME} - Candidate workspace')
app.add_middleware(CORSMiddleware, allow_origins=[
    'http://localhost:5173', 'http://127.0.0.1:5173',
], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app.include_router(user_router)
app.include_router(candidate_router)
