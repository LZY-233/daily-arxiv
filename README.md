# Daily arXiv Research Radar

Daily arXiv 是一个面向基础模型研究者的个性化论文雷达。它每天增量读取 arXiv 元数据，按研究主题、方法贡献和摘要中的证据信号进行初筛，将结果保存为可审计的 JSONL，并生成一个无需后端的静态阅读页面。

当前版本会为每日精选论文生成中文摘要与一句话 TL;DR，同时不会下载或保存论文 PDF。AI 增强是可选步骤：未配置 API Key 或接口暂时失败时，抓取、排序和网页发布仍会继续，页面自动回退到 arXiv 英文摘要。

## 研究偏好

- 核心：LLM、MLLM/VLM、MoE、Agent、预训练、后训练、模型架构。
- 次级：推理、效率、评测。
- 低优先级：安全。
- 排除：医疗、金融、遥感等垂直应用，除非包含可泛化的基础模型方法。
- 重点信号：方法创新、工程系统、理论价值、大规模实验、强基线、消融和开放资源。
- 已校准偏好：提高 MoE、缩放规律、算力匹配和训练/路由机制；降低以幻觉分析、忠实度分析、benchmark 构建或安全问题为主要贡献的论文。

默认每日展示最多 5 篇“必读”和 10 篇“值得浏览”，并用轻量多样性约束避免单一主题垄断精选；其余相关论文进入观察名单。MVP 的分数只基于标题和摘要，页面会明确显示“摘要初审”，不会把它冒充成论文质量的最终结论。

## 快速开始

项目只依赖 Python 3.11+ 标准库。

```powershell
# 使用内置样本离线跑通完整流程
python scripts/daily.py --fixture tests/fixtures/arxiv_feed.xml --now 2026-09-03T10:00:00+08:00

# 启动本地网站
python -m http.server 8000 --directory site
```

然后访问 <http://localhost:8000>。

联网获取最近论文：

```powershell
python scripts/daily.py --lookback-hours 72 --max-results 1000
```

如需在本地生成中文摘要，请仅通过环境变量提供 Key：

```powershell
$env:DEEPSEEK_API_KEY = "你的 API Key"
python scripts/daily.py --lookback-hours 72 --max-results 1000
```

默认通过 DeepSeek Responses API 使用 `deepseek-v4-flash`，只处理 5 篇“必读”和 10 篇“值得浏览”；已生成内容会从月度 JSONL 缓存复用。可用 `DEEPSEEK_MODEL`、`DEEPSEEK_ENRICH_LIMIT` 和 `DEEPSEEK_BATCH_SIZE` 环境变量调整模型、篇数和批量大小。

调整主题或权重后，可直接重排本地缓存，无需重复请求 arXiv：

```powershell
python scripts/daily.py --source-json data/latest.json
```

运行测试：

```powershell
python -m unittest discover -s tests -v
```

## 目录

```text
config/                 主题、权重和抓取配置
data/papers/            按月保存的论文 JSONL
data/runs/              每次任务的运行记录
data/latest.json        最近一次精选结果
site/                   可直接部署到 GitHub Pages 的静态网站
src/daily_arxiv/        抓取、解析、筛选、排名和存储逻辑
scripts/daily.py        本地与定时任务入口
tests/                  单元测试和离线 arXiv 样本
```

## 数据与隐私

- 代码、论文元数据和网站计划公开，许可证为 MIT。
- 不将论文 PDF 保存到仓库，只保存 arXiv 和 PDF 链接。
- 收藏、已读和忽略状态只写入浏览器 `localStorage`。
- API Key 只允许放入环境变量或 GitHub Actions Secrets，禁止提交到仓库。

## GitHub Actions 中配置 API Key

1. 打开仓库的 `Settings → Secrets and variables → Actions`。
2. 在 `Secrets` 页签点击 `New repository secret`，名称填写 `DEEPSEEK_API_KEY`，值填写 DeepSeek API Key。
3. 可选：在 `Variables` 页签添加 `DEEPSEEK_MODEL`；不设置时使用 `deepseek-v4-flash`。
4. 在 `Actions` 页重新运行 `Daily arXiv radar`，或等待下一次定时任务。

工作流只通过 `secrets.DEEPSEEK_API_KEY` 将 Key 注入单个抓取步骤的环境变量，Key 不进入代码、数据文件或提交记录。若 Secret 不存在，GitHub 会传入空值，程序记录 `skipped_no_key` 后继续发布英文摘要。

## 当前边界

- 相关性和证据评分是可解释的规则基线，不是模型评审。
- 中文摘要与 TL;DR 仅依据标题和 arXiv 摘要生成，不代表已阅读全文；页面保留英文原摘要供核对。
- 当前 API 按分类查询首次提交时间窗口、跨分类去重，并报告每个分类是否触及结果上限；旧论文的新版本复查将在延迟复评阶段补充。
- 尚未执行 PDF 正文审查、7/30 天延迟复评或外部引用/代码活跃度检查。
- GitHub Actions 在工作日北京时间 10:07 自动更新数据并部署 GitHub Pages，也可手动运行。

## 后续阶段

1. 用数日真实结果校准召回词、排除词和评分阈值。
2. 只对高优先级论文进行 PDF 关键章节深审。
3. 增加每周回顾、7/30 天复评和可导出的用户反馈。
