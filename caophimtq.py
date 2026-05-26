import json
import base64
import requests
from playwright.sync_api import sync_playwright

# === CẤU HÌNH THÔNG TIN ===
LINK_PHIM = "https://hhtq.ee/kiem-hiep/dau-la-dai-luc"
TEN_PHIM = "Đấu La Đại Lục"
ANH_BIA = "https://hhtq.ee/wp-content/uploads/2023/04/dau-la-dai-luc.jpg" 

# 💡 Selector chuẩn xác được trích xuất từ ảnh F12 của Dậu
SELECTOR_KHOI_TAP = ".halim-episode a" 

# === CẤU HÌNH GITHUB CỦA DẬU ===
GITHUB_TOKEN = os.getenv("GH_TOKEN")
REPO_NAME = os.getenv("GH_REPO", "Eternal161/dauphim")
FILE_PATH = "phim.json"

def lay_m3u8(page, url_tap):
    link_m3u8 = ""

    def handle_request(request):
        nonlocal link_m3u8
        # Bắt link m3u8 gốc
        if "m3u8" in request.url:
            link_m3u8 = request.url

    page.on("request", handle_request)
    
    try:
        page.goto(url_tap, wait_until="domcontentloaded", timeout=30000)
        
        # 1. Đợi 2 giây
        page.wait_for_timeout(2000) 
        
        # 2. Ấn nút play giữa màn hình (viewport mặc định 1280x720 -> giữa là 640x360)
        print("    🖱️ Đang click giữa màn hình để gọi m3u8...", end="")
        page.mouse.click(640, 360)
        
        # 3. Đợi thêm 4 giây cho player nhả link
        page.wait_for_timeout(4000)
        
    except Exception as e:
        print(f" Lỗi: {e}")
    finally:
        page.remove_listener("request", handle_request)

    return link_m3u8

def day_len_github(phim_moi):
    url_api = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    print("\n☁️ Đang kết nối với kho GitHub để cập nhật...")
    
    # BƯỚC 1: Kéo file phim.json hiện tại về
    response = requests.get(url_api, headers=headers)
    sha = ""
    data_hien_tai = {"movies": []}
    
    if response.status_code == 200:
        res_json = response.json()
        sha = res_json['sha'] 
        content_goc = base64.b64decode(res_json['content']).decode('utf-8')
        try:
            data_hien_tai = json.loads(content_goc)
        except:
            pass
            
    movies = data_hien_tai.get("movies", [])
    
    # BƯỚC 2: Kiểm tra trùng lặp và ghi đè
    da_ton_tai = False
    for m in movies:
        if m.get("title") == phim_moi["title"]:
            m["episodes"] = phim_moi["episodes"]
            m["status"] = phim_moi["status"]
            da_ton_tai = True
            break
            
    if not da_ton_tai:
        movies.append(phim_moi)
        
    data_hien_tai["movies"] = movies
    
    # BƯỚC 3: Push lên lại
    noi_dung_moi = json.dumps(data_hien_tai, ensure_ascii=False, indent=4)
    noi_dung_encoded = base64.b64encode(noi_dung_moi.encode('utf-8')).decode('utf-8')
    
    payload = {
        "message": f"🤖 Auto update phim: {phim_moi['title']} ({len(phim_moi['episodes'])} tập)",
        "content": noi_dung_encoded
    }
    if sha:
        payload["sha"] = sha
        
    put_response = requests.put(url_api, headers=headers, json=payload)
    
    if put_response.status_code in [200, 201]:
        print("✅ PUSH THÀNH CÔNG! Mở app Sáng TV lên xem ngay thôi!")
    else:
        print(f"❌ Lỗi Push GitHub: {put_response.text}")

def chay_tool():
    tap_phim_tong_hop = []
    
    with sync_playwright() as p:
        print(f"🚀 Bắt đầu cào bộ: {TEN_PHIM}")
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-web-security"]) 
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()
        
        try:
            page.goto(LINK_PHIM, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000) 
            
            cac_the_tap = page.locator(SELECTOR_KHOI_TAP).all()
            danh_sach_link_html = []
            
            # Quét danh sách HTML
            for the in cac_the_tap:
                # Ưu tiên lấy thuộc tính title (Vd: "Tập 2"), nếu không có mới lấy text_content
                ten = the.get_attribute("title")
                if not ten:
                    ten = the.text_content().strip()
                
                link = the.get_attribute("href")
                
                if link and "html" in link.lower():
                    ten_dep = f"Tập {ten}" if ten.isdigit() else ten
                    danh_sach_link_html.append({"ten": ten_dep, "url": link})
            
            # Xóa các link trùng lặp để phòng hờ web thiết kế 2 nút ấn cùng trỏ về 1 link
            danh_sach_link_html = list({v['url']:v for v in danh_sach_link_html}.values())
            
            print(f"✅ Quét thấy {len(danh_sach_link_html)} tập. Chuẩn bị đục khoét m3u8...\n")
            
            for i, tap in enumerate(danh_sach_link_html, 1):
                print(f"⏳ {tap['ten']} ({i}/{len(danh_sach_link_html)})...", end="")
                link_m3u8 = lay_m3u8(page, tap["url"])
                
                if link_m3u8:
                    print(" 🎯 Xong!")
                    tap_phim_tong_hop.append({
                        "text": tap["ten"],
                        "url": link_m3u8
                    })
                else:
                    print(" ⚠️ Không tìm thấy link!")
                    
        except Exception as e:
            print(f"❌ Vấp cỏ: {e}")
            
        browser.close()
        
    if tap_phim_tong_hop:
        phim_moi = {
            "title": TEN_PHIM,
            "thumb_url": ANH_BIA,
            "status": f"Full {len(tap_phim_tong_hop)} Tập",
            "episodes": tap_phim_tong_hop
        }
        day_len_github(phim_moi)
    else:
        print("\n⚠️ Chuyến đi trắng tay, không có gì để đẩy lên GitHub.")

if __name__ == "__main__":
    chay_tool()
