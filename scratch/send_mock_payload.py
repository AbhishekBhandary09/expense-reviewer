import urllib.request
import urllib.error
import base64
import json

def main():
    # Prepare the payload
    expense_data = {
        "amount": 150.0,
        "submitter": "alice@company.com",
        "category": "software",
        "description": "IDE License",
        "date": "2026-06-06"
    }
    
    # Base64 encode the JSON payload
    encoded_data = base64.b64encode(json.dumps(expense_data).encode("utf-8")).decode("utf-8")
    
    payload = {
        "message": {
            "data": encoded_data,
            "attributes": {
                "source": "verification-script"
            }
        },
        "subscription": "projects/my-project/subscriptions/my-subscription-test"
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8080/trigger/pubsub",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        print("Sending POST request to http://127.0.0.1:8080/trigger/pubsub ...")
        with urllib.request.urlopen(req, timeout=15) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            print("Response status code:", response.status)
            print("Response body:", res_json)
    except urllib.error.HTTPError as e:
        print("HTTP Error:", e.code, e.read().decode("utf-8"))
    except Exception as e:
        print("Error connecting to server:", e)

if __name__ == "__main__":
    main()
