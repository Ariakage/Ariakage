# 主页维护说明

这份 GitHub 个人主页以自设角色的银白、冰蓝、黑色与红蓝异瞳为视觉线索。英文入口为 `README.md`，中文入口为 `README_ZH_HANS.md`。

## 文件

- `assets/hero.png`：主页横幅，使用内置 imagegen 根据用户提供的自设参考图生成。
- `assets/character-original.png`：用户提供的原始自设图，原样保留。
- `assets/generated/`：仓库自托管的统计卡片、贡献趋势和贪吃蛇动画。
- `scripts/update_profile.py`：只使用 Python 标准库，抓取公开数据并输出明暗两套 SVG。
- `scripts/card_strings.py`：卡片中文文案。中英两版共用数据和布局，标题、指标、图例、日期说明及无障碍描述分别本地化。
- `scripts/finalize_snake.py`：为贪吃蛇输出补充减少动态效果的媒体查询。
- `.github/workflows/profile.yml`：检查、生成和更新流程。

## 更新与启用

工作流位于默认分支 `main` 后，在每天 **08:21（北京时间 / UTC+8）** 附近运行，也可以在 Actions → **Refresh profile visuals** → **Run workflow** 手动触发。GitHub 的定时任务可能延迟。修改生成脚本或工作流并推送到 main 也会触发更新。

工作流使用 GitHub 自动提供的 `GITHUB_TOKEN`，不需要配置个人 PAT、Vercel 服务或额外服务器。统计获取和 SVG 生成全部成功后，才提交 `assets/generated/` 的变化。失败时主页仍使用最后一次成功提交的图片，错误可在 Actions 中查看。

`validate` 任务只需读取仓库；`refresh` 任务只在 main 上运行，并获得提交生成图片所需的 `contents: write` 权限。所有第三方 Action 都固定到完整提交 SHA。若仓库的分支规则禁止机器人直接提交，需要按仓库规则改为生成更新 PR；不要关闭既有分支保护。

GitHub 对长期无活动的公开仓库可能暂停定时工作流；可在 Actions 中重新启用。首次上线的图片已随仓库提供，更新任务暂时未运行也不会出现空白卡片。

## 图表口径

- **Contributions / Days creating**：从 GitHub 不带认证的公开贡献日历读取最近 365 个日期的精确贡献数与非零天数。贡献不等于提交次数；GitHub 有自己的贡献统计规则。
- **Public repositories**：GitHub REST API 列出的全部公开自有仓库数，包含 fork。
- **Stars**：公开、非 fork 的自有仓库获得的星标总数。
- **Language palette**：公开、非 fork 的自有仓库中，GitHub Languages API 返回的代码字节数占比。显示前四种语言，其他合并为 Other。这不衡量熟练程度，也不代表编程时间。
- **Contribution rating**：复刻原 GitHub Readme Stats 的评分公式，沿用 `include_all_commits=true` 模式。等级为 C、C+、B-、B、B+、A-、A、A+、S；圆环对应 `100 - percentile`，同时显示该公式分数（满分 100）。这是基于固定公式的展示指标，不是 GitHub 官方评级，也不是实际用户排行榜。原算法及 MIT 许可证见下文。
- **PRs / Merged / Currently open**：GitHub Search API 中本人创建的公开 PR，分别为历史总量、已合并总量和当前仍开启的数量。合并率 = 已合并 / 全部 PR，包含尚未关闭的 PR 在分母中；尚无 PR 时显示「—」。
- **Commits / Issues opened**：公开仓库中本人创建的、被 GitHub 搜索索引到的历史提交 / Issue 总量，提交数不是贡献日历的贡献总数。搜索范围显式限定 `is:public`；如果搜索返回不完整结果，停止本次生成，保留上一版。
- **PR reviews / Repos contributed**：过去一年 GitHub 记录的公开 PR review 贡献数与参与贡献的公开仓库数。Review 分页获取并过滤私有仓库；参与仓库口径沿用原卡片，贡献类型为提交、Issue、PR 和仓库创建，使用 GraphQL `repositoriesContributedTo` 的默认统计范围。
- **Stars / Followers（评分卡）**：评分沿用原卡片的全部公开自有仓库星标（含 fork）与粉丝数。上方概览卡的星标仍只统计非 fork 仓库，两个口径在各自标签中标明。
- **Activity**：最近 12 个自然周，周一为一周开始。当前周尚未结束，已经在图中标注。
- **Snake**：使用 [Platane/snk](https://github.com/Platane/snk) 的 SVG-only Action，基于 GitHub 的贡献日历生成。日历范围由上游决定，可能与 365 天统计卡的起止边界略有差异。
- 原始公开数据快照保存在 `assets/generated/profile-data.json`；里面不包含 token 或私有仓库资料。

贡献日历 HTML 解析会检查日期完整性。若 GitHub 修改页面结构导致计数缺失，脚本会失败，而不是用零填补并发布错误数据。

## 本地维护

Python 3.12 或更新版本：

```sh
python3 scripts/update_profile.py
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

在线生成时，新增的评分数据查询需要通过环境变量 `GITHUB_TOKEN` 提供 GitHub token。Actions 已自动提供，不用额外配置 PAT；本地可使用已经登录的 GitHub CLI 凭据。不要将 token 写进文件或提交到仓库。离线重绘与测试不需要 token。

无需网络，重新绘制已有数据：

```sh
python3 scripts/update_profile.py --from-json assets/generated/profile-data.json
```

贪吃蛇由工作流中的固定版本 Action 生成，随后执行 `python3 scripts/finalize_snake.py`。完整维护代码没有额外 Python 依赖。

## GitHub 显示兼容性

README 使用 GitHub 支持的 Markdown、`picture` 和图片元素。图表是无脚本、无外部字体、无远程嵌入内容的 SVG；动效在图片内部实现，不依赖 README 执行 JavaScript。浏览器设置“减少动态效果”时会显示静态版本。

明暗图表通过 `prefers-color-scheme` 切换。横幅保留统一的浅色艺术画面。GitHub 的图片缓存可能使刚更新的图表稍晚显示。

每次更新同时生成 24 张统计卡片：中英文各 12 张，均含明暗主题和手机尺寸的趋势图。英文 README 使用原有文件名；中文 README 使用 `*-zh-light.svg` / `*-zh-dark.svg`，例如 `rating-zh-light.svg`。无文字的贪吃蛇动画和技术图标共用素材。编程语言名称、PR、GitHub 及评分等级等专有名称保留原写法；中文卡片使用系统中文字体回退，不加载外部字体。

技术栈图标来自 [Skill Icons](https://github.com/tandpfun/skill-icons)，已保存到仓库以避免外部图床临时故障。原始许可证保留在 [SKILL-ICONS-LICENSE](./SKILL-ICONS-LICENSE)，链接的替代文字同时列出工具名称。其他个人信息整理自原有 README / 简历与公开仓库；未改变原简历。

## 横幅生成记录

使用内置 imagegen 工具，以 `assets/character-original.png` 为参考图。最终生成提示词完整保存在 [hero-prompt.txt](./hero-prompt.txt)。角色原图作为用户素材保留；该仓库没有为原图或横幅另行授予开源许可。

## 参考

评分算法从 [GitHub Readme Stats / calculateRank.js](https://github.com/anuraghazra/github-readme-stats/blob/54a7985aeefda00d5eadb55b80c17c7f976c37d2/src/calculateRank.js) 移植，保留 [原始 MIT 许可证](./GITHUB-README-STATS-LICENSE)。权重为 commits 2、PRs 3、Issues 1、Reviews 1、Stars 4、Followers 1。使用公开数据与每日快照，可能与原 Vercel 服务的缓存时间或 token 可见范围不同。

- [GitHub：管理个人资料 README](https://docs.github.com/en/account-and-profile/how-tos/profile-customization/managing-your-profile-readme)
- [GitHub：计划事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [GitHub REST：用户仓库列表](https://docs.github.com/en/rest/repos/repos#list-repositories-for-a-user)
- [GitHub：贡献计入规则](https://docs.github.com/en/account-and-profile/concepts/contributions-visible-on-your-profile)
- [Platane/snk：贡献贪吃蛇](https://github.com/Platane/snk)
