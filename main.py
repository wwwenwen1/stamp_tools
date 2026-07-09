"""
合同批量盖章工具 — 主程序入口
FastAPI 后端 + 静态文件服务
"""

import os
import sys
import uuid
import shutil
import tempfile
import time
import webbrowser
import threading
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from stamp_engine import (
    stamp_pdf,
    get_page_count,
    render_page_preview,
    render_all_pages_preview,
    parse_page_range,
)
from converter import convert_to_pdf

# 项目根目录
if getattr(sys, 'frozen', False):
    # exe 模式：数据目录跟随 exe，静态文件从打包临时目录读取
    BASE_DIR = Path(sys.executable).parent.absolute()
    STATIC_DIR = Path(sys._MEIPASS) / "static"
else:
    # 开发模式：所有目录在脚本同级
    BASE_DIR = Path(__file__).parent.absolute()
    STATIC_DIR = BASE_DIR / "static"

UPLOADS_DIR = BASE_DIR / "uploads"
STAMPS_DIR = BASE_DIR / "stamps"
OUTPUTS_DIR = BASE_DIR / "outputs"

# 最大上传文件大小 (50MB)
MAX_UPLOAD_SIZE = 50 * 1024 * 1024
# 上传文件保留时间（秒），超过则清理
UPLOAD_RETENTION_SECONDS = 24 * 60 * 60

# 确保目录存在
for d in [UPLOADS_DIR, STAMPS_DIR, OUTPUTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="合同批量盖章工具", version="1.0.0")

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/stamps", StaticFiles(directory=str(STAMPS_DIR)), name="stamps")


def _cleanup_old_uploads():
    """清理过期的上传目录"""
    now = time.time()
    for job_dir in UPLOADS_DIR.iterdir():
        if job_dir.is_dir():
            try:
                mtime = os.path.getmtime(str(job_dir))
                if now - mtime > UPLOAD_RETENTION_SECONDS:
                    shutil.rmtree(job_dir, ignore_errors=True)
            except Exception:
                pass


@app.get("/")
async def index():
    """返回主页面"""
    return FileResponse(str(STATIC_DIR / "index.html"))


# ============================================================
# API 端点
# ============================================================

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    上传合同文件，转为 PDF，返回页面预览

    Returns:
        {
            "file_id": "xxx",
            "page_count": 10,
            "previews": ["base64_png_1", "base64_png_2", ...]
        }
    """
    # 清理过期上传
    _cleanup_old_uploads()

    # 验证文件类型
    ext = os.path.splitext(file.filename)[1].lower()
    allowed = {".pdf", ".docx", ".doc", ".xlsx", ".xls"}
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}。支持: PDF, Word, Excel"
        )

    # 生成唯一文件ID
    file_id = str(uuid.uuid4())[:8]
    job_dir = UPLOADS_DIR / file_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # 保存上传文件（限制大小）
    original_name = file.filename
    input_path = job_dir / original_name
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制（最大 {MAX_UPLOAD_SIZE // (1024*1024)}MB）"
        )
    with open(input_path, "wb") as f:
        f.write(content)

    # 转换为 PDF
    try:
        pdf_path = convert_to_pdf(str(input_path), str(job_dir))
    except Exception as e:
        # 清理
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"文件转换失败: {str(e)}")

    # 获取页数
    try:
        page_count = get_page_count(pdf_path)
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"无法读取PDF: {str(e)}")

    # 渲染所有页面缩略图（高清）
    import base64
    try:
        preview_images = render_all_pages_preview(pdf_path, scale=1.2)
        previews_b64 = [
            base64.b64encode(img).decode("utf-8")
            for img in preview_images
        ]
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"渲染预览失败: {str(e)}")

    return JSONResponse({
        "file_id": file_id,
        "original_name": original_name,
        "page_count": page_count,
        "previews": previews_b64,
        "pdf_path": str(pdf_path),
    })


@app.post("/api/preview-page")
async def preview_page(
    file_id: str = Form(...),
    page_num: int = Form(...),
):
    """
    获取单页高清预览（用于精确定位盖章位置）

    Returns:
        {"image": "base64_png"}
    """
    import base64

    job_dir = UPLOADS_DIR / file_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="文件未找到，请重新上传")

    # 查找 job_dir 中的 PDF 文件
    pdf_files = list(job_dir.glob("*.pdf"))
    if not pdf_files:
        raise HTTPException(status_code=404, detail="PDF文件未找到")

    pdf_path = str(pdf_files[0])
    try:
        img_bytes = render_page_preview(pdf_path, page_num, scale=1.0)
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        return JSONResponse({"image": img_b64})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"渲染失败: {str(e)}")


@app.post("/api/upload-stamp")
async def upload_stamp(stamp: UploadFile = File(...)):
    """
    上传印章图片

    Returns:
        {"stamp_id": "xxx"}
    """
    ext = os.path.splitext(stamp.filename)[1].lower()
    if ext not in {".png", ".jpg", ".jpeg", ".bmp"}:
        raise HTTPException(status_code=400, detail="印章图片仅支持 PNG/JPG/BMP 格式")

    stamp_id = str(uuid.uuid4())[:8]
    stamp_path = STAMPS_DIR / f"{stamp_id}{ext}"
    with open(stamp_path, "wb") as f:
        content = await stamp.read()
        f.write(content)

    return JSONResponse({
        "stamp_id": stamp_id,
        "stamp_path": str(stamp_path),
    })


@app.post("/api/stamp")
async def apply_stamp(
    file_id: str = Form(...),
    stamp_id: str = Form(...),
    x_percent: float = Form(...),
    y_percent: float = Form(...),
    page_range: str = Form(default="all"),
    stamp_width: float = Form(default=25.0),
    opacity: int = Form(default=80),
):
    """
    执行盖章操作

    Args:
        file_id: 文件ID
        stamp_id: 印章ID
        x_percent: 印章中心 X 坐标（页面宽度百分比）
        y_percent: 印章中心 Y 坐标（页面高度百分比）
        page_range: 页码范围（默认 "all"）
        stamp_width: 印章宽度百分比（默认25%）
        opacity: 印章透明度 (0-100，默认80)

    Returns:
        FileResponse: 盖章后的 PDF 文件
    """
    # 查找 PDF 文件
    job_dir = UPLOADS_DIR / file_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="文件未找到，请重新上传")

    pdf_files = list(job_dir.glob("*.pdf"))
    if not pdf_files:
        raise HTTPException(status_code=404, detail="PDF文件未找到")

    pdf_path = str(pdf_files[0])

    # 查找印章文件
    stamp_files = list(STAMPS_DIR.glob(f"{stamp_id}.*"))
    if not stamp_files:
        raise HTTPException(status_code=404, detail="印章未找到，请重新上传")

    stamp_path = str(stamp_files[0])

    # 验证坐标参数
    if not (0 <= x_percent <= 100):
        raise HTTPException(status_code=400, detail="X 坐标必须在 0-100 之间")
    if not (0 <= y_percent <= 100):
        raise HTTPException(status_code=400, detail="Y 坐标必须在 0-100 之间")
    if not (1 <= stamp_width <= 100):
        raise HTTPException(status_code=400, detail="印章宽度必须在 1-100 之间")
    if not (0 <= opacity <= 100):
        raise HTTPException(status_code=400, detail="透明度必须在 0-100 之间")

    # 获取总页数
    total_pages = get_page_count(pdf_path)

    # 解析页码范围
    try:
        pages = parse_page_range(page_range, total_pages)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"页码范围格式错误: {str(e)}")

    if not pages:
        raise HTTPException(status_code=400, detail="页码范围为空，请检查输入")

    # 生成输出文件名
    original_name = "document"
    for f in job_dir.iterdir():
        if f.suffix.lower() in {".docx", ".doc", ".xlsx", ".xls", ".pdf"}:
            original_name = f.stem
            break

    output_id = str(uuid.uuid4())[:6]
    output_filename = f"{original_name}_盖章_{output_id}.pdf"
    output_path = str(OUTPUTS_DIR / output_filename)

    # 执行盖章
    try:
        stamp_pdf(
            pdf_path=pdf_path,
            stamp_image_path=stamp_path,
            output_path=output_path,
            pages=pages,
            x_percent=x_percent,
            y_percent=y_percent,
            stamp_width_percent=stamp_width,
            opacity=opacity,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"盖章失败: {str(e)}")

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=output_filename,
    )


# ============================================================
# 印章管理
# ============================================================

STAMPS_MANIFEST = STAMPS_DIR / "stamps.json"


def _load_stamps_manifest() -> dict:
    """加载印章清单"""
    import json
    if STAMPS_MANIFEST.exists():
        with open(STAMPS_MANIFEST, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_stamps_manifest(manifest: dict):
    """保存印章清单"""
    import json
    with open(STAMPS_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


@app.get("/api/stamps")
async def list_stamps():
    """列出所有已保存的印章"""
    manifest = _load_stamps_manifest()
    stamps_list = []
    for stamp_id, info in manifest.items():
        stamps_list.append({
            "stamp_id": stamp_id,
            "name": info.get("name", "未命名"),
            "filename": info.get("filename", ""),
            "created_at": info.get("created_at", ""),
        })
    # 按创建时间倒序
    stamps_list.sort(key=lambda x: x["created_at"], reverse=True)
    return JSONResponse(stamps_list)


@app.post("/api/stamps/{stamp_id}/save")
async def save_stamp(stamp_id: str, name: str = Form(...)):
    """保存/命名印章"""
    # 查找印章文件
    stamp_files = list(STAMPS_DIR.glob(f"{stamp_id}.*"))
    if not stamp_files:
        raise HTTPException(status_code=404, detail="印章文件未找到")

    manifest = _load_stamps_manifest()
    manifest[stamp_id] = {
        "name": name.strip(),
        "filename": stamp_files[0].name,
        "created_at": manifest.get(stamp_id, {}).get("created_at", "") or __import__("datetime").datetime.now().isoformat(),
    }
    _save_stamps_manifest(manifest)

    return JSONResponse({"ok": True, "stamp_id": stamp_id, "name": name.strip()})


@app.delete("/api/stamps/{stamp_id}")
async def delete_stamp(stamp_id: str):
    """删除印章"""
    # 删除文件
    for f in STAMPS_DIR.glob(f"{stamp_id}.*"):
        f.unlink()

    # 更新清单
    manifest = _load_stamps_manifest()
    manifest.pop(stamp_id, None)
    _save_stamps_manifest(manifest)

    return JSONResponse({"ok": True})


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


def open_browser():
    """延迟打开浏览器"""
    import time
    time.sleep(1)
    webbrowser.open("http://127.0.0.1:5188")


def main():
    """程序入口"""
    host = "127.0.0.1"
    port = 5188

    # 确保 Windows 控制台支持 Unicode 输出
    import io
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    print(f"""
╔══════════════════════════════════════════╗
║         合同批量盖章工具 v1.0            ║
║                                          ║
║  浏览器将自动打开，如未打开请访问:         ║
║  http://{host}:{port}                ║
║                                          ║
║  按 Ctrl+C 退出程序                       ║
╚══════════════════════════════════════════╝
    """)

    # 自动打开浏览器
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except OSError as e:
        if "10048" in str(e) or "in use" in str(e).lower():
            print(f"\n[错误] 端口 {port} 已被占用，请先关闭已运行的工具再试。")
        else:
            print(f"\n[错误] 启动失败: {e}")
        input("\n按 Enter 键退出...")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n已退出。")
    except Exception as e:
        print(f"\n[错误] 未知异常: {e}")
        input("\n按 Enter 键退出...")
        sys.exit(1)


if __name__ == "__main__":
    main()
