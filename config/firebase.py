# config/firebase.py
import firebase_admin
from firebase_admin import credentials, firestore
from django.conf import settings

_db = None

def get_firestore_client():
    global _db
    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
    if _db is None:
        _db = firestore.client()
    return _db