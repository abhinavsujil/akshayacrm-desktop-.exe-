# supabase_utils.py

import requests
import json

SUPABASE_URL = "https://exjmniefzgytfvbnbqct.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV4am1uaWVmemd5dGZ2Ym5icWN0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTIyMjM5MjAsImV4cCI6MjA2Nzc5OTkyMH0.U0m52fIJvtiwfrz11VHtow2sHHK3cNxiLu6nXEFcQzU"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def supabase_get(table, filter_query=None, select="*"):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
    if filter_query:
        url += f"&{filter_query}"
    response = requests.get(url, headers=HEADERS)
    return response

def supabase_post(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    print(f"[POST] Table: {table}")
    print(f"Data: {json.dumps(data, indent=2)}")

    response = requests.post(url, headers=HEADERS, json=data)

    # Print full error if failed
    if response.status_code not in (200, 201):
        print("❌ Supabase POST Error:")
        print("Status Code:", response.status_code)
        print("Response:", response.text)
    else:
        print("✅ POST Success:", response.status_code)

    return response
