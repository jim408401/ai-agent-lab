# 01 最小 ReAct Agent（Ollama 版）

對應書中 1.1.5 節。只用 Python 標準函式庫，模型走本機 Ollama。

```
ollama pull gemma4:e4b
python agent.py "把 100 歐元和 50 英鎊換成美元，再加總"
python agent.py --fake     # 不需 Ollama，用假模型看迴圈
```

結構：`ollama_model`（Model）→ `run_agent`（Harness：組上下文、驗證、迴圈）→ `TOOLS_IMPL`（Environment）。
