from app.database import engine, Base
import app.users.models
import app.security.models
import app.workshops.models
import app.incidents.models

print("Dropping all tables...")
Base.metadata.drop_all(bind=engine)
print("All tables dropped.")
