from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")

db = client["medai"]   # 👈 VERY IMPORTANT
users_collection = db["users"]
patients_collection = db["patients"]
audit_logs = db["audit_logs"]
activities_collection = db["activities"]
# persistent system settings document
settings_collection = db["settings"]
