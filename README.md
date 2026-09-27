# 配置错误定位：论文轻量 Demo

这是一个基于 Streamlit 的单页面演示程序，用论文图 1 的两个日志案例展示配置错误定位流程。默认使用本地测试响应，可以直接运行，**不需要 OpenAI API Key**。程序不启动 Hadoop，也不复现论文的完整 benchmark；测试响应中的解释是模拟文本，不能用来衡量论文方法的准确率。

## 运行环境

- Python 3.11
- uv（用于创建虚拟环境和安装依赖）
- macOS 或 Linux 终端；下列命令在 macOS、Python 3.11.15 和 uv 0.12.17 下验证

如果尚未获取代码，先克隆仓库（这是私有仓库，需要 GitHub 访问权限）：

```bash
git clone https://github.com/yoyuzh/demo-reproduction.git
cd demo-reproduction
```

如果已经在项目目录中，直接从包含 `light_demo/` 的仓库根目录执行下面的命令。先确认工具可用：

```bash
python3.11 --version
uv --version
```

## 安装并启动

首次运行时，在仓库根目录执行：

```bash
uv venv --python python3.11 .venv
uv pip install --python .venv/bin/python -r light_demo/requirements.txt
.venv/bin/streamlit run light_demo/app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

以后运行只需要执行最后一条 `streamlit run` 命令。浏览器打开 <http://127.0.0.1:8501>；停止服务时在终端按 `Ctrl+C`。如果 8501 端口已被占用，把启动命令中的 `8501` 改为 `8502`，并打开对应地址。

## 使用页面

1. 在“选择案例”中选择一个预置案例。页面会填入故障日志和 JSON 配置。
2. 保持“使用测试响应”勾选，点击“开始定位配置错误”。此模式不联网调用 OpenAI，适合先检查页面和流程。
3. 查看“Stage 1 · 关键日志”“Stage 2 · 流转状态”和“诊断报告”。

| 案例 | 测试响应的预期路径 | 预期配置项 |
| --- | --- | --- |
| 图 1：`mapred.local.dir` | `fast-flow` | `mapred.local.dir` |
| 图 1：`LdapGroupsMapping` | `direct-flow` | `hadoop.security.group.mapping.ldap.search.group.hierarchy.levels` |
| 测试案例：强制验证失败 | `complete-flow` | `mapred.local.dir` |

第三项是专门检查 `complete-flow` 的测试案例，不是论文中的第三个案例。**测试响应只支持未修改的预置日志和配置**；如果手动修改输入，请按下一节切换到真实模型调用。

## 使用真实模型（可选）

在启动服务的**同一个终端**设置环境变量，然后启动或重启 Streamlit：

```bash
export OPENAI_API_KEY='<你的 OpenAI API Key>'
# 可选：默认模型为 gpt-4.1
export OPENAI_MODEL='gpt-4.1'
.venv/bin/streamlit run light_demo/app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

在页面中取消勾选“使用测试响应”，再点击“开始定位配置错误”。程序会请求 OpenAI Chat Completions API；没有有效密钥或请求失败时，页面会显示错误，本次不会生成诊断报告。论文实验使用的是 `gpt-4-0613`，换用其他模型时输出可能不同。不要把实际密钥写进代码或提交到仓库。

## 运行自检

在仓库根目录执行：

```bash
.venv/bin/python -m unittest light_demo.test_core -v
```

目前包含 6 项流程测试。实现范围和论文对应关系见 [light_demo/README.md](light_demo/README.md)，论文 PDF 见 [3650212.3652106.pdf](3650212.3652106.pdf)。
