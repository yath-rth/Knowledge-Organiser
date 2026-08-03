import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("service_account.json")
firebase_admin.initialize_app(cred)

try:
    db = firestore.client(database_id="databasev1")
    print(db._database_string)
    print(db)
except Exception as e:
    print(e)