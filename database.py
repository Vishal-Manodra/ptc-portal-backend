# database.py
# This file sets up the "bridge" between our Python code and PostgreSQL.
# Think of it like dialing a phone number to connect to the database.

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

# Load all values from .env file into environment variables
load_dotenv()

# Read the database connection string from .env
DATABASE_URL = os.getenv("DATABASE_URL")

# create_engine = establish the connection to PostgreSQL
# It's like opening a pipeline to the database
engine = create_engine(DATABASE_URL)

# SessionLocal = a factory that creates individual database "sessions"
# Each API request gets its own session (like each customer gets their own waiter)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base = the parent class all our database table models will inherit from
# When we define a table in models.py, it extends this Base
Base = declarative_base()


# This is a "dependency" — FastAPI will call this function for every request
# that needs database access. It opens a session, gives it to the route,
# then closes it when the request is done (the "finally" guarantees cleanup).
def get_db():
    db = SessionLocal()
    try:
        yield db          # "yield" means: give this db session to whoever asked
    finally:
        db.close()        # always close the session after the request finishes