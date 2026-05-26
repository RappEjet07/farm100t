# ─── API ────────────────────────────────────────────────────────────────

 
def check_pool():

    try:

        r = requests.get(f"{API_BASE}/pool/remaining", headers=HEADERS, timeout=15)

        r.raise_for_status()

        d = r.json().get("data", {})

        remaining = d.get("remaining", 0)

        total = d.get("totalQuota", 1)

        pct = (remaining / total) * 100

        print(f"[*] Pool: {remaining:,} remaining ({pct:.2f}%)")

        print(f"    Total: {total:,} | Granted: {d.get('grantedCount', 0):,}")

        return d

    except Exception as e:

        print(f"[!] Pool error: {e}")

        return None

 
def get_upload_url(filename):

    try:

        r = requests.post(f"{API_BASE}/grant/submit/upload", headers=HEADERS,

                          json={"fileName": filename}, timeout=15)

        r.raise_for_status()

        d = r.json()

        if d.get("code") != 0:

            return None, None

        return d["data"]["uploadUrl"], d["data"]["resourceUrl"]

    except:

        return None, None

 
def upload_screenshot(upload_url, path):

    try:

        data = path.read_bytes()

        r = requests.put(upload_url, headers={

            "Content-Type": "application/octet-stream",

            "Referer": "https://100t.xiaomimimo.com/",

            "User-Agent": HEADERS["User-Agent"],

        }, data=data, timeout=30)

        return r.status_code in (200, 201)

    except:

        return False

 
def solve_captcha(api_key, provider="capsolver"):

    print(f"    Solving captcha ({provider})...")

    if provider == "capsolver":

        url_create = "https://api.capsolver.com/createTask"

        url_result = "https://api.capsolver.com/getTaskResult"

        task_type = "ReCaptchaV2EnterpriseTaskProxyLess"

        interval = 3

    else:

        url_create = "https://api.2captcha.com/createTask"

        url_result = "https://api.2captcha.com/getTaskResult"

        task_type = "RecaptchaV2EnterpriseTaskProxyless"

        interval = 5

 
    try:

        r = requests.post(url_create, json={

            "clientKey": api_key,

            "task": {

                "type": task_type,

                "websiteURL": "https://100t.xiaomimimo.com/",

                "websiteKey": CAPTCHA_SITEKEY,

            },

        }, timeout=30)

        result = r.json()

        if result.get("errorId", 0) != 0:

            print(f"[!] Captcha error: {result.get('errorDescription')}")

            return None

        task_id = result["taskId"]

    except Exception as e:

        print(f"[!] Captcha error: {e}")

        return None

 
    for _ in range(60):

        time.sleep(interval)

        try:

            r = requests.post(url_result, json={"clientKey": api_key, "taskId": task_id}, timeout=15)

            result = r.json()

            if result.get("status") == "ready":

                token = result["solution"]["gRecaptchaResponse"]

                print(f"    Captcha solved ({len(token)} chars)")

                return token

            if result.get("errorId", 0) != 0:

                print(f"[!] Captcha error: {result.get('errorDescription')}")

                return None

        except:

            pass

 
    print("[!] Captcha timeout")

    return None

 
def get_captcha_e_token():

    """Use Playwright to load 100t page, trigger Xiaomi SDK captcha flow,

    intercept /captcha/v2/data response, and extract the encrypted 'e' token."""

    import subprocess

    helper = SCRIPT_DIR / "get_captcha_e.py"

    try:

        r = subprocess.run(

            [PLAYWRIGHT_PYTHON, str(helper)],

            capture_output=True, text=True, timeout=60,

        )

        if r.returncode == 0 and r.stdout.strip():

            parts = r.stdout.strip().split("\t")

            if len(parts) == 2:

                event_id, e_token = parts

                print(f"    Got e token from Playwright (event={event_id[:16]}...)")

                return event_id, e_token

        print(f"[!] Playwright captcha helper failed: {r.stderr.strip()}")

    except subprocess.
  TimeoutExpired:

        print("[!] Playwright captcha helper timed out")

    except Exception as e:

        print(f"[!] Playwright captcha helper error: {e}")

    return None, None

 
def verify_xiaomi(recaptcha_token, encrypted_token):

    """POST /captcha/v2/recaptcha/verify to get final captcha token."""

    try:

        r = requests.post(CAPTCHA_VERIFY_URL, params={

            "k": CAPTCHA_XIAOMI_KEY, "locale": "zh_CN",

            "_t": str(int(time.time() * 1000)),

        }, data={"e": encrypted_token, "g": recaptcha_token, "type": "4"}, headers={

            "Content-type": "application/x-www-form-urlencoded",

            "Referer": "https://100t.xiaomimimo.com/",

            "User-Agent": HEADERS["User-Agent"],

        }, timeout=15)

        d = r.json()

        if d.get("code") == 0 and d.get("data", {}).get("result"):

            print("    Xiaomi captcha verified")

            return d["data"]["token"]

        print(f"[!] Xiaomi verify failed: code={d.get('code')}, result={d.get('data', {}).get('result')}")

        return None

    except Exception as e:

        print(f"[!] Xiaomi verify error: {e}")

        return None

 
def submit(email, description, proof_urls, captcha_token=None):

    """proof_urls is a comma-separated string of screenshot URLs + project URL."""

    payload = {

        "email": email,

        "agentTool": AGENT_TOOL,

        "models": MODELS,

        "workDescription": description,

        "proofUrl": proof_urls,

        "lang": "en",

    }

    if captcha_token:

        payload["captchaToken"] = captcha_token

    try:

        r = requests.post(f"{API_BASE}/grant/submit", headers=HEADERS, json=payload, timeout=15)

        r.raise_for_status()

        d = r.json()

        return d.get("code") == 0, d.get("message", str(d))

    except Exception as e:

        return False, str(e)

 
# ─── Main ────────────────────────────────────────────────────────────────

 
def main():

    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--count", type=int, default=1)

    parser.add_argument("--dry-run", action="store_true")

    parser.add_argument("--check-pool", action="store_true")

    parser.add_argument("--skip-captcha", action="store_true")

    args = parser.parse_args()

 
    state = load_state()

 
    pool = check_pool()

    if not pool:

        sys.exit(1)

    if args.check_pool:

        return

    if pool["remaining"] <= 0:

        print("[!] Pool exhausted")

        sys.exit(1)

 
    # Load description

    if not DESCRIPTION_FILE.exists():

        print(f"[!] {DESCRIPTION_FILE} not found — create description.txt")

        sys.exit(1)

    description = DESCRIPTION_FILE.read_text().strip()

    print(f"[*] Description: {len(description)} chars")

 
    # Load project URL

    project_url = ""

    if PROJECT_FILE.exists():

        project_url = PROJECT_FILE.read_text().strip()

        if project_url:

            print(f"[*] Project: {project_url}")

    else:

        print(f"[!] {PROJECT_FILE} not found — create project.txt")

 
    # Load captcha key

    captcha_key = None

    if not args.skip_captcha:

        env_file = CRED_DIR / "captcha-provider.env"

        if env_file.exists():

            for line in env_file.read_text().splitlines():

                if line.startswith("CAPTCHA_CAPSOLVER_API_KEY="):

                    captcha_key = line.split("=", 1)[1]

                    break

        if not captcha_key:

            print("[!] CapSolver key not found, skipping captcha")

            args.skip_captcha = True

 
    # Screenshots — need at least 2

    SCREENSHOTS_DIR.mkdir(exist_ok=True)

    screenshots = list(SCREENSHOTS_DIR.glob("*.png")) + list(SCREENSHOTS_DIR.glob("*.jpg"))

    if len(screenshots) < 2:

        print(f"[!] Need at least 2 screenshots in {SCREENSHOTS_DIR}/")

        print(f"    Found: {len(screenshots)}")

        sys.exit(1)

 
    print(f"\n{'='*50}")

    print(f"  Submitting {args.count} application(s)")

    print(f"  Captcha: {'skip' if args.
                        skip_captcha else 'capsolver'}")

    if project_url:

        print(f"  Project: {project_url}")

    print(f"{'='*50}\n")

 
    ok_count = 0

    fail_count = 0

 
    for i in range(args.count):

        print(f"--- [{i+1}/{args.count}] ---")

 
        email = generate_email(state)

        print(f"    Email: {email}")

 
        if args.dry_run:

            print("    [DRY RUN]")

            continue

 
        if is_used(email, state):

            email = generate_email(state)

 
        # Upload 2 screenshots

        proof_parts = []

        picked = random.sample(screenshots, 2)

        for j, ss in enumerate(picked):

            fname = f"Screenshot_{int(time.time())}_{i}_{j}.png"

            upload_url, resource_url = get_upload_url(fname)

            if not upload_url:

                print(f"    [-] Upload URL failed for screenshot {j+1}")

                break

            if upload_screenshot(upload_url, ss):

                proof_parts.append(resource_url)

                print(f"    Screenshot {j+1} uploaded")

            else:

                print(f"    [-] Screenshot {j+1} upload failed")

                break

 
        if len(proof_parts) < 2:

            print("    [-] Screenshot upload incomplete")

            fail_count += 1

            continue

 
        # Add project URL

        if project_url:

            proof_parts.append(project_url)

 
        proof_urls = ",".join(proof_parts)

 
        # Captcha (Playwright + Capsolver flow)

        captcha_token = None

        if not args.skip_captcha:

            # Step 1: Playwright triggers Xiaomi SDK → extract 'e' token

            event_id, e_token = get_captcha_e_token()

            if e_token:

                # Step 2: Capsolver solves reCAPTCHA → get 'g' token

                recaptcha_token = solve_captcha(captcha_key)

                if recaptcha_token:

                    # Step 3: Verify with e + g → get final captcha token

                    captcha_token = verify_xiaomi(recaptcha_token, e_token)

                    if not captcha_token:

                        print("    Submitting without captcha token...")

                else:

                    print("    [-] Captcha solve failed, submitting without token...")

            else:

                print("    [-] Could not get e token, submitting without captcha...")

 
        # Submit

        success, msg = submit(email, description, proof_urls, captcha_token)

        if success:

            print(f"    [+] SUCCESS")

            state["submitted"].append(email)

            state["total"] = state.get("total", 0) + 1

            save_state(state)

            ok_count += 1

        else:

            print(f"    [-] FAILED: {msg}")

            fail_count += 1

 
        if i < args.count - 1:

            delay = random.uniform(3, 8)

            print(f"    Waiting {delay:.1f}s...")

            time.sleep(delay)

 
    print(f"\n{'='*50}")

    print(f"  Done: {ok_count} ok, {fail_count} fail | Total: {state.get('total', 0)}")

    print(f"{'='*50}")

 
 
if __name__ == "__main__":

    main()

 
