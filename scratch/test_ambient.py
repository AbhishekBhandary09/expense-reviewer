import subprocess
import time
import urllib.request
import urllib.error
import base64
import json
import sys

def main():
    print("Starting FastAPI ambient server...")
    # Start the server using the virtual environment python/uvicorn
    server_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8080"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for the server to spin up
    print("Waiting for server to start...")
    time.sleep(3)
    
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
    
    exit_code = 1
    try:
        print("Sending POST request to http://127.0.0.1:8080/trigger/pubsub ...")
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            print("Response status code:", response.status)
            print("Response body:", res_json)
            
            if response.status == 200 and res_json.get("status") == "success":
                print("SUCCESS: Endpoint processed Pub/Sub trigger correctly!")
                exit_code = 0
            else:
                print("FAILURE: Invalid response received.")
    except urllib.error.HTTPError as e:
        print("HTTP Error:", e.code, e.read().decode("utf-8"))
    except Exception as e:
        print("Error connecting to server:", e)
    finally:
        print("Shutting down FastAPI server...")
        server_process.terminate()
        try:
            stdout, stderr = server_process.communicate(timeout=3)
            print("Server stdout log preview:\n", stdout[:800])
        except Exception:
            pass
            
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
