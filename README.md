# 网页搜索技能
调用内置浏览器执行网络搜索，只调用bing搜索，较稳定，支持多词条查询，返回网页原始搜索结果及AI归纳摘要。

# 安装依赖
```uv venv -p 3.10```
```uv pip install -r requirements.txt```
```uv run playwright install chromium```

# 运行
```配置下config.yaml，没llm就把开关置false```
```uv run main.py```
```将skill.md加入agent的技能```
