import requests

ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiIyQkNCNzQiLCJqdGkiOiI2OTlkMjQ5OTA0NTQxZTc2ZWRkMzMzODMiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6dHJ1ZSwiaWF0IjoxNzcxOTA2MjAxLCJpc3MiOiJ1ZGFwaS1nYXRld2F5LXNlcnZpY2UiLCJleHAiOjE3NzE5NzA0MDB9.k8M6pdpFGofqQUBiyDa0teyS3LqPq9afMSQ2pO0ZWss"
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Accept": "application/json"}

# Test 1: Profile
r = requests.get("https://api.upstox.com/v2/user/profile", headers=HEADERS)
print("✅ Profile:", r.status_code == 200)

# Test 2: Instruments  
r = requests.get("https://api.upstox.com/v2/instruments/nse_eq", headers=HEADERS)
print("✅ Instruments:", r.status_code == 200 and r.json().get('status') == 'success')

if r.status_code == 200:
    print("✅ Token VALID! Instruments count:", len(r.json()['data']['data']))
else:
    print("❌ Error:", r.text[:200])
