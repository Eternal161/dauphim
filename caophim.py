import os
import re
import time
import json
import datetime
import requests
from github import Github
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# =========================================================
# CONFIG ROPHIM - BÓC MASTER M3U8 LẤY LINK MIXED.M3U8 CHUẨN
# =========================================================
TARGET_SITE   = "https://rophim10.co.com/the-loai/hoat-hinh"
FILE_PATH     = "phim.json"
LIMIT_MOVIES  = 20

VN_TZ = datetime.timezone(datetime.timedelta(hours=7))
GITHUB_TOKEN = os.getenv("GH_TOKEN")
REPO_NAME    = os.getenv("GH_REPO", "Eternal161/dauhoiquan") 

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://rophim10.co.com/"
}

JS_EXTRACT_MOVIES = """
() => {
    let results = [];
    let anchors = Array.from(document.querySelectorAll('a'));
    for (let a of anchors) {
        let href = a.href || '';
        if (!href.includes('/phim/') || href.includes('javascript:') || href.includes('#')) continue;
        
        let img = a.querySelector('img');
        if (!img) {
            let parent = a.parentElement;
            if (parent) img = parent.querySelector('img');
        }
        if (!img) continue; 
        
        let title = a.title || img.alt || a.innerText.trim() || 'Phim Hoạt Hình';
        let thumb = img.getAttribute('data-src') || img.src || '';
        
        let status = 'Full';
        let container = a.closest('div, li, article');
        if (container) {
            let statusEl = container.querySelector('.status, .episode, .label, .ep, span.badge');
            if (statusEl) status = statusEl.innerText.trim();
        }
        
        if (thumb && !results.find(x => x.href === href)) {
            results.push({ href, title: title.replace(/\\n/g, ' ').trim(), thumb, status });
        }
    }
    return results;
}
"""

JS_GET_EPS = """
() => {
    let eps = [];
    let links = document.querySelectorAll('a');
    for (let a of links) {
        let txt = a.innerText.trim();
        if (/^Tập\s*\d+/i.test(txt) && txt.length < 15) {
            if (a.href && !a.href.includes('javascript:')) {
                if (!eps.find(e => e.text === txt)) {
                    eps.push({text: txt, href: a.href});
                }
            }
        }
    }
    eps.sort((a, b) => {
        let matchA = a.text.match(/\d+/);
        let matchB = b.text.match(/\d+/);
        let numA = matchA ? parseInt(matchA[0]) : 0;
        let numB = matchB ? parseInt(matchB[0]) : 0;
        return numA - numB;
    });
    return eps;
}
"""

def clean_and_resolve_m3u8(u):
    if not u: return u
    # Lưỡi dao cạo sạch sẽ mọi dấu \, ", ' ở cuối link
    u = u.replace('\\', '').replace('"', '').replace("'", "").strip()
    
    # TUYỆT CHIÊU BÓC MASTER M3U8
    if "index.m3u8" in u.lower() and ("opstream" in u or "kkphim" in u):
        try:
            r = requests.get(u, headers=_HEADERS, timeout=5)
            if r.status_code == 200:
                # Đọc từng dòng trong file index.m3u8
                for line in r.text.split('\n'):
                    line = line.strip()
                    # Nếu dòng nào kết thúc bằng .m3u8 (ví dụ: 3000k/hls/mixed.m3u8) thì lấy
                    if line.endswith('.m3u8') and not line.startswith('#'):
                        base_url = u.rsplit('index.m3u8', 1)[0]
                        return base_url + line
        except:
            pass
    return u

def wait_and_extract_m3u8(page, streams):
    try: page.locator("text=/Xem Ngay|Xem Phim/i").first.click(timeout=1500)
    except: pass
    page.wait_for_timeout(1500)

    for _ in range(2):
        for frame in page.frames:
            try: 
                locator = frame.locator("video, .vjs-big-play-button, .jw-icon-display, body")
                if locator.count() > 0: locator.first.click(timeout=1000)
            except: pass
        page.wait_for_timeout(1500)
    
    deadline = time.time() + 8
    while time.time() < deadline:
        if streams: return clean_and_resolve_m3u8(streams[-1])
        time.sleep(1)
        
    m3u8_pattern = re.compile(r'(https?://[^\s"\'<>]*\.m3u8[^\s"\'<>]*)')
    try:
        found = m3u8_pattern.findall(page.content())
        if found: return clean_and_resolve_m3u8(found[-1])
    except: pass
    
    for frame in page.frames:
        try:
            found = m3u8_pattern.findall(frame.content())
            if found: return clean_and_resolve_m3u8(found[-1])
        except: pass
        
    return None

def scrape_and_push():
    now_str = datetime.datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
    print(f"🚀 BẮT ĐẦU BOT CÀO PHIM (Giờ VN): {now_str} - caophim.py:140")

    all_movies_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, user_agent=_HEADERS["User-Agent"])
        page = context.new_page()
        Stealth().apply_stealth_sync(page)
        page.on("popup", lambda p: p.close()) 
        
        print(f"📺 Đang mở trang: {TARGET_SITE} - caophim.py:151")
        try:
            page.goto(TARGET_SITE, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)
            for _ in range(4):
                page.mouse.wheel(0, 1500)
                page.wait_for_timeout(1000)
                
            raw_movies = page.evaluate(JS_EXTRACT_MOVIES)
            movies_list = raw_movies[:LIMIT_MOVIES]
            print(f"🎥 TÌM THẤY {len(movies_list)} PHIM. Bắt đầu xử lý...\n - caophim.py:161")
        except Exception as e:
            print(f"❌ Lỗi khi lấy danh sách phim: {e} - caophim.py:163")
            movies_list = []
        
        streams = []
        def process_url(url):
            url_clean = clean_and_resolve_m3u8(url)
            if (".m3u8" in url_clean.lower() and url_clean not in streams and "ad" not in url_clean.lower()):
                streams.append(url_clean)

        page.on("request", lambda req: process_url(req.url))
        page.on("response", lambda res: process_url(res.url))

        for idx, movie in enumerate(movies_list, 1):
            print(f"\n[{idx}/{len(movies_list)}] Đang xử lý: {movie['title']} - caophim.py:176")
            try:
                page.goto(movie['href'], wait_until="load", timeout=30000)
                page.wait_for_timeout(2000)
                
                try: page.locator("text=/Xem Ngay|Xem Phim/i").first.click(timeout=2000)
                except: pass
                page.wait_for_timeout(2000)

                eps = page.evaluate(JS_GET_EPS)

                if eps:
                    if len(eps) > 12:
                        print(f"⏭️ Bỏ qua vì phim có {len(eps)} tập (Lớn hơn 12). - caophim.py:189")
                        continue

                    print(f"👉 Phát hiện phim bộ có {len(eps)} tập. - caophim.py:192")
                    movie_eps_data = [] 
                    
                    for ep in eps:
                        streams.clear() 
                        try:
                            page.goto(ep['href'], wait_until="load", timeout=30000)
                            page.wait_for_timeout(2000)
                        except: pass
                        
                        link = wait_and_extract_m3u8(page, streams)
                        if link:
                            print(f"✅ Bắt thành công {ep['text']} > {link[:60]}... - caophim.py:204")
                            movie_eps_data.append({"text": ep['text'], "url": link})
                        else:
                            print(f"⚠️ Lỗi tải {ep['text']} - caophim.py:207")
                    
                    if movie_eps_data:
                        all_movies_data.append({
                            "title": movie['title'],
                            "status": f"Full {len(movie_eps_data)} Tập",
                            "thumb_url": movie['thumb'],
                            "episodes": movie_eps_data
                        })
                else:
                    streams.clear()
                    link = wait_and_extract_m3u8(page, streams)
                    if link:
                        print(f"👉 Phim lẻ. ✅ Tải thành công > {link[:60]}... - caophim.py:220")
                        all_movies_data.append({
                            "title": movie['title'],
                            "status": movie['status'],
                            "thumb_url": movie['thumb'],
                            "stream_url": link
                        })
                    else:
                        print("⚠️ Không tìm thấy link m3u8. - caophim.py:228")
                        
            except Exception as e:
                print(f"❌ Bỏ qua do lỗi: {e} - caophim.py:231")
                
        browser.close()

    print(f"\n🎉 HOÀN TẤT! Thu hoạch được {len(all_movies_data)} phim. - caophim.py:235")
    
    content = json.dumps({"movies": all_movies_data}, indent=2, ensure_ascii=False)
    
    if GITHUB_TOKEN:
        try:
            repo = Github(GITHUB_TOKEN).get_repo(REPO_NAME)
            msg = "🎬 Cập nhật Phim Hoạt Hình: " + now_str
            try:
                existing = repo.get_contents(FILE_PATH)
                repo.update_file(existing.path, msg, content, existing.sha)
                print(f"✅ Đã lưu thành công vào {REPO_NAME}/{FILE_PATH} - caophim.py:246")
            except:
                repo.create_file(FILE_PATH, msg, content)
                print(f"✅ Đã tạo mới file {FILE_PATH} trên GitHub! - caophim.py:249")
        except Exception as e:
            print(f"❌ Lỗi khi tải lên GitHub: {e} - caophim.py:251")
    else:
        with open(FILE_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Đã lưu cục bộ ra file {FILE_PATH} (Do không có GH_TOKEN) - caophim.py:255")

if __name__ == "__main__":
    scrape_and_push()
