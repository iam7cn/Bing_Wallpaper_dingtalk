import requests
import json
import os
from pathlib import Path

# 从环境变量读取钉钉Webhook（适配GitHub Actions）
DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK", "")

def fetch_bing_wallpaper_batch(api_urls):
    """批量爬取指定必应壁纸API接口的数据"""
    all_new_data = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    for idx, api_url in enumerate(api_urls, 1):
        print(f"正在爬取第 {idx} 个必应壁纸接口: {api_url}")
        try:
            response = requests.get(api_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            # 提取有效壁纸数据（含copyrightlink）
            for img_info in data.get("images", []):
                if img_info.get("urlbase") and img_info.get("enddate"):
                    img_url = f'https://cn.bing.com{img_info["urlbase"]}_UHD.jpg'
                    new_item = {
                        "enddate": img_info.get("enddate", ""),
                        "url": img_url,
                        "copyright": img_info.get("copyright", ""),
                        "copyrightlink": img_info.get("copyrightlink", "")  # 保留详情链接
                    }
                    all_new_data.append(new_item)
        except requests.exceptions.RequestException as e:
            print(f"爬取接口 {api_url} 出错: {e}")
            continue
        except json.JSONDecodeError as e:
            print(f"解析接口 {api_url} JSON数据出错: {e}")
            continue
    return all_new_data

def download_bing_wallpaper(img_data):
    """
    下载壁纸图片到Bing_Wallpaper/年份 目录，按指定规则命名
    return: True=本次新下载，False=已存在未下载/下载失败
    """
    # GitHub Actions运行时使用工作目录，无需特殊处理
    base_dir = Path("Bing_Wallpaper")
    enddate = img_data["enddate"]
    year = enddate[:4] if len(enddate) >= 4 else "unknown"
    target_dir = base_dir / year
    target_dir.mkdir(parents=True, exist_ok=True)
    # 图片命名：enddate_zh-cn_UHD.jpg
    img_name = f"{enddate}_zh-cn_UHD.jpg"
    img_path = target_dir / img_name
    # 跳过已下载的图片，返回False标记
    if img_path.exists():
        print(f"图片 {img_name} 已存在，跳过下载")
        return False
    # 流式下载图片，返回True标记为新下载
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        print(f"正在下载: {img_data['url']} -> {img_path}")
        response = requests.get(img_data["url"], headers=headers, timeout=30, stream=True)
        response.raise_for_status()
        with open(img_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"下载完成: {img_path}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"下载图片 {img_name} 失败: {e}")
        return False

def get_hitokoto():
    """
    从https://v1.hitokoto.cn/获取今日一言信息
    return: 一言文本+来源的组合字典，含hitokoto/from
    """
    hitokoto_url = "https://v1.hitokoto.cn/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        print(f"\n正在获取今日一言: {hitokoto_url}")
        response = requests.get(hitokoto_url, headers=headers, timeout=10)
        response.raise_for_status()
        hitokoto_data = response.json()
        # 提取一言文本和来源，做兜底处理
        hitokoto_text = hitokoto_data.get("hitokoto", "今日一言获取失败")
        hitokoto_from = hitokoto_data.get("from", "未知来源")
        print(f"今日一言获取成功: 『{hitokoto_text}』- {hitokoto_from}")
        return {
            "hitokoto": hitokoto_text,
            "from": hitokoto_from
        }
    except requests.exceptions.RequestException as e:
        print(f"获取今日一言出错: {e}")
        return {"hitokoto": "今日一言获取失败", "from": "未知来源"}
    except json.JSONDecodeError as e:
        print(f"解析今日一言JSON出错: {e}")
        return {"hitokoto": "今日一言获取失败", "from": "未知来源"}

def send_single_to_dingtalk(img_data, hitokoto_info):
    """
    按指定emoji格式，将单条新下载壁纸信息+今日一言推送到钉钉
    :param hitokoto_info: 一言字典，含hitokoto/from
    """
    # 检查Webhook是否为空
    if not DINGTALK_WEBHOOK:
        print("钉钉Webhook未配置，跳过推送")
        return
    
    # 提取壁纸所有字段，做兜底处理
    enddate = img_data.get("enddate", "未知日期")
    url = img_data.get("url", "未知地址")
    copyright = img_data.get("copyright", "未知版权")
    copyrightlink = img_data.get("copyrightlink", "未知链接")
    # 按指定格式拼接内容，含emoji、详情链接、一言特殊格式
    send_content = f"""📢 {enddate} bing壁纸已下载更新！
📷 壁纸地址：{url}
📝 版权信息：{copyright}
🔗 详情: {copyrightlink}

💬 今日一言：『{hitokoto_info['hitokoto']}』- {hitokoto_info['from']}"""
    # 钉钉机器人推送格式（text类型，支持emoji和换行）
    dingtalk_data = {
        "msgtype": "text",
        "text": {
            "content": send_content
        }
    }
    headers = {
        "Content-Type": "application/json;charset=utf-8"
    }
    try:
        print(f"正在推送【{enddate}】的壁纸信息到钉钉...")
        response = requests.post(DINGTALK_WEBHOOK, headers=headers, json=dingtalk_data, timeout=15)
        response.raise_for_status()
        result = response.json()
        if result.get("errcode") == 0:
            print(f"【{enddate}】壁纸信息推送成功！")
        else:
            print(f"【{enddate}】壁纸信息推送失败: 错误码{result.get('errcode')}，错误信息{result.get('errmsg')}")
    except requests.exceptions.RequestException as e:
        print(f"【{enddate}】壁纸信息推送网络出错: {e}")
    except json.JSONDecodeError as e:
        print(f"【{enddate}】解析钉钉返回JSON出错: {e}")

def main():
    """主函数：全流程执行（指定emoji格式推送+仅新壁纸推送）"""
    # 1. 定义基础目录和文件路径（bing.json放在Bing_Wallpaper下）
    base_dir = Path("Bing_Wallpaper")
    base_dir.mkdir(parents=True, exist_ok=True)  # 确保Bing_Wallpaper目录存在
    json_file = base_dir / "bing.json"  # 核心修改：JSON文件路径指向Bing_Wallpaper
    
    # 2. 定义必应壁纸API列表（先idx=8，后idx=0）
    bing_api_urls = [
        "https://cn.bing.com/HPImageArchive.aspx?format=js&idx=8&n=8",
        "https://cn.bing.com/HPImageArchive.aspx?format=js&idx=0&n=8"
    ]
    # 存储本次新下载的壁纸数据，仅推送这些
    new_downloaded_data = []

    # 3. 批量爬取壁纸数据
    new_bing_data = fetch_bing_wallpaper_batch(bing_api_urls)
    if not new_bing_data:
        print("未爬取到任何必应壁纸数据，程序终止")
        return

    # 4. 读取原有数据+合并去重+按日期升序排序
    old_bing_data = []
    if os.path.exists(json_file):
        with open(json_file, "r", encoding="utf-8") as f:
            try:
                old_bing_data = json.load(f)
            except json.JSONDecodeError:
                print("原有JSON文件损坏，将清空重新保存")
                old_bing_data = []
    # 按enddate去重
    bing_dict = {item["enddate"]: item for item in old_bing_data}
    for item in new_bing_data:
        bing_dict[item["enddate"]] = item
    # 升序排序（新日期在下）
    final_bing_data = sorted(bing_dict.values(), key=lambda x: x["enddate"])

    # 5. 保存最新JSON数据（到Bing_Wallpaper/bing.json）
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(final_bing_data, f, ensure_ascii=False, indent=4)
    print(f"\nJSON数据已更新保存: {json_file}，累计{len(final_bing_data)}条壁纸")

    # 6. 下载所有壁纸，筛选出本次新下载的壁纸
    print("\n开始下载壁纸图片...")
    for img_data in final_bing_data:
        is_new_download = download_bing_wallpaper(img_data)
        if is_new_download:
            new_downloaded_data.append(img_data)  # 仅加入新下载的壁纸

    # 7. 若无新下载的壁纸，直接终止后续流程
    if not new_downloaded_data:
        print("\n本次无新下载的壁纸，跳过今日一言获取和钉钉推送")
        print("===== 全流程执行完成 =====")
        return

    # 8. 获取今日一言（含来源）
    hitokoto_info = get_hitokoto()

    # 9. 仅推送本次新下载的壁纸到钉钉（逐条发送，指定emoji格式）
    print(f"\n开始推送本次新下载的{len(new_downloaded_data)}张壁纸信息到钉钉...")
    for img_data in new_downloaded_data:
        send_single_to_dingtalk(img_data, hitokoto_info)

    print("\n===== 全流程执行完成 =====")

if __name__ == "__main__":
    main()
