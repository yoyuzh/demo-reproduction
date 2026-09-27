# 配置错误定位：论文轻量 Demo

单页面 Streamlit 演示版，使用工作区 PDF 中图 1 的 `mapred.local.dir` 直接症状和 `LdapGroupsMapping` 间接症状。不运行 Hadoop，也不复现整套 benchmark。每个案例的日志、少量正常模板、JSON 配置和预期配置项保存在 [cases.py](cases.py)；页面允许手动修改日志和配置。

## 启动

在本工作区根目录运行：

```bash
uv venv --python python3.11 .venv
uv pip install --python .venv/bin/python -r light_demo/requirements.txt
.venv/bin/streamlit run light_demo/app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

打开 <http://127.0.0.1:8501>，选择案例并点击“开始定位配置错误”。默认启用**测试响应**，不请求 OpenAI；两个论文案例都可以走到报告。第三个案例明确标为测试用途，固定让图 3 验证失败，用于检查 `complete-flow`。这些测试解释是本地模拟文本，不代表论文或 OpenAI 的真实回答。

真实模型调用：先在启动服务的终端设置 `OPENAI_API_KEY`，然后重启服务并取消“使用测试响应”勾选。可选 `OPENAI_MODEL` 指定模型；默认是 `gpt-4.1`。论文实验使用 `gpt-4-0613`，因此其他模型的输出可能不同。没有有效凭据或 API 返回错误时，页面显示错误，**不会生成诊断报告**。

## 流程

1. Stage 1：论文案例使用手工解析模板，跳过 Drain；从本案例的正常模板库中排除相同模板；按论文 Algorithm 1 的 10 个词各 `0.1` 评分，并展示模板、异常度和选中的原始日志。
2. Stage 2：先匹配配置值、完整配置名和按 `.` 拆分的配置名片段。存在候选时，使用论文图 3 的 **system prompt 原文**逐项验证；没有候选项或验证失败时，使用图 4 的 **system prompt 原文**间接推断。界面显示 `fast-flow`、`direct-flow` 或 `complete-flow` 的实际流转。
3. 报告：展示可疑配置、关联日志、模型解释、实际路径和响应来源。图 3 只要求模型输出概率；为补充 `fast-flow` 报告中的解释，确定根因后会额外使用图 4 的原始 prompt 做一次解释调用，这次调用不改变根因选择。

图 1 样例在 PDF 第 3 页，图 3/4 prompt 在第 6 页。这个 Demo 只展示核心逻辑，两个案例不能证明论文报告的准确率。

## 自检

```bash
.venv/bin/python -m unittest light_demo.test_core -v
```
