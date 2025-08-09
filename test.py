from supabase_utils import db

staff_docs = db.collection("staff").stream()
for staff in staff_docs:
    print(f"Staff: {staff.id}")
    logs = db.collection("staff").document(staff.id).collection("logs").stream()
    for log in logs:
        print("  Log:", log.to_dict())
