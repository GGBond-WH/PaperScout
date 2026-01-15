# OpenReview 论文筛选与评分分析工具

一个基于 Streamlit 的 Web 应用，用于在 OpenReview 上按会议、年份、关键词、评分等维度筛选论文，并展示评审详情。

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ 功能特性

### 筛选功能
- **会议筛选**: 支持 ICLR, NeurIPS, ICML, AAAI 2021-2025（AAAI 为 Web 数据源，无评审分）
- **年份筛选**: 2018-2026 年份范围选择
- **关键词筛选**: 支持 AND/OR 逻辑，可选择匹配范围（标题/摘要/两者）
- **评分筛选**: 最低平均分、最高分、评审数量筛选（**支持自适应 5 分/10 分制**）
- **自定义 Venue**: 直接输入 OpenReview Venue ID

### 展示功能
- 论文列表表格显示（标题、会议、作者、评分）
- 可展开的论文详情（摘要、评审明细、PDF链接）
- 关键词高亮显示
- 分页浏览
- CSV 导出

### 技术特性
- 6 小时 API 缓存，减少重复请求
- 指数退避重试机制
- 评分字符串智能解析（支持 "6: Strong Accept" 等格式）

## 🚀 快速开始

### 环境要求
- Python 3.10+
- pip

### 本地运行

1. **克隆或下载项目**
   ```bash
   cd PaperScout
   conda create -n paperscout python=3.9
   conda activate paperscout
   ```
   
2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **启动应用**
   ```bash
   streamlit run app.py
   ```

4. **访问应用**
   
   浏览器打开 http://localhost:8501

## ☁️ 部署到 Streamlit Community Cloud

### 准备工作

1. 将项目推送到 GitHub 仓库

2. 确保仓库包含以下文件：
   - `app.py`
   - `requirements.txt`
   - `config.py`
   - `parsing.py`
   - `openreview_client.py`
   - `ui_components.py`

### 部署步骤

1. 访问 [Streamlit Community Cloud](https://share.streamlit.io/)

2. 点击 "New app"

3. 连接你的 GitHub 账号

4. 选择仓库、分支和主文件 (`app.py`)

5. 点击 "Deploy"

6. 等待部署完成（约 2-5 分钟）

### 注意事项

- 本应用仅使用 OpenReview 公开 API，无需配置任何密钥
- 首次部署可能需要几分钟安装依赖
- 免费版有资源限制，大量数据加载时可能较慢

## 📁 项目结构

```
PaperScout/
├── app.py                  # Streamlit 主应用
├── config.py               # 配置和会议映射
├── parsing.py              # 评分解析和筛选逻辑
├── openreview_client.py    # OpenReview API 客户端
├── web_scraper.py          # GitHub/Web 数据抓取 (AAAI 2021-2025)
├── ui_components.py        # UI 组件
├── requirements.txt        # Python 依赖
├── README.md               # 本文件
└── .streamlit/
    └── config.toml         # Streamlit 配置
```

## 🔧 自定义配置

### 添加新会议

编辑 `config.py` 中的 `VENUE_MAPPINGS`:

```python
VENUE_MAPPINGS["NewConf"] = {
    "display_name": "NewConf",
    "aliases": ["newconf", "nc"],
    "patterns": [
        "NewConf.org/{year}/Conference",
    ],
    "years_available": list(range(2023, 2027)),
}
```

### 调整评分字段优先级

编辑 `config.py` 中的 `SCORE_FIELD_NAMES` 列表，按优先级排序。

## 📝 使用说明

### 基本工作流

1. **选择会议**: 在左侧边栏多选框选择会议
2. **设置年份**: 调整年份滑块
3. **加载数据**: 点击「加载数据」按钮
4. **筛选结果**: 输入关键词、设置评分阈值
5. **查看详情**: 展开论文卡片查看摘要和评审
6. **导出结果**: 点击「导出 CSV」下载筛选结果

### 评分解析说明

工具会自动从评审字段中提取数值评分：
- `"6: Strong Accept"` → 6.0
- `"8 (Top 10%)"` → 8.0
- `"3.5"` → 3.5

无法解析的评分会被标记为空值，不参与统计。

## ⚠️ 已知限制

1. **OpenReview 覆盖范围**: 并非所有会议都在 OpenReview 上，部分早期年份可能无数据
2. **API 速率限制**: OpenReview API 有请求频率限制，大量请求时可能需要等待
3. **Venue ID 变化**: 不同年份的会议可能使用不同的 Venue ID 格式
4. **评审字段差异**: 不同会议使用的评分字段名可能不同（rating/recommendation/score）

## 🐛 故障排除

### 无法加载数据

1. 检查网络连接
2. 确认 OpenReview 网站可访问
3. 尝试使用自定义 Venue ID
4. 点击「清除缓存」后重试

### 评分显示为空

可能是该会议使用了非标准的评分字段名。可以在 `config.py` 的 `SCORE_FIELD_NAMES` 中添加新的字段名。

## 📄 License

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
