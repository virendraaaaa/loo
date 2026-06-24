import os
import json
import time
import sys
import random
import re
import datetime
import asyncio
import requests
import contextvars
import shutil

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Install: pip install playwright")
    sys.exit(1)

log_prefix_var = contextvars.ContextVar("log_prefix", default="")
email_lock = asyncio.Lock()
current_progress = ""

def log(action, status, email=None, error=None):
    """Logging function to session_check.log and console"""
    global current_progress
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    parts = [f"[{ts}]"]
    prefix = log_prefix_var.get()
    if not prefix:
        prefix = current_progress
    if prefix:
        parts.append(prefix)
    if email:
        parts.append(f"[{email}]")
    parts.append(f"{action} | {status}")
    if error:
        error_clean = str(error).replace("\r", "").replace("\n", " | ")
        parts.append(f"| {error_clean}")
        
    msg = " ".join(parts) + "\n"
    print(msg.rstrip())
    
    try:
        with open("session_check.log", "a", encoding="utf-8") as f:
            f.write(msg)
    except:
        pass

def play_success_sound():
    """Play success mp3 sound asynchronously using Windows winmm.dll"""
    if os.name == 'nt':
        try:
            import ctypes
            import random
            sound_path = os.path.abspath("jokowi-saya-akan-lawan.mp3")
            if os.path.exists(sound_path):
                alias_id = f"success_sound_{random.randint(1000, 9999)}"
                # Open
                ctypes.windll.winmm.mciSendStringW(f'open "{sound_path}" type mpegvideo alias {alias_id}', None, 0, 0)
                # Play
                ctypes.windll.winmm.mciSendStringW(f"play {alias_id}", None, 0, 0)
                
                # Auto-close after 20 seconds to free resources
                async def auto_close(alias):
                    await asyncio.sleep(20)
                    try:
                        import ctypes
                        ctypes.windll.winmm.mciSendStringW(f"close {alias}", None, 0, 0)
                    except:
                        pass
                asyncio.create_task(auto_close(alias_id))
        except:
            pass

def load_config():
    """Load config"""
    default_config = {
        "email_file": "email.txt",
        "login_url": "https://app.leonardo.ai/auth/login",
        "headless": False,
        "connect_endpoint": "https://api.genityboost.site/connect/account",
        "connect_token": "OIYJ3PHqi8lic_b52ARg2Os9",
        "direct_injection": False,
        "profile_dir": "D:/BotLeonardo_profiles"
    }
    if not os.path.exists("config.json"):
        return default_config
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            user_config = json.load(f)
            for k, v in default_config.items():
                if k not in user_config:
                    user_config[k] = v
            return user_config
    except:
        return default_config

def input_with_default(prompt, default_val):
    try:
        val = input(prompt).strip()
        return val if val else default_val
    except (EOFError, KeyboardInterrupt):
        return default_val
    except Exception:
        return default_val

def parse_emails():
    """Parse email.txt into {username_prefix: (full_email, password)}"""
    emails_map = {}
    if os.path.exists("email.txt"):
        try:
            with open("email.txt", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or ":" not in line:
                        continue
                    email, pwd = line.split(":", 1)
                    prefix = email.split("@")[0].lower()
                    emails_map[prefix] = (email, pwd)
        except Exception as e:
            print(f"Error reading email.txt: {e}")
    return emails_map

async def check_single_account(p, email, password, cookies_path, config):
    """Check Canva session, Leonardo login, onboarding, credit, and link extension"""
    email_user = email.split("@")[0]
    profile_dir_config = config.get("profile_dir", "")
    if profile_dir_config:
        os.makedirs(profile_dir_config, exist_ok=True)
        temp_dir = os.path.join(profile_dir_config, f"check_profile_{email_user}")
    else:
        temp_dir = os.path.abspath(f"check_profile_{email_user}")
        
    path_to_extension = os.path.abspath("leonardo-connect")
    if not os.path.exists(path_to_extension):
        path_to_extension = os.path.abspath("leonardo-connect-extension")
        
    log("Playwright", "START_BROWSER", email, f"Profile: {temp_dir}")
    
    # Ensure any previous locked directory is cleaned
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
        
    context = None
    try:
        # Load the cookies from file
        if not os.path.exists(cookies_path):
            return {"status": "NO_COOKIES_FILE", "canva": "ERROR", "leonardo": "ERROR"}
            
        with open(cookies_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
            
        # Launch persistent context
        is_headless = config.get("headless", False)
        launch_args = [
            "--start-maximized",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            f"--disable-extensions-except={path_to_extension}",
            f"--load-extension={path_to_extension}",
        ]
        if is_headless:
            launch_args.append("--headless=new")

        context = await p.chromium.launch_persistent_context(
            user_data_dir=temp_dir,
            headless=False,
            viewport=None,
            ignore_https_errors=True,
            args=launch_args
        )
        
        await context.add_cookies(cookies)
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Step A: Check Canva Session
        log("Canva", "VERIFY_SESSION", email)
        try:
            await page.goto("https://www.canva.com/settings/your-account", wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)
        except Exception as e:
            log("Canva", "GOTO_FAIL", email, str(e))
            
        # Detect if we are logged in to Canva
        url = page.url
        canva_ok = False
        if "canva.com" in url and "login" not in url and "signup" not in url:
            # We are on settings page or dashboard, which means Canva session is active
            canva_ok = True
            log("Canva", "SESSION_VALID", email)
        else:
            # Check if login buttons are present
            login_btn = await page.query_selector("button:has-text('Log in'), button:has-text('Masuk'), button:has-text('Sign up')")
            if not login_btn:
                # Fallback: maybe just settings page load succeeded?
                # Check for settings headings
                settings_header = await page.query_selector("text=Account settings, text=Pengaturan akun, text=Your details")
                if settings_header:
                    canva_ok = True
                    log("Canva", "SESSION_VALID (Header detected)", email)
                    
        if not canva_ok:
            log("Canva", "SESSION_EXPIRED", email, f"URL: {url}")
            return {"status": "CANVA_EXPIRED", "canva": "EXPIRED", "leonardo": "SKIPPED"}
            
        # Step B: Authenticate with Leonardo via Canva
        log("Leonardo", "START_AUTH", email)
        try:
            await page.goto(config["login_url"], wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(3)
        except Exception as e:
            log("Leonardo", "GOTO_FAIL", email, str(e))
            return {"status": "LEONARDO_GOTO_FAIL", "canva": "OK", "leonardo": "ERROR"}
            
        # Check if already logged in to Leonardo
        url = page.url
        logged_in = False
        
        # We loop to authorize or handle redirects
        for attempt in range(15):
            url = page.url
            if "leonardo.ai" in url and "login" not in url and "auth" not in url:
                logged_in = True
                break
                
            # If on Leonardo login page, click Canva button
            if "leonardo.ai" in url and ("login" in url or "auth" in url):
                canva_btn = None
                try:
                    canva_btn = await page.query_selector("xpath=//button[.//span[text()='Canva']]")
                    if not canva_btn:
                        canva_btn = await page.query_selector("button:has-text('Canva')")
                    if canva_btn and await canva_btn.is_visible():
                        log("Leonardo", "CLICKING_CANVA_BUTTON", email)
                        await canva_btn.click()
                        await asyncio.sleep(4)
                except Exception as click_err:
                    log("Leonardo", "CANVA_CLICK_ERR", email, str(click_err))
                    
            # If on Canva authorize page, click Allow
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
                    
            await asyncio.sleep(2)
            
        if not logged_in:
            log("Leonardo", "AUTH_FAILED", email, f"Final URL: {page.url}")
            return {"status": "LEONARDO_AUTH_FAILED", "canva": "OK", "leonardo": "FAILED"}
            
        log("Leonardo", "LOGIN_SUCCESS", email)
        
        # Step C: Onboarding modal handling
        log("Leonardo", "START_ONBOARDING_CHECK", email)
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
        
        while time.time() - start_time < 90:
            try:
                # Agree terms checkboxes
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
                    
                # Click onboarding buttons
                clicked_modal = False
                for selector in modal_selectors:
                    try:
                        btn = page.locator(selector).first
                        if await btn.is_visible():
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
                    
                # Check if we are idle and onboarding is complete
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
            
        if not leo_ready:
            log("Leonardo", "ONBOARDING_TIMEOUT_OR_DASHBOARD_MISSING", email)
            
        # Step D: Poll credits/tokens using graphql
        log("Leonardo", "POLLING_CREDITS", email)
        total_tokens = 0
        plan = "UNKNOWN"
        try:
            session_info = await page.evaluate("""
                fetch("https://app.leonardo.ai/api/auth/get-session", {
                    headers: { Accept: "application/json" },
                    credentials: "include"
                }).then(r => r.json()).then(d => ({
                    token: d.session?.accessToken || null
                })).catch(e => ({}))
            """)
            token = session_info.get("token")
            if token:
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
                plan = credits_info.get("plan", "FREE")
                log("Result", f"CREDIT_CHECK | Plan: {plan} | Tokens: {total_tokens}", email)
            else:
                log("Result", "NO_ACCESS_TOKEN", email)
        except Exception as cred_err:
            log("Result", "CREDIT_CHECK_ERROR", email, str(cred_err))
            
        # Step E: Link/Inject extension
        log("Extension", "START_LINK", email)
        extension_linked = "SKIPPED"
        try:
            result = await page.evaluate("""
                fetch("https://app.leonardo.ai/api/auth/get-session", {
                    headers: { Accept: "application/json" },
                    credentials: "include"
                }).then(r => r.json()).then(d => ({
                    token: d.session?.accessToken ? true : false
                })).catch(e => ({}))
            """)
            
            if result.get("token"):
                connect_token = config.get("connect_token", "OIYJ3PHqi8lic_b52ARg2Os9")
                
                if not config.get("direct_injection", True):
                    # Visual Extension Popup Method
                    extension_id = None
                    for _ in range(15):
                        for sw in context.service_workers:
                            if "background.js" in sw.url:
                                extension_id = sw.url.split("/")[2]
                                break
                        if extension_id:
                            break
                        await asyncio.sleep(1)
                        
                    if extension_id:
                        ext_page = await context.new_page()
                        await ext_page.goto(f"chrome-extension://{extension_id}/popup.html")
                        await ext_page.wait_for_selector("#ctoken", timeout=5000)
                        await asyncio.sleep(1.5)
                        await ext_page.fill("#ctoken", connect_token)
                        await asyncio.sleep(0.3)
                        await ext_page.click("#btn")
                        
                        status_text = ""
                        connected = False
                        for _ in range(25):
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
                            extension_linked = "CONNECTED"
                            play_success_sound()
                        else:
                            log("Extension", "CONNECT_FAIL", email, f"Status: {status_text}")
                            extension_linked = f"FAILED ({status_text.strip()})"
                    else:
                        log("Extension", "NOT_FOUND", email)
                        extension_linked = "EXTENSION_NOT_FOUND"
                else:
                    # Direct Injection Method
                    sw = None
                    for _ in range(15):
                        for active_sw in context.service_workers:
                            if "background.js" in active_sw.url:
                                sw = active_sw
                                break
                        if sw:
                            break
                        await asyncio.sleep(1)
                        
                    if sw:
                        endpoint = config.get("connect_endpoint", "https://api.genityboost.site/connect/account")
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
                            extension_linked = "CONNECTED"
                            play_success_sound()
                        else:
                            out_data = connect_res.get("out") or {}
                            server_msg = out_data.get("error") or out_data.get("message") or json.dumps(out_data)
                            err_msg = f"Status: {connect_res.get('status')} | {server_msg}"
                            log("Extension", "CONNECT_FAIL", email, err_msg)
                            extension_linked = f"FAILED ({err_msg})"
                    else:
                        log("Extension", "NOT_FOUND", email)
                        extension_linked = "EXTENSION_NOT_FOUND"
            else:
                log("Session", "NO_TOKEN", email)
                extension_linked = "NO_LEONARDO_TOKEN"
        except Exception as ext_err:
            log("Extension", "LINK_ERROR", email, str(ext_err))
            extension_linked = f"ERROR ({str(ext_err)})"
            
        return {
            "status": "SUCCESS",
            "canva": "OK",
            "leonardo": "OK",
            "plan": plan,
            "tokens": total_tokens,
            "extension": extension_linked
        }
        
    except Exception as e:
        log("Process", "ERROR", email, str(e))
        return {"status": f"PROCESS_ERROR ({str(e)})", "canva": "ERROR", "leonardo": "ERROR"}
        
    finally:
        if context:
            try:
                await context.close()
            except:
                pass
            await asyncio.sleep(2)
            
        # Clean up check profiles
        if config.get("delete_temp_profiles", True):
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    log("Cleanup", f"Deleted check profile: {temp_dir}", email)
            except Exception as clean_err:
                log("Cleanup", f"Failed to delete check profile: {str(clean_err)}", email)

async def check_worker(queue, worker_id, runtime_config, emails_map, results_list):
    """Worker coroutine to process queue of cookie files"""
    while not queue.empty():
        try:
            cookies_file = await queue.get()
        except asyncio.QueueEmpty:
            break
        except Exception:
            break
            
        cookies_path = os.path.join("cookies", cookies_file)
        m = re.search(r"cookies_(.+)\.json$", cookies_file)
        if not m:
            queue.task_done()
            continue
            
        email_prefix = m.group(1).lower()
        email, password = emails_map.get(email_prefix, (None, None))
        if not email:
            email = f"{email_prefix}@unknown.com"
            password = "qwerty123"
            
        log_prefix_var.set(f"[Worker {worker_id} | {email_prefix}]")
        log("Checker", "START_CHECK", email)
        
        config = load_config()
        config["delete_temp_profiles"] = runtime_config.get("delete_temp_profiles", True)
        config["headless"] = runtime_config.get("headless", False)
        
        try:
            async with async_playwright() as p:
                res = await check_single_account(p, email, password, cookies_path, config)
                res["email"] = email
                res["file"] = cookies_file
                results_list.append(res)
                
                print(f"\n========================================\n"
                      f"CHECK RESULT: {email}\n"
                      f"Canva Sesi: {res.get('canva')}\n"
                      f"Leonardo Sesi: {res.get('leonardo')}\n"
                      f"Kredit: {res.get('tokens', 0)} ({res.get('plan', 'UNKNOWN')})\n"
                      f"Link GenityBoost: {res.get('extension', 'SKIPPED')}\n"
                      f"========================================\n")
                
                # Delete cookies file if requested
                if runtime_config.get("delete_cookies", False):
                    try:
                        if os.path.exists(cookies_path):
                            os.remove(cookies_path)
                            log("Cleanup", f"Deleted cookies file: {cookies_path}", email)
                    except Exception as cookie_del_err:
                        log("Cleanup", f"Failed to delete cookies file: {str(cookie_del_err)}", email)
        except Exception as e:
            log("Checker", "WORKER_ERROR", email, str(e))
            results_list.append({
                "email": email,
                "file": cookies_file,
                "status": f"FATAL_ERROR ({str(e)})",
                "canva": "ERROR",
                "leonardo": "ERROR"
            })
            
        queue.task_done()
        await asyncio.sleep(5)

async def main():
    os.system("cls" if os.name == "nt" else "clear")
    
    config = load_config()
    
    print(f"\n========================================\n  BOT LEONARDO COOKIE SESSION CHECKER\n========================================\n")
    
    # 1. Parse emails
    emails_map = parse_emails()
    print(f"Loaded {len(emails_map)} account credentials from email.txt\n")
    
    # 2. Scan cookies folder
    cookies_dir = "cookies"
    if not os.path.exists(cookies_dir):
        print(f"[ERROR] Folder 'cookies' tidak ditemukan di workspace.")
        return
        
    all_files = [f for f in os.listdir(cookies_dir) if f.startswith("cookies_") and f.endswith(".json")]
    print(f"Ditemukan {len(all_files)} file cookies di folder '{cookies_dir}'\n")
    
    if not all_files:
        print("[WARNING] Tidak ada file cookies yang dapat diperiksa.")
        return
        
    # 3. Prompt user
    num_workers_str = input_with_default("Masukkan jumlah worker/sesi paralel yang ingin dijalankan (default: 1): ", "1")
    try:
        num_workers = int(num_workers_str)
    except:
        num_workers = 1
        
    cleanup_str = input_with_default("Apakah ingin menghapus profil temp browser setelah selesai? (y/n) (default: y): ", "y").lower()
    delete_temp_profiles = cleanup_str != 'n'
    
    delete_cookies_str = input_with_default("Apakah ingin menghapus file cookies (.json) setelah dicek? (y/n) (default: n): ", "n").lower()
    delete_cookies = delete_cookies_str == 'y'
    
    default_headless = "y" if config.get("headless", False) else "n"
    headless_str = input_with_default(f"Apakah ingin menjalankan browser secara headless (tanpa visual)? (y/n) (default: {default_headless}): ", default_headless).lower()
    headless_mode = headless_str == 'y'
    
    runtime_config = {
        "delete_temp_profiles": delete_temp_profiles,
        "delete_cookies": delete_cookies,
        "headless": headless_mode
    }
    
    results_list = []
    
    # Start log
    try:
        with open("session_check.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- START COOKIES CHECKING at {datetime.datetime.now()} ---\n")
    except:
        pass
        
    # Queue
    queue = asyncio.Queue()
    for f in all_files:
        await queue.put(f)
        
    # Spawn workers
    workers = []
    for i in range(1, num_workers + 1):
        task = asyncio.create_task(check_worker(queue, i, runtime_config, emails_map, results_list))
        workers.append(task)
        await asyncio.sleep(3)
        
    await asyncio.gather(*workers)
    
    # 4. Generate report summary
    report_path = "session_check_results.txt"
    try:
        success_count = sum(1 for r in results_list if r.get("status") == "SUCCESS")
        canva_ok = sum(1 for r in results_list if r.get("canva") == "OK")
        canva_expired = sum(1 for r in results_list if r.get("canva") == "EXPIRED")
        leonardo_connected = sum(1 for r in results_list if r.get("extension") == "CONNECTED")
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"========================================\n")
            f.write(f"  LAPORAN PENGECEKAN SESI COOKIES\n")
            f.write(f"  Tanggal: {datetime.datetime.now()}\n")
            f.write(f"========================================\n\n")
            
            f.write(f"Statistik Ringkas:\n")
            f.write(f"Total Cookies Diperiksa : {len(results_list)}\n")
            f.write(f"Sesi Canva OK           : {canva_ok}\n")
            f.write(f"Sesi Canva Expired      : {canva_expired}\n")
            f.write(f"Terhubung GenityBoost   : {leonardo_connected}\n\n")
            
            f.write(f"Detail Akun:\n")
            f.write(f"{'Email':<45} | {'Canva':<10} | {'Leonardo':<10} | {'Kredit':<8} | {'GenityBoost':<25} | {'Status':<25}\n")
            f.write(f"{'-'*45}-|-{'-'*10}-|-{'-'*10}-|-{'-'*8}-|-{'-'*25}-|-{'-'*25}\n")
            for r in results_list:
                f.write(f"{r.get('email', ''):<45} | "
                        f"{r.get('canva', ''):<10} | "
                        f"{r.get('leonardo', ''):<10} | "
                        f"{str(r.get('tokens', 0)):<8} | "
                        f"{r.get('extension', ''):<25} | "
                        f"{r.get('status', ''):<25}\n")
                        
        print(f"\n========================================")
        print(f"PENGECEKAN SELESAI!")
        print(f"Laporan ringkas disimpan ke: {report_path}")
        print(f"Total Canva Sesi OK: {canva_ok} | Expired: {canva_expired}")
        print(f"========================================\n")
    except Exception as rep_err:
        print(f"Gagal menulis laporan summary: {rep_err}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[WARNING] Pengecekan dihentikan oleh pengguna.")
    except Exception as e:
        print(f"[ERROR] {e}")
