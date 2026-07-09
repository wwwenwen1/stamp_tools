# 合同批量盖章工具

一个基于 Python + PyMuPDF 的合同批量盖章工具，支持 PDF/Word/Excel 文件上传，可视化拖拽定位印章，自动抠除白色背景，一键导出盖章后的 PDF。

## 功能特性

- **多格式支持** — 上传 PDF、Word (.docx/.doc)、Excel (.xlsx/.xls)，自动转为 PDF
- **可视化拖拽** — 在页面上直接拖拽印章到任意位置，所见即所得
- **智能抠白** — 自动识别并去除印章图片的白色背景，只保留印章主体
- **透明度调节** — 印章透明度可调，下方文字仍可阅读（默认 85%）
- **页面范围** — 支持当前页盖章或指定页码范围
- **印章管理** — 上传后可命名保存，下次直接选用，数据持久化
- **实时预览** — 前端 Canvas 实时模拟最终盖章效果

## 快速开始

### 方式一：直接运行 exe（无需 Python）

1. 下载 `合同盖章工具.exe`
2. 双击运行，浏览器自动打开
3. 上传合同文件 → 上传印章 → 拖拽定位 → 盖章导出

> 注意：上传 Word/Excel 需要电脑安装 Microsoft Office

### 方式二：源码运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动
python main.py
```

浏览器打开 `http://127.0.0.1:5188`

## 依赖项

- Python 3.10+
- PyMuPDF — PDF 渲染与盖章
- FastAPI + uvicorn — Web 服务
- Pillow — 印章图像处理（抠白 + 透明度）
- pywin32 — 调用 Microsoft Office 转换 Word/Excel（仅 Windows）

## 项目结构

```
stamp_tool/
├── main.py              # FastAPI 后端入口
├── stamp_engine.py      # 盖章引擎（PyMuPDF）
├── converter.py         # 格式转换（win32com → PDF）
├── static/
│   ├── index.html       # 前端页面
│   ├── app.js           # 前端逻辑（Canvas 预览 + 拖拽）
│   └── style.css        # 样式
├── stamps/              # 保存的印章（运行时生成）
├── requirements.txt
└── 启动工具.bat          # Windows 一键启动脚本
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 上传合同文件，返回页面预览 |
| POST | `/api/upload-stamp` | 上传印章图片 |
| POST | `/api/stamp` | 执行盖章，返回 PDF |
| GET  | `/api/stamps` | 列出已保存印章 |
| POST | `/api/stamps/{id}/save` | 命名保存印章 |
| DELETE | `/api/stamps/{id}` | 删除印章 |

## 打包为 exe

```bash
pip install pyinstaller
python -m PyInstaller --onefile --noconsole \
  --add-data "static;static" \
  --add-data "stamps;stamps" \
  --name "合同盖章工具" \
  --hidden-import win32com --hidden-import pythoncom \
  --collect-all pymupdf --collect-all PIL \
  main.py
```

输出在 `dist/` 目录下。

## License

MIT
