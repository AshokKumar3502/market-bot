import requests

ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiIyQkNCNzQiLCJqdGkiOiI2OTk5NDlhNDMwNTVlYzdlZWU3NWQyOGYiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6dHJ1ZSwiaWF0IjoxNzcxNjUzNTQwLCJpc3MiOiJ1ZGFwaS1nYXRld2F5LXNlcnZpY2UiLCJleHAiOjE3NzE3MTEyMDB9.C9G0JmGSmJXr6-mtOZWENL5usa7SRvwP5JBKJHgP3CA"

url = "https://api.upstox.com/v2/market-quote/ltp?instrument_key=NSE_EQ|INE935N01020"

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Accept": "application/json"
}

response = requests.get(url, headers=headers)

print(response.status_code)
print(response.json())