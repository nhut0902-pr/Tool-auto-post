import requests
from bs4 import BeautifulSoup
import json
import openai
import facebook
import os
from datetime import datetime

# ====== Lấy key từ environment ======
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FACEBOOK_ACCESS_TOKEN = os.environ.get("FACEBOOK_ACCESS_TOKEN")
FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID")
URL_TO_SCRAPE = "https://dantri.com.vn/cong-nghe/ai-internet.htm"  # Thay bằng trang web của bạn
HISTORY_FILE = "posted_history.json"
DASHBOARD_FILE = "dashboard.json"

openai.api_key = GEMINI_API_KEY

# ====== Lịch sử bài đã đăng ======
def load_history():
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

# ====== Mini-dashboard ======
def update_dashboard(post_id, url, message):
    dashboard = []
    try:
        with open(DASHBOARD_FILE, "r") as f:
            dashboard = json.load(f)
    except:
        pass
    dashboard.append({
        "facebook_id": post_id,
        "url": url,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "snippet": message[:100]
    })
    with open(DASHBOARD_FILE, "w") as f:
        json.dump(dashboard, f, indent=2)

# ====== Lấy nhiều bài mới từ web ======
def get_all_posts(url):
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.find_all("article")  # Hoặc div class="post"
    
    posts = []
    history = load_history()
    
    for article in articles:
        link_tag = article.find("a")
        post_url = link_tag['href'] if link_tag else None
        if not post_url or post_url in history:
            continue
        
        text = article.get_text(separator="\n").strip()
        imgs = [img['src'] for img in article.find_all("img") if img.get('src')]
        videos = [video['src'] for video in article.find_all("video") if video.get('src')]
        posts.append({
            "url": post_url,
            "text": text,
            "images": imgs,
            "videos": videos
        })
    return posts

# ====== Chọn hình ảnh/video đẹp nhất ======
def choose_best_media(img_urls, video_urls):
    best_img = None
    max_size = 0
    for url in img_urls:
        try:
            r = requests.get(url, stream=True, timeout=5)
            size = int(r.headers.get('Content-Length', 0))
            if size > max_size:
                max_size = size
                best_img = url
        except:
            continue
    best_video = video_urls[0] if video_urls else None
    return best_img, best_video

# ====== Tạo nội dung đa dạng bằng Gemini ======
def generate_post(prompt):
    try:
        response = openai.chat.completions.create(
            model="gemini-1.5-t",
            messages=[
                {"role": "system", "content": "Bạn là chuyên gia viết nội dung Facebook hấp dẫn, ngắn gọn, thu hút người đọc."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message["content"]
    except Exception as e:
        print("Lỗi Gemini:", e)
        return None

def generate_post_versions(text):
    prompt_short = f"Tóm tắt nội dung sau thành bài Facebook ngắn, thu hút: {text[:1000]}"
    prompt_long = f"Tạo bài Facebook dài hơn, chi tiết, kèm hashtags: {text[:1500]}"
    
    short_post = generate_post(prompt_short)
    long_post = generate_post(prompt_long)
    
    return short_post, long_post

# ====== Đăng bài lên Facebook ======
def post_to_facebook(message, img_url=None, video_url=None):
    graph = facebook.GraphAPI(FACEBOOK_ACCESS_TOKEN)
    try:
        if video_url:
            # Facebook hỗ trợ video từ URL hoặc upload, ở đây dùng URL
            post = graph.put_video(video=open(video_url, "rb"), title=message[:50], description=message)
        elif img_url:
            img_data = requests.get(img_url).content
            post = graph.put_photo(image=img_data, message=message)
        else:
            post = graph.put_object(parent_object=FACEBOOK_PAGE_ID, connection_name='feed', message=message)
        print("Đã đăng bài! ID:", post.get("id"))
        return post.get("id")
    except Exception as e:
        print("Lỗi đăng bài Facebook:", e)
        return None

# ====== Quy trình auto post ======
def auto_post(url):
    posts = get_all_posts(url)
    if not posts:
        print("Không có bài mới để đăng.")
        return
    
    history = load_history()
    
    for post in posts:
        best_img, best_video = choose_best_media(post['images'], post['videos'])
        short_post, long_post = generate_post_versions(post['text'])
        final_post = long_post or short_post or post['text'][:500]  # fallback
        
        post_id = post_to_facebook(final_post, best_img, best_video)
        if post_id:
            history.append(post['url'])
            save_history(history)
            update_dashboard(post_id, post['url'], final_post)

if __name__ == "__main__":
    auto_post(URL_TO_SCRAPE)
