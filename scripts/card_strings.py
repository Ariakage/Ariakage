"""Chinese copy for the profile's shared SVG layouts; English is the source text."""

ZH = {
    "01 / GITHUB AT A GLANCE": "01 / GitHub 概览",
    "Contributions · past 365 days": "贡献次数 · 近 365 天",
    "Days creating · past 365 days": "活跃天数 · 近 365 天",
    "Public repositories": "公开仓库",
    "Stars · original public repos": "星标 · 原创公开仓库",
    "PUBLIC PROFILE / UPDATED {updated} UTC": "公开数据 / 更新于 {updated} UTC",
    "Ariakage's GitHub overview": "Ariakage 的 GitHub 概览",
    "{total} contributions and {active} active days over the past 365 days; {repos} public repositories; {stars} stars on original public repositories.": "近 365 天贡献 {total} 次、活跃 {active} 天；公开仓库 {repos} 个；原创公开仓库获得 {stars} 个星标。",
    "02 / LANGUAGE PALETTE": "02 / 代码语言分布",
    "A little of everything I build with.": "让想法成形的那些语言。",
    "Other": "其他",
    "No public language data yet.": "暂无公开语言数据。",
    "By code bytes in original public repositories.": "按原创公开仓库的代码字节数计算。",
    "A snapshot of code, not a measure of proficiency.": "展示代码构成，不代表语言熟练程度。",
    "Languages in Ariakage's public repositories": "Ariakage 公开仓库的代码语言分布",
    "No language data": "暂无语言数据",
    "03 / CONTRIBUTION RATING": "03 / 贡献评分",
    "Every contribution leaves a mark.": "每一份贡献，都留下了痕迹。",
    "GRS RANK": "贡献等级",
    "Commits · all time": "代码提交 · 历史累计",
    "Issues opened · all time": "发起议题 · 历史累计",
    "PR reviews · past year": "PR 审查 · 近一年",
    "Repos contributed · year": "参与仓库 · 近一年",
    "Stars · all public repos": "星标 · 全部公开仓库",
    "Followers": "关注者",
    "GitHub Readme Stats formula · Public activity": "沿用 GitHub Readme Stats 公式 · 公开贡献",
    "Formula-based indicator, not an official GitHub rating.": "基于公式计算，并非 GitHub 官方评级。",
    "GitHub Readme Stats rank {level}; formula score {score:.1f} out of 100. ": "GitHub Readme Stats 贡献等级 {level}；公式得分 {score:.1f}，满分 100。",
    "commits": "代码提交",
    "issues": "发起议题",
    "reviews": "PR 审查",
    "contributed_repos": "参与仓库",
    "stars": "星标",
    "followers": "关注者",
    "Ariakage's contribution rating": "Ariakage 的贡献评分",
    "04 / PULL REQUESTS": "04 / PR 协作记录",
    "PRs opened · all time": "发起 PR · 历史累计",
    "Merged · all time": "已合并 · 历史累计",
    "Currently open": "当前未关闭",
    "Merged / all PRs": "合并率 · 已合并 / 全部 PR",
    "PRs I authored across public repositories.": "统计我在公开仓库中发起的 PR。",
    "UPDATED {updated} UTC": "更新于 {updated} UTC",
    "Ariakage's pull requests": "Ariakage 的 PR 协作记录",
    "{prs} public authored PRs; {merged} merged; {open} open; merge rate {rate}.": "共发起 {prs} 个公开 PR；已合并 {merged} 个；当前未关闭 {open} 个；合并率 {rate}。",
    "05 / THE RHYTHM OF BUILDING": "05 / 创作的节奏",
    "Small steps, a growing constellation.": "一点点积累，连成自己的星图。",
    "LAST 12 WEEKS": "最近 12 周",
    "{day}: {value} contributions": "{day}：{value} 次贡献",
    "Contributions per week · Monday start · Current week is partial": "每周贡献次数 · 周一为起点 · 本周尚未结束",
    "LAST 12 WEEKS / UPDATED {updated} UTC": "最近 12 周 / 更新于 {updated} UTC",
    "Ariakage's weekly contribution activity": "Ariakage 的每周贡献趋势",
    "Week of {day}: {value}": "{day} 所在周：{value} 次贡献",
}


def translator(locale):
    if locale not in ("en", "zh"):
        raise ValueError(f"Unsupported card locale: {locale}")

    def translate(message, **values):
        # Missing Chinese copy must fail the build instead of publishing mixed labels.
        return (ZH[message] if locale == "zh" else message).format(**values)

    return translate
