# test.py

from supabase_utils import supabase_get

if __name__ == "__main__":
    # List staff
    resp_staff = supabase_get("staff")
    print("=== STAFF ===")
    print(resp_staff.status_code, resp_staff.text)

    # List logs
    resp_logs = supabase_get("logs")
    print("=== LOGS ===")
    print(resp_logs.status_code, resp_logs.text)

    # List services
    resp_services = supabase_get("services")
    print("=== SERVICES ===")
    print(resp_services.status_code, resp_services.text)
