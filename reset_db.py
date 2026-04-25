from app.database import engine, Base
import app.module_users.models
import app.security.models
import app.module_workshops.models
import app.module_incidents.models

print("Dropping all tables...")
Base.metadata.drop_all(bind=engine)
print("All tables dropped.")
