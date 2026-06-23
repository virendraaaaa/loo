import os
import json
import time
import sys
import random
import re
import datetime
import asyncio
import requests

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Install: pip install playwright")
    sys.exit(1)

current_progress = ""

def log(action, status, email=None, error=None):
    """Logging in identical style to automation_bot.py"""
    global current_progress
    
    if action == "Email" and status == "START" and error and error.startswith("[") and "/" in error:
        current_progress = error
        error = None
        
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    is_important = True  # Log most events for registration bot
    
    parts = [f"[{ts}]"]
    if current_progress:
        parts.append(current_progress)
    if email:
        parts.append(f"[{email}]")
    parts.append(f"{action} | {status}")
    if error:
        error_clean = str(error).replace("\r", "").replace("\n", " | ")
        parts.append(f"| {error_clean}")
        
    msg = " ".join(parts) + "\n"
    print(msg.rstrip())
    
    if is_important:
        try:
            with open("bot_execution.log", "a", encoding="utf-8") as f:
                f.write(msg)
        except:
            pass

def load_config():
    """Load config"""
    default_config = {
        "email_file": "email.txt",
        "signup_url": "https://www.canva.com/brand/join?token=H4cKam2KEzH3Z43NJpNGfg&referrer=team-invite",
        "password": "qwerty123",
        "headless": False,
        "connect_endpoint": "https://api.genityboost.site/connect/account",
        "loop_delay": 10,
        "max_accounts": 0,
    }
    if not os.path.exists("config.json"):
        return default_config
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            user_config = json.load(f)
            # Merge with defaults
            for k, v in default_config.items():
                if k not in user_config:
                    user_config[k] = v
            return user_config
    except:
        return default_config

def generate_random_name():
    """Generate a realistic random name"""
    first_names = ["Budi", "Andi", "Siti", "Dewi", "Rian", "Denny", "Eka", "Putri", "Adi", "Agus", "Rini", "Fajar", "Hadi", "Indah", "Joko", "Kartika", "Lestari", "Mega", "Nugroho", "Prasetyo"]
    last_names = ["Pratama", "Wijaya", "Santoso", "Hidayat", "Saputra", "Kurniawan", "Sari", "Wulandari", "Utami", "Setiawan", "Gunawan", "Budiman", "Siregar", "Lubis", "Ginting", "Nasution"]
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def generate_temp_email():
    """Generate temporary email from Lisensify API, avoiding @lisensify.com domain"""
    url = "https://lisensify.com/api/generate"
    headers = {
        "Accept": "*/*",
        "Referer": "https://lisensify.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    }
    
    # Try up to 5 times to get a non-blocked domain
    for attempt in range(5):
        try:
            log("Lisensify", f"GENERATE_REQUEST_ATTEMPT_{attempt+1}")
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                email = data.get("address")
                if email:
                    if email.lower().endswith("@lisensify.com" or "@jujurjanggal.my.id" or "@kwocag.my.id"):
                        log("Lisensify", "REJECTED_LISENSIFY_DOMAIN", email, "Retrying for a custom domain...")
                        continue
                    log("Lisensify", "GENERATE_SUCCESS", email)
                    return email
            log("Lisensify", "GENERATE_FAIL", error=f"Status code: {response.status_code}")
        except Exception as e:
            log("Lisensify", "GENERATE_ERROR", error=str(e))
    return None

def check_temp_inbox(email):
    """Check Lisensify inbox API for messages"""
    # URL encode the email address for safety
    encoded_email = requests.utils.quote(email)
    url = f"https://lisensify.com/api/inbox/{encoded_email}"
    headers = {
        "Accept": "*/*",
        "Referer": "https://lisensify.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        log("Lisensify", "INBOX_ERROR", email, str(e))
    return None

async def poll_for_otp(email, timeout_seconds=120):
    """Poll Lisensify inbox for Canva verification code"""
    log("Lisensify", "WAIT_FOR_OTP", email, f"Timeout: {timeout_seconds}s")
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        inbox = check_temp_inbox(email)
        if inbox and isinstance(inbox, dict):
            messages = inbox.get("messages", [])
            count = inbox.get("count", 0)
            if count > 0 and messages:
                log("Lisensify", f"RECEIVED_{len(messages)}_MESSAGES", email)
                for msg in messages:
                    subject = msg.get("subject", "")
                    sender = msg.get("from", "") or msg.get("fromAddress", "")
                    log("Lisensify", f"MESSAGE_PREVIEW: From={sender}, Subject='{subject}'", email)
                    
                    # Search for 6 digit code in subject
                    match = re.search(r"\b(\d{6})\b", subject)
                    if match:
                        code = match.group(1)
                        log("Lisensify", "OTP_FOUND_IN_SUBJECT", email, f"Code: {code}")
                        return code
                        
                    # Also try to search other fields if they exist (just in case)
                    for key in ["text", "body", "html"]:
                        if key in msg and msg[key]:
                            match = re.search(r"\b(\d{6})\b", str(msg[key]))
                            if match:
                                code = match.group(1)
                                log("Lisensify", f"OTP_FOUND_IN_{key.upper()}", email, f"Code: {code}")
                                return code
            else:
                # Log a subtle check message to console (without writing to file to avoid bloating log)
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Polling Lisensify inbox... (no new messages yet)")
        
        await asyncio.sleep(4)
        
    log("Lisensify", "OTP_TIMEOUT", email)
    return None

async def type_human(page, selector, text):
    """Type with realistic delays"""
    try:
        if isinstance(selector, str):
            await page.click(selector, timeout=5000)
            await asyncio.sleep(0.3)
            await page.fill(selector, "")
            for char in text:
                await page.type(selector, char, delay=random.uniform(0.04, 0.08))
        else:
            await selector.click(timeout=5000)
            await asyncio.sleep(0.3)
            await selector.fill("")
            for char in text:
                await selector.type(char, delay=random.uniform(0.04, 0.08))
        await asyncio.sleep(0.3)
        return True
    except Exception as e:
        log("TypeHuman", "ERROR", error=str(e))
        return False

async def save_session_if_credits_ok(page, context, email, password):
    """Check if the account has 8,500 credits and save the session to browser_profiles/"""
    try:
        log("Result", "CHECKING_CREDITS_8500", email)
        
        # Get access token from session
        session_info = await page.evaluate("""
            fetch("https://app.leonardo.ai/api/auth/get-session", {
                headers: { Accept: "application/json" },
                credentials: "include"
            }).then(r => r.json()).then(d => ({
                token: d.session?.accessToken || null
            })).catch(e => ({}))
        """)
        
        token = session_info.get("token")
        if not token:
            log("Result", "CHECK_CREDITS_FAIL | Access token not found in session", email)
            return False
            
        has_credits = False
        # Poll up to 10 attempts for the credits to update on Leonardo backend
        for attempt in range(10):
            credits_info = await page.evaluate("""
                async (token) => {
                    try {
                        const r = await fetch("https://api.leonardo.ai/v1/graphql", {
                            method: "POST",
                            headers: { 
                                "Authorization": "Bearer " + token, 
                                "Content-Type": "application/json" 
                            },
                            body: JSON.stringify({ query: "{ user_details { plan subscriptionTokens paidTokens } }" })
                        });
                        const j = await r.json();
                        return (j.data && j.data.user_details && j.data.user_details[0]) || {};
                    } catch (e) {
                        return {};
                    }
                }
            """, token)
            
            sub_tokens = credits_info.get("subscriptionTokens")
            paid_tokens = credits_info.get("paidTokens")
            total_tokens = (sub_tokens or 0) + (paid_tokens or 0)
            
            log("Result", f"CREDIT_POLL_ATTEMPT_{attempt+1} | Total Tokens: {total_tokens}", email)
            
            if total_tokens >= 8500:
                has_credits = True
                break
            await asyncio.sleep(2)
            
        if has_credits:
            log("Result", "CREDITS_8500_DETECTED", email)
            # Create browser_profiles/ directory if it doesn't exist
            os.makedirs("browser_profiles", exist_ok=True)
            
            # Save account details
            with open("browser_profiles/akun_sukses.txt", "a", encoding="utf-8") as f:
                f.write(f"{email}:{password}\n")
                
            # Export cookies
            cookies = await context.cookies()
            email_user = email.split("@")[0]
            cookies_path = f"browser_profiles/cookies_{email_user}.json"
            with open(cookies_path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=4)
                
            log("Result", f"SESSION_SAVED_TO_PROFILES: {cookies_path}", email)
            return True
        else:
            log("Result", "CREDITS_8500_NOT_FOUND", email)
            return False
    except Exception as e:
        log("Result", "SAVE_SESSION_ERROR", email, str(e))
        return False

async def register_canva(p, email, config):
    """Register to Canva using Email signup flow and auto-login to Leonardo with script injection"""
    password = config.get("password", "qwerty123")
    signup_url = config.get("signup_url")
    
    # Create temp directory for browser profile
    email_user = email.split("@")[0]
    profile_dir_config = config.get("profile_dir", "")
    if profile_dir_config:
        os.makedirs(profile_dir_config, exist_ok=True)
        temp_dir = os.path.join(profile_dir_config, f"temp_profile_{email_user}")
    else:
        temp_dir = os.path.abspath(f"temp_profile_{email_user}")
        
    # Detect extension folder dynamically (supports both folder names)
    path_to_extension = os.path.abspath("leonardo-connect")
    if not os.path.exists(path_to_extension):
        path_to_extension = os.path.abspath("leonardo-connect-extension")
        
    log("Playwright", "START_BROWSER", email, f"Profile: {temp_dir} | Extension: {path_to_extension}")
    
    context = None
    try:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=temp_dir,
            headless=config.get("headless", False),
            viewport=None,
            ignore_https_errors=True,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                f"--disable-extensions-except={path_to_extension}",
                f"--load-extension={path_to_extension}",
            ]
        )
        page = context.pages[0] if context.pages else await context.new_page()
        
        log("Canva", "NAVIGATE_TO_SIGNUP", email)
        await page.goto(signup_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        
        # Step 1: Accept cookies if prompted
        try:
            cookies_selectors = [
                "button:has-text('Accept')",
                "button:has-text('Accept all')",
                "button:has-text('Accept cookies')",
                "button:has-text('Setuju')",
                "button:has-text('Terima')",
                "button:has-text('Lanjut')",
                "button:has-text('Allow')",
            ]
            for selector in cookies_selectors:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    await el.click()
                    log("Canva", "COOKIES_ACCEPTED", email)
                    await asyncio.sleep(0.5)
                    break
        except:
            pass
            
        # Step 2: Handle entering the email flow
        # Check if email input is already visible (by checking standard attributes or any visible input field)
        email_input = None
        try:
            email_input = await page.query_selector("input[type='email'], input[name='email'], input[placeholder*='email'], input[placeholder*='surel']")
            if email_input and not await email_input.is_visible():
                email_input = None
        except:
            pass
            
        if not email_input:
            log("Canva", "EMAIL_INPUT_NOT_VISIBLE_LOOKING_FOR_BUTTONS", email)
            # Find continue with email buttons
            email_btn_clicked = False
            
            # First, check if there's a "Continue in another way" or "Lanjutkan dengan cara lain" button
            another_way_selectors = [
                "button[aria-label*='another way']",
                "button[aria-label*='cara lain']",
                "button:has-text('Continue in another way')",
                "button:has-text('Lanjutkan dengan cara lain')",
                "button:has-text('another way')",
                "button:has-text('cara lain')"
            ]
            for selector in another_way_selectors:
                try:
                    el = await page.query_selector(selector)
                    if el and await el.is_visible():
                        await el.click()
                        log("Canva", "CLICKED_CONTINUE_ANOTHER_WAY", email)
                        await asyncio.sleep(1.5)
                        break
                except:
                    pass
            
            # Next, look for the "Continue with email" or "Lanjutkan dengan email" button
            email_btn_selectors = [
                "button[aria-label='Continue with email']",
                "button[aria-label='Lanjutkan dengan email']",
                "button:has-text('Continue with email')",
                "button:has-text('Lanjutkan dengan email')",
                "button[aria-label*='email']",
                "button[aria-label*='Email']",
                "button:has-text('email')",
                "button:has-text('Email')",
                "[data-testid='email-login-button']",
            ]
            for selector in email_btn_selectors:
                try:
                    el = await page.query_selector(selector)
                    if el and await el.is_visible():
                        await el.click()
                        log("Canva", "CLICKED_CONTINUE_WITH_EMAIL_BUTTON", email)
                        email_btn_clicked = True
                        await asyncio.sleep(2.0)
                        break
                except:
                    pass
            
            if not email_btn_clicked:
                # If button wasn't clicked, check if the input is visible now
                try:
                    email_input = await page.wait_for_selector("input", timeout=5000)
                except:
                    pass
                    
        # Step 3: Type email
        log("Canva", "FILL_EMAIL", email)
        
        # Use wait_for_selector to handle transitions / animations
        # Fallback to the first visible input if specific attributes are missing
        email_input = None
        try:
            email_input = await page.wait_for_selector("input[type='email'], input[name='email']", timeout=5000)
        except:
            pass
            
        if not email_input:
            try:
                # Canva uses inputs without type='email' sometimes
                # Let's search by placeholder, label, class or just get the first visible input
                inputs = await page.query_selector_all("input")
                for inp in inputs:
                    if await inp.is_visible():
                        inp_type = await inp.get_attribute("type") or ""
                        inp_placeholder = await inp.get_attribute("placeholder") or ""
                        inp_id = await inp.get_attribute("id") or ""
                        if inp_type not in ["hidden", "submit", "button", "checkbox", "radio"]:
                            email_input = inp
                            log("Canva", f"FOUND_EMAIL_INPUT_FALLBACK: type={inp_type}, id={inp_id}", email)
                            break
            except Exception as e:
                log("Canva", "EMAIL_INPUT_SEARCH_ERR", email, str(e))
        
        if not email_input:
            raise Exception("Email input field not found")
            
        await type_human(page, email_input, email)
        
        # Click Continue / Lanjutkan
        continue_clicked = False
        continue_selectors = [
            "button[type='submit']",
            "button:has-text('Continue')",
            "button:has-text('Lanjutkan')",
            "button:has-text('Next')",
        ]
        for selector in continue_selectors:
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    await el.click()
                    continue_clicked = True
                    log("Canva", "CLICKED_EMAIL_CONTINUE", email)
                    break
            except:
                pass
                
        if not continue_clicked:
            # Press enter in email input
            await email_input.press("Enter")
            log("Canva", "PRESSED_ENTER_ON_EMAIL", email)
            
        await asyncio.sleep(4)
        
        # Step 4: Handle "Create your account" (Nama, Sandi/Password) if Canva prompts
        # It may show fields for Name and Password, or it may ask for OTP immediately.
        # Check which screen Canva transitioned to (wait up to 10s)
        log("Canva", "WAIT_NEXT_STEP", email)
        mode = None
        for _ in range(20):
            try:
                name_input = await page.query_selector("input[type='text']:not([name='code']):not([placeholder*='code']):not([placeholder*='kode'])")
                if name_input and await name_input.is_visible():
                    mode = "name"
                    break
            except:
                pass
            try:
                code_input = await page.query_selector("input[name='code'], input[placeholder*='code'], input[placeholder*='kode']")
                if code_input and await code_input.is_visible():
                    mode = "otp"
                    break
            except:
                pass
            await asyncio.sleep(0.5)
            
        if mode == "name":
            name_input = await page.query_selector("input[type='text']:not([name='code']):not([placeholder*='code']):not([placeholder*='kode'])")
            random_name = generate_random_name()
            log("Canva", "FILL_NAME", email, f"Name: {random_name}")
            await type_human(page, name_input, random_name)
            await asyncio.sleep(1)
            
            pwd_input = await page.query_selector("input[type='password']")
            if pwd_input and await pwd_input.is_visible():
                log("Canva", "FILL_PASSWORD", email)
                await type_human(page, pwd_input, password)
                await asyncio.sleep(1)
                
            # Click "Create account" / "Buat akun" / "Continue"
            create_btn_clicked = False
            create_selectors = [
                "button[type='submit']",
                "button:has-text('Create account')",
                "button:has-text('Buat akun')",
                "button:has-text('Continue')",
                "button:has-text('Lanjutkan')"
            ]
            for selector in create_selectors:
                try:
                    el = await page.query_selector(selector)
                    if el and await el.is_visible():
                        await el.click()
                        create_btn_clicked = True
                        log("Canva", "CLICKED_CREATE_ACCOUNT", email)
                        break
                except:
                    pass
            if not create_btn_clicked:
                await page.keyboard.press("Enter")
                log("Canva", "PRESSED_ENTER_ON_REGISTRATION", email)
                
            await asyncio.sleep(5)
            
        # Step 5: Wait for OTP page and poll Lisensify
        otp_code = await poll_for_otp(email)
        if not otp_code:
            raise Exception("Failed to get verification OTP from Lisensify")
            
        # Fill OTP code
        log("Canva", "ENTER_OTP", email, f"OTP: {otp_code}")
        
        # Check if code input is present
        # Canva verification inputs are usually 6 separate fields or a single input
        code_input = None
        try:
            code_input = await page.wait_for_selector("input[name='code'], input[placeholder*='code'], input[placeholder*='kode'], input[type='text']", timeout=10000)
        except:
            pass
        
        if code_input and await code_input.is_visible():
            await type_human(page, code_input, otp_code)
            log("Canva", "OTP_TYPED_SINGLE_INPUT", email)
        else:
            # Try to find all visible input fields (sometimes Canva has 6 separate inputs)
            inputs = await page.query_selector_all("input")
            visible_inputs = []
            for inp in inputs:
                if await inp.is_visible():
                    inp_type = await inp.get_attribute("type") or ""
                    if inp_type not in ["email", "password", "hidden", "checkbox", "radio"]:
                        visible_inputs.append(inp)
            
            if len(visible_inputs) >= 6:
                log("Canva", "OTP_TYPING_MULTIPLE_INPUTS", email)
                for idx, char in enumerate(otp_code[:len(visible_inputs)]):
                    await visible_inputs[idx].focus()
                    await visible_inputs[idx].fill(char)
                    await asyncio.sleep(0.1)
            else:
                # Fallback: try to type globally if focus can be set
                log("Canva", "OTP_TYPING_FALLBACK", email)
                await page.keyboard.type(otp_code, delay=100)
                
        await asyncio.sleep(2)
        
        # Wait for submit or auto-submit
        # If code input doesn't auto-submit, press Enter or click submit
        submit_selectors = [
            "button[type='submit']",
            "button:has-text('Continue')",
            "button:has-text('Lanjutkan')",
            "button:has-text('Confirm')",
            "button:has-text('Konfirmasi')"
        ]
        for selector in submit_selectors:
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    await el.click()
                    log("Canva", "CLICKED_OTP_SUBMIT", email)
                    break
            except:
                pass
                
        # Wait for redirect and check if success
        log("Canva", "WAIT_FOR_SUCCESS", email)
        success = False
        
        for attempt in range(20):
            try:
                url = page.url
                # Canva dashboard or team invitation accept indicator
                if "canva.com" in url and "signup" not in url and "login" not in url and "brand/join" not in url:
                    success = True
                    log("Canva", "REGISTRATION_SUCCESS_DASHBOARD", email)
                    break
                    
                # Look for team welcome/accept indicators
                accepted = await page.query_selector("text=You've accepted the team invite, text=Anda telah menerima undangan, text=telah bergabung")
                if accepted and await accepted.is_visible():
                    success = True
                    log("Canva", "REGISTRATION_SUCCESS_TEAM_ACCEPTED", email)
                    break
                    
                # What will you design header
                design_header = await page.query_selector("text=What will you design, text=Search designs, text=Beranda")
                if design_header and await design_header.is_visible():
                    success = True
                    log("Canva", "REGISTRATION_SUCCESS_HOME", email)
                    break
            except:
                pass
            await asyncio.sleep(1.5)
            
        if success:
            # Append success email to email.txt
            email_file = config.get("email_file", "email.txt")
            try:
                with open(email_file, "a", encoding="utf-8") as f:
                    f.write(f"{email}:{password}\n")
                log("Result", "SAVED_TO_FILE", email, f"File: {email_file}")
            except Exception as file_err:
                log("Result", "SAVE_ERROR", email, str(file_err))
                
            # ==================== PHASE 2: LOGIN LEONARDO ====================
            log("Leonardo", "START_LOGIN", email)
            
            # Step 2a: Navigate to Leonardo
            try:
                await page.goto(config["login_url"], wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(3)
            except Exception as e:
                log("Leonardo", "GOTO_FAIL", email, str(e))
                return False
            
            # Loop to handle login page and Canva authorization redirect
            login_success = False
            for attempt in range(30):
                try:
                    url = page.url
                    
                    if "error=invalid_request" in url:
                        log("Leonardo", "INVALID_REQUEST_DETECTED", email, "Leonardo URL contains error=invalid_request. Skipping this account...")
                        return False
                    
                    # Check if we reached the dashboard
                    if "leonardo.ai" in url and "login" not in url and "auth" not in url:
                        # Check for the checkbox (e.g. "I agree to receive updates...") and click it if present
                        try:
                            agree_checkbox = await page.query_selector("input[type='checkbox'], span[class*='checkbox'], div[class*='checkbox'], [role='checkbox']")
                            if agree_checkbox and await agree_checkbox.is_visible():
                                is_checked = await agree_checkbox.is_checked() if hasattr(agree_checkbox, 'is_checked') else False
                                if not is_checked:
                                    log("Leonardo", "CLICKING_AGREE_CHECKBOX", email)
                                    await agree_checkbox.click()
                                    await asyncio.sleep(0.5)
                        except Exception as chk_err:
                            pass
                            
                        # Sometimes a welcome/terms modal appears before dashboard loads completely. Check if it's visible.
                        welcome_btn = await page.query_selector("button:has-text('Continue'), button:has-text('Confirm'), button:has-text('Agree')")
                        if welcome_btn and await welcome_btn.is_visible():
                            log("Leonardo", "CLICKING_WELCOME_CONTINUE_BEFORE_DASHBOARD", email)
                            await welcome_btn.click()
                            await asyncio.sleep(0.5)
                        else:
                            log("Leonardo", "LOGIN_SUCCESS_DASHBOARD", email)
                            login_success = True
                            break
                        
                    # Check if we are on the Leonardo login page
                    if "leonardo.ai" in url and ("login" in url or "auth" in url):
                        # Click Canva button directly
                        canva_btn = None
                        try:
                            # Try xpath
                            canva_btn = await page.query_selector("xpath=//button[.//span[text()='Canva']]")
                            if not canva_btn:
                                # Try has-text
                                canva_btn = await page.query_selector("button:has-text('Canva')")
                            if not canva_btn:
                                # Try general buttons
                                buttons = await page.query_selector_all("button")
                                for btn in buttons:
                                    text = await btn.text_content()
                                    if text and "canva" in text.lower():
                                        canva_btn = btn
                                        break
                                        
                            if canva_btn and await canva_btn.is_visible():
                                log("Leonardo", "CLICKING_CANVA_BUTTON", email)
                                await canva_btn.click()
                                await asyncio.sleep(4)
                        except Exception as click_err:
                            log("Leonardo", "CANVA_CLICK_ERR", email, str(click_err))
                            
                    # Check if we are on Canva authorize/allow page
                    if "canva.com" in url:
                        # Accept cookies if prompted
                        try:
                            accept_cookies = await page.query_selector("button:has-text('Accept all cookies'), button:has-text('Accept')")
                            if accept_cookies and await accept_cookies.is_visible():
                                await accept_cookies.click()
                                await asyncio.sleep(1)
                        except:
                            pass
                            
                        # Click Allow
                        try:
                            allow_btn = await page.query_selector("button:has-text('Allow'), [role='button']:has-text('Allow')")
                            if allow_btn and await allow_btn.is_visible():
                                log("Leonardo", "CLICKING_CANVA_ALLOW_BUTTON", email)
                                await allow_btn.click()
                                await asyncio.sleep(4)
                        except Exception as allow_err:
                            log("Leonardo", "ALLOW_CLICK_ERR", email, str(allow_err))
                except Exception as loop_err:
                    pass
                await asyncio.sleep(2)
                
            if not login_success:
                log("Leonardo", "LOGIN_TIMEOUT_FAILED", email)
                return False
            
            # Step 2c: Wait for Leonardo dashboard onboarding modals (supports Terms checkbox, Continue, Skip and Let's Go)
            log("Leonardo", "STARTING_ONBOARDING_MODAL_HANDLING", email)
            
            checkbox_selector = "input[type='checkbox'], span[class*='checkbox'], div[class*='checkbox'], [role='checkbox']"
            modal_selectors = [
                "button:has-text('Continue')", 
                "button:has-text('Confirm')", 
                "button:has-text('Lanjut')", 
                "button:has-text('Accept')", 
                "button:has-text('Skip')",
                "button:has-text('Let\'s Go!')", 
                "button:has-text('Let\'s Go')",
                "text=Continue", 
                "text=Confirm", 
                "text=Skip",
                "text=Let's Go!"
            ]
            
            leo_ready = False
            start_time = time.time()
            last_action_time = time.time()
            
            while time.time() - start_time < 60:
                try:
                    # 1. Check for any unchecked checkboxes (e.g. Terms agreements) and click them
                    try:
                        checkboxes = await page.query_selector_all(checkbox_selector)
                        for cb in checkboxes:
                            if await cb.is_visible():
                                is_checked = await cb.is_checked() if hasattr(cb, 'is_checked') else False
                                aria_checked = await cb.get_attribute("aria-checked")
                                if not is_checked and aria_checked != "true":
                                    log("Leonardo", "CLICKING_AGREE_CHECKBOX", email)
                                    await cb.click()
                                    await asyncio.sleep(0.5)
                    except:
                        pass
                    
                    # 2. Check for any visible and enabled modal/onboarding buttons
                    clicked_modal = False
                    for selector in modal_selectors:
                        try:
                            btn = page.locator(selector).first
                            if await btn.is_visible():
                                # Enforce that we are not on a login/auth URL to avoid clicking login/auth page "Continue" buttons
                                url = page.url
                                if "login" in url or "auth" in url:
                                    continue
                                if await btn.is_enabled():
                                    text = await btn.text_content()
                                    log("Leonardo", f"MODAL_CLICKED: {text.strip() if text else 'Button'}", email)
                                    await btn.click()
                                    clicked_modal = True
                                    last_action_time = time.time()
                                    await asyncio.sleep(1.5)
                                    break
                        except:
                            pass
                            
                    if clicked_modal:
                        continue
                        
                    # 3. If no modal was clicked, check if we've been idle on the dashboard for enough time
                    idle_time = time.time() - last_action_time
                    if idle_time > 8:
                        url = page.url
                        if "leonardo.ai" in url and "login" not in url and "auth" not in url:
                            leo_ready = True
                            log("Leonardo", f"ONBOARDING_COMPLETED_IDLE_DETECTED (idle {int(idle_time)}s)", email)
                            break
                except:
                    pass
                await asyncio.sleep(0.5)
            
            
            if leo_ready:
                await asyncio.sleep(1)
                
                # Step 2e: Verify session and Inject Connection token
                try:
                    result = await page.evaluate("""
                        fetch("https://app.leonardo.ai/api/auth/get-session", {
                            headers: { Accept: "application/json" },
                            credentials: "include"
                        }).then(r => r.json()).then(d => ({
                            token: d.session?.accessToken ? true : false,
                            user: d.user?.email
                        })).catch(e => ({error: e.message}))
                    """)
                    
                    connect_token = config.get("connect_token", "OIYJ3PHqi8lic_b52ARg2Os9")
                    
                    if result.get("token"):
                        if not config.get("direct_injection", True):
                            # METODE VISUAL: Buka tab popup ekstensi dan klik hubungkan secara visual
                            extension_id = None
                            # Wait for service worker to register
                            for _ in range(15):
                                for sw in context.service_workers:
                                    if "background.js" in sw.url:
                                        extension_id = sw.url.split("/")[2]
                                        break
                                if extension_id:
                                    break
                                await asyncio.sleep(1)
                                    
                            if extension_id:
                                try:
                                    ext_page = await context.new_page()
                                    await ext_page.goto(f"chrome-extension://{extension_id}/popup.html")
                                    await ext_page.wait_for_selector("#ctoken", timeout=5000)
                                    
                                    # Wait for local storage load to complete
                                    await asyncio.sleep(1.5)
                                    
                                    # Fill the token
                                    await ext_page.fill("#ctoken", connect_token)
                                    await asyncio.sleep(0.3)
                                    
                                    # Double check to ensure it was not overwritten by popup's async storage load
                                    val = await ext_page.eval_on_selector("#ctoken", "el => el.value")
                                    if val != connect_token:
                                        await ext_page.fill("#ctoken", connect_token)
                                        await asyncio.sleep(0.3)
                                        
                                    await ext_page.click("#btn")
                                    
                                    status_text = ""
                                    connected = False
                                    for _ in range(30):
                                        try:
                                            status_el = await ext_page.query_selector("#status")
                                            if status_el:
                                                status_text = await status_el.text_content()
                                                if "CONNECTED" in status_text:
                                                    connected = True
                                                    break
                                                elif "FAILED" in status_text or "rejected" in status_text:
                                                    break
                                        except:
                                            pass
                                        await asyncio.sleep(1)
                                        
                                    if connected:
                                        log("Extension", "CONNECT_SUCCESS", email, status_text.replace('\n', ' | '))
                                        await save_session_if_credits_ok(page, context, email, password)
                                        return True
                                    else:
                                        log("Extension", "CONNECT_FAIL", email, f"Status: {status_text}")
                                        await save_session_if_credits_ok(page, context, email, password)
                                        return False
                                except Exception as ext_err:
                                    log("Extension", "ERROR", email, str(ext_err))
                                    await save_session_if_credits_ok(page, context, email, password)
                                    return False
                            else:
                                log("Extension", "NOT_FOUND", email)
                                await save_session_if_credits_ok(page, context, email, password)
                                return False
                        else:
                            # METODE INJEKSI LANGSUNG (Service Worker)
                            sw = None
                            # Wait for service worker to register
                            for _ in range(15):
                                for active_sw in context.service_workers:
                                    if "background.js" in active_sw.url:
                                        sw = active_sw
                                        break
                                if sw:
                                    break
                                await asyncio.sleep(1)
                                    
                            if sw:
                                try:
                                    endpoint = config.get("connect_endpoint", "https://api.genityboost.site/connect/account")
                                    # Evaluate doConnect inside service worker context
                                    js_code = """
                                    async ([endpoint, token]) => {
                                        try {
                                            return await doConnect(endpoint, token);
                                        } catch (e) {
                                            return { ok: false, error: e.message || String(e) };
                                        }
                                    }
                                    """
                                    connect_res = await sw.evaluate(js_code, [endpoint, connect_token])
                                    
                                    if connect_res.get("ok"):
                                        log("Extension", f"CONNECT_SUCCESS | Tokens: {connect_res.get('tokens')}", email)
                                        await save_session_if_credits_ok(page, context, email, password)
                                        return True
                                    else:
                                        out_data = connect_res.get("out") or {}
                                        server_msg = out_data.get("error") or out_data.get("message") or json.dumps(out_data)
                                        err_msg = f"Status: {connect_res.get('status')} | {server_msg}"
                                        log("Extension", "CONNECT_FAIL", email, err_msg)
                                        await save_session_if_credits_ok(page, context, email, password)
                                        return False
                                except Exception as ext_err:
                                    log("Extension", "ERROR", email, str(ext_err))
                                    await save_session_if_credits_ok(page, context, email, password)
                                    return False
                            else:
                                log("Extension", "NOT_FOUND", email)
                                await save_session_if_credits_ok(page, context, email, password)
                                return False
                    else:
                        log("Session", "NO_TOKEN", email)
                        return False
                except Exception as e:
                    log("Session", "ERROR", email, str(e))
                    return False
            else:
                log("Leonardo", "DASHBOARD_TIMEOUT", email)
                return False
        else:
            raise Exception("Timeout waiting for successful registration landing page")
            
    except Exception as e:
        log("Canva", "REGISTRATION_FAILED", email, str(e))
        return False
    finally:
        if context:
            try:
                await context.close()
            except:
                pass
            # Wait for browser to fully release locks
            await asyncio.sleep(2)

async def main():
    os.system("cls" if os.name == "nt" else "clear")
    
    # Unified execution log starter
    try:
        with open("bot_execution.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- START CANVA TEMPMAIL REGISTER BOT (LOOP MODE - 2 WORKERS) at {datetime.datetime.now()} ---\n")
    except:
        pass
        
    config = load_config()
    loop_delay = config.get("loop_delay", 10)
    max_accounts = config.get("max_accounts", 0)
    
    print("========================================")
    print("  BOT LEONARDO REGISTER LOOP (2 WORKERS)")
    print(f"  Delay between runs: {loop_delay}s")
    if max_accounts > 0:
        print(f"  Target: {max_accounts} accounts")
    else:
        print("  Target: Infinite loop (Ctrl+C to stop)")
    print("========================================\n")
    
    account_count = 0
    success_count = 0
    lock = asyncio.Lock()
    
    async def worker(worker_id, p):
        nonlocal account_count, success_count
        while True:
            async with lock:
                if max_accounts > 0 and account_count >= max_accounts:
                    break
                account_count += 1
                current_run = account_count
            
            print(f"\n--- [Worker {worker_id} | RUN #{current_run}] ---")
            
            # Get a temporary email
            email = generate_temp_email()
            if not email:
                log("Main", "ERROR", error="Failed to generate temporary email from Lisensify")
                print(f"[Worker {worker_id}] Waiting {loop_delay} seconds before retrying...")
                await asyncio.sleep(loop_delay)
                continue
                
            log("Main", f"START_REGISTRATION_RUN_{current_run} (Worker {worker_id})", email)
            
            try:
                success = await register_canva(p, email, config)
                async with lock:
                    if success:
                        success_count += 1
                        print(f"\n========================================\n[SUCCESS] RUN #{current_run} SUCCESSFUL (Worker {worker_id}): {email}\nTotal Success: {success_count}/{account_count}\n========================================")
                    else:
                        print(f"\n========================================\n[FAILED] RUN #{current_run} FAILED (Worker {worker_id}): {email}\nTotal Success: {success_count}/{account_count}\n========================================")
            except Exception as e:
                log("Main", "ERROR", error=str(e))
                print(f"[Worker {worker_id} | Run #{current_run}] crashed: {e}")
            
            print(f"\n[Worker {worker_id}] Waiting {loop_delay} seconds before the next run...")
            await asyncio.sleep(loop_delay)

    try:
        async with async_playwright() as p:
            tasks = [
                asyncio.create_task(worker(1, p)),
                asyncio.create_task(worker(2, p))
            ]
            await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n[WARNING] Loop stopped by user.")
        
    log("Main", "DONE", error=f"Total: {account_count}, Success: {success_count}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[WARNING] STOP")
    except Exception as e:
        print(f"[ERROR] {e}")
