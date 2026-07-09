"""
PDF 盖章引擎
使用 PyMuPDF 在 PDF 页面指定位置叠加印章图片
"""

import os
import io
import tempfile
import fitz  # PyMuPDF
from PIL import Image


def parse_page_range(range_str: str, total_pages: int) -> list[int]:
    """
    解析页码范围字符串，返回页码列表（1-based）

    支持格式:
        "all"           → 所有页面
        "1-5"           → 第1到5页
        "1-5,7,10-15"   → 混合范围
        "odd"           → 奇数页
        "even"          → 偶数页

    Args:
        range_str: 页码范围字符串
        total_pages: 文档总页数

    Returns:
        页码列表（1-based），已去重排序
    """
    range_str = range_str.strip().lower()

    if range_str == "all":
        return list(range(1, total_pages + 1))

    if range_str == "odd":
        return [i for i in range(1, total_pages + 1) if i % 2 == 1]

    if range_str == "even":
        return [i for i in range(1, total_pages + 1) if i % 2 == 0]

    pages = set()
    parts = range_str.split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            try:
                start, end = part.split("-", 1)
                start, end = int(start.strip()), int(end.strip())
                if start < 1:
                    start = 1
                if end > total_pages:
                    end = total_pages
                for p in range(start, end + 1):
                    pages.add(p)
            except ValueError:
                continue
        else:
            try:
                p = int(part)
                if 1 <= p <= total_pages:
                    pages.add(p)
            except ValueError:
                continue

    return sorted(pages)


def _process_stamp_opacity(stamp_path: str, opacity: int) -> str:
    """
    处理印章图片：自动抠除白色背景 + 应用透明度

    - 白色/近白色区域 → 始终变为透明（自动抠图）
    - 有色区域（印章主体）→ 按 opacity 参数调整透明度

    Args:
        stamp_path: 原始印章图片路径
        opacity: 印章主体透明度百分比 (0-100)，100=完全不透明，推荐 85

    Returns:
        处理后的临时 PNG 文件路径
    """
    img = Image.open(stamp_path).convert("RGBA")
    pixels = list(img.getdata())
    factor = opacity / 100.0

    WHITE_THRESHOLD = 230  # RGB 各通道都大于此值视为白色背景

    new_pixels = []
    for r, g, b, a in pixels:
        # 自动抠除白色背景：RGB 都接近255的像素 → 完全透明
        if r > WHITE_THRESHOLD and g > WHITE_THRESHOLD and b > WHITE_THRESHOLD:
            # 白色背景，直接透明
            new_pixels.append((r, g, b, 0))
        else:
            # 印章主体，按 opacity 调整透明度
            final_alpha = int(255 * factor)
            # 如果原图自带 alpha 通道，取更严格的
            if a < final_alpha:
                final_alpha = a
            new_pixels.append((r, g, b, final_alpha))

    img.putdata(new_pixels)

    fd, temp_path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    img.save(temp_path, "PNG")
    return temp_path


def stamp_pdf(
    pdf_path: str,
    stamp_image_path: str,
    output_path: str,
    pages: list[int],
    x_percent: float,
    y_percent: float,
    stamp_width_percent: float = 25.0,
    opacity: int = 80,
) -> str:
    """
    在 PDF 的指定页面上叠加印章图片

    Args:
        pdf_path: 输入 PDF 路径
        stamp_image_path: 印章图片路径（PNG 透明背景）
        output_path: 输出 PDF 路径
        pages: 需要盖章的页码列表（1-based）
        x_percent: 印章中心 X 坐标（页面宽度百分比，0-100）
        y_percent: 印章中心 Y 坐标（页面高度百分比，0-100）
        stamp_width_percent: 印章宽度占页面宽度的百分比（默认25%）
        opacity: 印章透明度 (0-100，默认80，100=完全不透明)

    Returns:
        输出 PDF 路径
    """
    # 处理印章透明度
    processed_stamp = _process_stamp_opacity(stamp_image_path, opacity)
    try:
        return _stamp_pdf_inner(
            pdf_path, processed_stamp, output_path, pages,
            x_percent, y_percent, stamp_width_percent,
        )
    finally:
        # 清理临时印章文件
        if processed_stamp != stamp_image_path:
            try:
                os.remove(processed_stamp)
            except Exception:
                pass


def _stamp_pdf_inner(
    pdf_path: str,
    stamp_image_path: str,
    output_path: str,
    pages: list[int],
    x_percent: float,
    y_percent: float,
    stamp_width_percent: float = 25.0,
) -> str:
    doc = fitz.open(pdf_path)
    try:
        total_pages = doc.page_count

        # 读取印章图片（获取宽高比）
        stamp_pixmap = None
        stamp_img = None
        try:
            stamp_img = fitz.open(stamp_image_path)
            stamp_pixmap = stamp_img[0].get_pixmap()
        except Exception:
            pass
        finally:
            if stamp_img:
                stamp_img.close()

        for page_num in pages:
            if page_num < 1 or page_num > total_pages:
                continue

            page = doc[page_num - 1]  # PyMuPDF 使用 0-based 索引
            page_rect = page.rect
            page_w = page_rect.width
            page_h = page_rect.height

            # 计算印章放置位置（中心点）
            stamp_w = page_w * (stamp_width_percent / 100.0)
            center_x = page_w * (x_percent / 100.0)
            center_y = page_h * (y_percent / 100.0)

            # 计算印章矩形的左上角和右下角
            # 保持印章图片的宽高比
            if stamp_pixmap:
                aspect = stamp_pixmap.height / stamp_pixmap.width if stamp_pixmap.width > 0 else 1.0
            else:
                aspect = 1.0  # 默认正方形

            stamp_h = stamp_w * aspect

            x0 = center_x - stamp_w / 2
            y0 = center_y - stamp_h / 2
            x1 = center_x + stamp_w / 2
            y1 = center_y + stamp_h / 2

            stamp_rect = fitz.Rect(x0, y0, x1, y1)

            # 在页面上插入印章图片
            page.insert_image(
                stamp_rect,
                filename=stamp_image_path,
                overlay=True,
                keep_proportion=True,
            )

        # 保存输出 PDF
        doc.save(output_path)
    finally:
        doc.close()

    return output_path


def get_page_count(pdf_path: str) -> int:
    """获取 PDF 页数"""
    doc = fitz.open(pdf_path)
    count = doc.page_count
    doc.close()
    return count


def render_page_preview(pdf_path: str, page_num: int, scale: float = 0.5) -> bytes:
    """
    渲染 PDF 单页为 PNG 图片

    Args:
        pdf_path: PDF 文件路径
        page_num: 页码（1-based）
        scale: 缩放比例（默认0.5，即50%大小）

    Returns:
        PNG 图片字节数据
    """
    doc = fitz.open(pdf_path)
    if page_num < 1 or page_num > doc.page_count:
        doc.close()
        raise ValueError(f"页码 {page_num} 超出范围 (1-{doc.page_count})")

    page = doc[page_num - 1]
    # 增大分辨率以获得清晰的预览
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


def render_all_pages_preview(pdf_path: str, scale: float = 0.3) -> list[bytes]:
    """
    渲染 PDF 所有页为 PNG 缩略图

    Args:
        pdf_path: PDF 文件路径
        scale: 缩放比例（默认0.3）

    Returns:
        PNG 图片字节数据列表，按页码顺序
    """
    doc = fitz.open(pdf_path)
    mat = fitz.Matrix(scale, scale)
    results = []
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        results.append(pix.tobytes("png"))
    doc.close()
    return results


if __name__ == "__main__":
    # 简单测试
    import sys
    if len(sys.argv) < 2:
        print("用法: python stamp_engine.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"PDF 页数: {get_page_count(pdf_path)}")

    pages = parse_page_range("1-3", get_page_count(pdf_path))
    print(f"页码范围 1-3 解析结果: {pages}")

    pages = parse_page_range("odd", get_page_count(pdf_path))
    print(f"奇数页: {pages}")
