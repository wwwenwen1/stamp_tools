"""
文件格式转换模块
通过 win32com 调用 Microsoft Office 将 Word/Excel 文件转为 PDF
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path


def _find_office_path():
    """查找 MS Office 安装路径"""
    # 常见安装路径
    possible_paths = [
        r"C:\Program Files\Microsoft Office\root\Office16",
        r"C:\Program Files (x86)\Microsoft Office\root\Office16",
        r"C:\Program Files\Microsoft Office\Office16",
        r"C:\Program Files (x86)\Microsoft Office\Office16",
        r"C:\Program Files\Microsoft Office\Office15",
        r"C:\Program Files (x86)\Microsoft Office\Office15",
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return p
    return None


def _check_libreoffice():
    """检查 LibreOffice 是否可用（作为备用方案）"""
    try:
        result = subprocess.run(
            ["libreoffice", "--version"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 尝试 soffice
    try:
        result = subprocess.run(
            ["soffice", "--version"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return False


def convert_to_pdf_libreoffice(input_path: str, output_dir: str) -> str:
    """
    使用 LibreOffice 将文档转为 PDF（备用方案）
    返回输出 PDF 路径
    """
    result = subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf",
         "--outdir", output_dir, input_path],
        capture_output=True, text=True, timeout=120
    )

    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice 转换失败: {result.stderr}")

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.pdf")
    return output_path


def convert_to_pdf_win32(input_path: str, output_dir: str) -> str:
    """
    使用 win32com (MS Office) 将 Word/Excel 文档转为 PDF
    返回输出 PDF 路径
    """
    # win32com 仅在 Windows 上可用
    if sys.platform != "win32":
        raise RuntimeError("win32com 仅支持 Windows 系统，请使用 LibreOffice")

    import pythoncom
    pythoncom.CoInitialize()

    ext = os.path.splitext(input_path)[1].lower()
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.pdf")

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    try:
        from win32com import client

        if ext in [".docx", ".doc"]:
            word = None
            doc = None
            try:
                word = client.Dispatch("Word.Application")
                word.Visible = False
                word.DisplayAlerts = 0
                doc = word.Documents.Open(os.path.abspath(input_path))
                doc.SaveAs(os.path.abspath(output_path), FileFormat=17)  # 17 = PDF
            finally:
                if doc:
                    try:
                        doc.Close()
                    except Exception:
                        pass
                if word:
                    try:
                        word.Quit()
                    except Exception:
                        pass

        elif ext in [".xlsx", ".xls"]:
            excel = None
            wb = None
            try:
                excel = client.Dispatch("Excel.Application")
                excel.Visible = False
                excel.DisplayAlerts = False
                wb = excel.Workbooks.Open(os.path.abspath(input_path))
                wb.ExportAsFixedFormat(0, os.path.abspath(output_path))  # 0 = PDF
            finally:
                if wb:
                    try:
                        wb.Close()
                    except Exception:
                        pass
                if excel:
                    try:
                        excel.Quit()
                    except Exception:
                        pass
        else:
            raise ValueError(f"不支持的文件格式: {ext}")

    finally:
        pythoncom.CoUninitialize()

    return output_path


def convert_to_pdf(input_path: str, output_dir: str) -> str:
    """
    将文档转为 PDF，自动选择最佳转换方式

    Args:
        input_path: 输入文件路径 (.docx/.doc/.xlsx/.xls/.pdf)
        output_dir: 输出目录

    Returns:
        输出 PDF 路径（如果输入已是 PDF 则返回原路径）

    Raises:
        RuntimeError: 转换失败
    """
    ext = os.path.splitext(input_path)[1].lower()

    # PDF 文件无需转换
    if ext == ".pdf":
        return input_path

    # 优先使用 win32com（Windows + MS Office）
    if sys.platform == "win32":
        return convert_to_pdf_win32(input_path, output_dir)

    # 备用：LibreOffice
    if _check_libreoffice():
        return convert_to_pdf_libreoffice(input_path, output_dir)

    raise RuntimeError(
        "无法转换文件。Windows 系统请确保安装了 Microsoft Office；"
        "其他系统请安装 LibreOffice。"
    )


if __name__ == "__main__":
    # 测试
    import sys
    if len(sys.argv) > 1:
        pdf_path = convert_to_pdf(sys.argv[1], "./outputs")
        print(f"转换成功: {pdf_path}")
