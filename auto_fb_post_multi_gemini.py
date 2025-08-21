import os
import requests
from bs4 import BeautifulSoup
import json
import facebook
from datetime import datetime
import google.generativeai as genai

# ===== Khai báo môi trường =====
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FACEBOOK_ACCESS_TOKEN = os.environ.get("FACEBOOK_ACCESS_TOKEN")
FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID")

# 4 Trang web cần quét
URLS_TO_SCRAPE = [
    "https://dantri.com.vn/cong-nghe/ai-internet.html",
    
]

HISTORY_FILE = "posted_history.json"
DASHBOARD_FILE = "dashboard.json"

# ===== Khởi tạo Gemini SDK =====
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# =====Lịch sử bài đã đăng =====
def load_history():
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

# ===== Dashboard đơn giản =====
def update_dashboard(fb_id, url, snippet):
    dash = []
    try:
        with open(DASHBOARD_FILE, "r") as f:
            dash = json.load(f)
    except:
        pass
    dash.append({
        "fb_id": fb_id,
        "url": url,
        "snippet": snippet,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    with open(DASHBOARD_FILE, "w") as f:
        json.dump(dash, f, indent=2)

# ===== Quét bài từ từng trang =====
def get_posts(url):
    try:
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        # Lấy các thẻ bài viết phổ biến
        candidates = soup.find_all(["article", "div"], class_=lambda x: x and "post" in x.lower())
        history = load_history()
        posts = []
        for c in candidates:
            link = c.find("a")
            post_url = link['href'] if link and link.get('href') else None
            if not post_url or post_url in history:
                continue
            text = " ".join(p.get_text().strip() for p in c.find_all("p"))
            posts.append({"url": post_url, "text": text})
        return posts
    except Exception as e:
        print(f"Error crawling {url}:", e)
        return []

# ===== Tạo nội dung bằng Gemini =====
def gen_content(prompt):
    try:
        res = model.generate_content(prompt)
        return res.text
    except Exception as e:
        print("Gemini lỗi:", e)
        return None

def create_variants(text):
    short = gen_content(f"Tóm tắt nội dung sau thành bài Facebook ngắn, hấp dẫn: {text[:1000]}")
    long = gen_content(f"Tạo bài Facebook dài hơn, chi tiết, có hashtags: {text[:1500]}")
    return short, long

# ===== Đăng Facebook =====
def post_facebook(msg):
    graph = facebook.GraphAPI(FACEBOOK_ACCESS_TOKEN)
    try:
        post = graph.put_object(parent_object=FACEBOOK_PAGE_ID, connection_name='feed', message=msg)
        print("Đăng thành công, ID:", post.get("id"))
        return post.get("id")
    except Exception as e:
        print("Lỗi đăng FB:", e)
        return None

# ===== Quy trình chính =====
def run_auto():
    history = load_history()
    for url in URLS_TO_SCRAPE:
        posts = get_posts(url)
        for p in posts:
            short, long = create_variants(p["text"])
            final = long or short or p["text"][:300]
            fb_id = post_facebook(final)
            if fb_id:
                history.append(p["url"])
                save_history(history)
                update_dashboard(fb_id, p["url"], final[:100])

if __name__ == "__main__":
    run_auto()
