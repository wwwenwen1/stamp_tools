# 合同批量盖章工具

## 项目概述

Web 可视化合同盖章工具。上传 PDF/Word/Excel → 拖拽印章定位 → 自动抠白 → 导出盖章 PDF。

- 后端：FastAPI + PyMuPDF，端口 5188
- 前端：原生 HTML/CSS/JS，Canvas 实时预览
- Office 转换：win32com 调用本机 MS Office（仅 Windows）
- 打包：PyInstaller --onefile --noconsole

## 项目结构

```
main.py              # 入口，所有 API 端点
stamp_engine.py      # 盖章引擎 + 抠白处理 (Pillow)
converter.py         # Word/Excel → PDF (win32com)
static/              # 前端 index.html / app.js / style.css
stamps/              # 保存的印章 (stamps.json + png)
requirements.txt
启动工具.bat          # 开发环境双击启动
```

## 启动

```bash
pip install -r requirements.txt
python main.py
# 浏览器打开 http://127.0.0.1:5188
```

## 打包 exe

```bash
python -m PyInstaller --onefile --noconsole --add-data "static;static" --add-data "stamps;stamps" --name "合同盖章工具" --hidden-import win32com --hidden-import pythoncom --collect-all pymupdf --collect-all PIL main.py
```

输出 `dist/合同盖章工具.exe`

## 关键设计点

- **抠白逻辑**前后端各一套：后端 Pillow, 前端 Canvas API，判定 RGB>230 为白色背景
- **exe 路径**：`sys.frozen` 判断是否 exe 模式；exe 时数据目录跟 exe 走，静态文件读 `sys._MEIPASS`
- **noconsole 模式**：main.py 开头重定向 sys.stdout/stderr/stdin 为 devnull，否则 uvicorn 日志崩溃
- **印章持久化**：stamps.json 记录元数据，每次启动加载已保存印章列表

## 已知限制

- Word/Excel 上传依赖本机安装 Microsoft Office
- 仅绑定 127.0.0.1，仅本机访问
- exe 约 44MB
