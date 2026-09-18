import json
import urllib.request
import urllib.error
import time
import sys

# Define ANSI escape codes for colored output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    print(f"{Colors.HEADER}Testing GET /health endpoint...{Colors.ENDC}")
    url = f"{BASE_URL}/health"
    try:
        req = urllib.request.Request(url, method="GET")
        start_time = time.time()
        with urllib.request.urlopen(req) as response:
            latency = time.time() - start_time
            if response.status == 200:
                print(f"{Colors.OKGREEN}✓ Health Check Passed | Latency: {latency:.4f}s{Colors.ENDC}\n")
                return True
            else:
                print(f"{Colors.FAIL}✗ Health Check Failed | Status: {response.status}{Colors.ENDC}\n")
                return False
    except Exception as e:
        print(f"{Colors.FAIL}✗ Health Check Failed | Error: {e}{Colors.ENDC}\n")
        print(f"{Colors.WARNING}Please ensure the FastAPI server is running (e.g., 'uvicorn main:app --reload').{Colors.ENDC}\n")
        return False

def test_cases():
    file_path = "BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
    print(f"{Colors.HEADER}Loading test cases from {file_path}...{Colors.ENDC}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            cases = data.get("cases", [])
    except FileNotFoundError:
        print(f"{Colors.FAIL}✗ File {file_path} not found!{Colors.ENDC}")
        return
    except json.JSONDecodeError:
        print(f"{Colors.FAIL}✗ Invalid JSON format in {file_path}!{Colors.ENDC}")
        return
    
    if not cases:
        print(f"{Colors.WARNING}! No cases found in the JSON file.{Colors.ENDC}")
        return

    url = f"{BASE_URL}/optimize-energy"
    
    print(f"{Colors.HEADER}Starting POST /optimize-energy tests...{Colors.ENDC}\n")
    
    for idx, case in enumerate(cases):
        case_id = case.get("input", {}).get("scenario_id", f"UNKNOWN-{idx}")
        payload = json.dumps(case.get("input", {})).encode("utf-8")
        
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        
        start_time = time.time()
        
        try:
            with urllib.request.urlopen(req) as response:
                latency = time.time() - start_time
                status = response.status
                
                if status == 200:
                    if latency > 4.0:
                        print(f"{Colors.WARNING}Case {case_id}: PASSED (WARNING: High Latency) | Latency: {latency:.4f}s{Colors.ENDC}")
                    else:
                        print(f"{Colors.OKGREEN}Case {case_id}: PASSED | Latency: {latency:.4f}s{Colors.ENDC}")
                else:
                    print(f"{Colors.FAIL}Case {case_id}: FAILED | Status: {status} | Latency: {latency:.4f}s{Colors.ENDC}")
        except urllib.error.HTTPError as e:
            latency = time.time() - start_time
            print(f"{Colors.FAIL}Case {case_id}: FAILED | Status: {e.code} | Latency: {latency:.4f}s{Colors.ENDC}")
            try:
                print(f"   Reason: {e.read().decode('utf-8')}")
            except:
                pass
        except Exception as e:
            latency = time.time() - start_time
            print(f"{Colors.FAIL}Case {case_id}: ERROR | Error: {str(e)} | Latency: {latency:.4f}s{Colors.ENDC}")

if __name__ == "__main__":
    if test_health():
        test_cases()
