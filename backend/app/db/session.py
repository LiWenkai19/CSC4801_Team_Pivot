from sqlmodel import Session, create_engine
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL,echo=True,pool_size = 10,max_overflow=20)

def get_db():
    with Session(engine) as session:
        yield session

