# 数据基础调研

更新时间：2026-08-24

## 结论

第一版采用“官方静态数据 + CommunityDragon 斗魂数据 + 本地局内数据 + 人工可审查规则”的组合，不依赖强化符文或斗魂装备胜率榜。

原因：

- Riot 的 Data Dragon 能稳定提供英雄、装备、版本和中文资源，但不完整覆盖斗魂强化符文。
- CommunityDragon 能提供当前版本的斗魂强化符文、中文说明、图标路径和计算参数。
- Live Client Data API 能在本机对局中提供英雄、装备、属性和游戏状态，但不能证明它会返回当前屏幕上的强化候选。
- 当前强化候选仍应从游戏画面识别；识别结果只在本地使用。
- Riot 当前政策明确禁止产品展示强化符文胜率和斗魂模式装备胜率，因此推荐依据应是机制、协同关系和当前上下文，而不是换皮胜率排行。

## 已验证的数据现状

在 2026-08-24 实际拉取并检查：

| 数据 | 结果 | 主要用途 |
| --- | ---: | --- |
| Data Dragon 最新版本 | `16.16.1` | 版本锚点 |
| 英雄 | 173 个 | 英雄 ID、中文名、基础属性、技能说明 |
| 全部装备记录 | 868 条 | 装备 ID、中文名、说明、价格、标签、地图可用性 |
| 地图 30 的斗魂装备记录 | 175 条 | 普通装备的斗魂版本、棱彩装备、锻造器等 |
| CommunityDragon 斗魂强化 | 225 个 | 强化 ID、内部名、中文名、说明、稀有度、图标、参数 |

剑魔和诺手均能通过 Data Dragon 的稳定英雄 ID 读取：

- 暗裔剑魔：`Aatrox` / `266`
- 诺克萨斯之手：`Darius` / `122`

## 数据分层

### 1. 版本静态数据

每个版本同步一次，生成不可变快照。

| 实体 | 首选来源 | 关键字段 |
| --- | --- | --- |
| 版本 | Data Dragon `versions.json` | `patch`、抓取时间、文件摘要 |
| 英雄 | Data Dragon `champion.json` 和单英雄文件 | `id`、`key`、中文名、标签、基础属性、技能 |
| 装备 | Data Dragon `item.json` | `id`、中文名、说明、属性、价格、`maps[30]`、图标 |
| 强化 | CommunityDragon `cdragon/arena/zh_cn.json` | `id`、`apiName`、中文名、说明、稀有度、图标、参数 |
| 斗魂改动 | Riot 官方版本公告 | 英雄、装备、强化的版本差异和模式专属调整 |

数据源：

- <https://ddragon.leagueoflegends.com/api/versions.json>
- <https://ddragon.leagueoflegends.com/cdn/16.16.1/data/zh_CN/champion.json>
- <https://ddragon.leagueoflegends.com/cdn/16.16.1/data/zh_CN/item.json>
- <https://raw.communitydragon.org/latest/cdragon/arena/zh_cn.json>
- <https://www.leagueoflegends.com/zh-tw/news/game-updates/league-of-legends-patch-26-16-notes/>

注意：Data Dragon 官方说明版本号不一定与每个地区客户端完全一致。国服 `realms/cn.json` 当前返回 403，第一版需要允许用户选择或自动检测版本，不能把 `latest` 永久当作国服真实版本。

### 2. 局内上下文数据

每局在本机临时生成，不上传。

| 字段 | 获取方式 | 第一版要求 |
| --- | --- | --- |
| 当前英雄 | Live Client Data API，画面识别兜底 | 必须 |
| 队友英雄 | Live Client Data API | 必须 |
| 当前装备 | Live Client Data API | 必须 |
| 当前属性、等级、金币 | Live Client Data API | 可选 |
| 当前三个强化候选 | 截图固定区域 + 图标匹配 + 中文文字识别 | 必须 |
| 已选强化 | 本地记录每次选择；画面识别校验 | 必须 |
| 当前回合、对手信息 | Live Client Data API 或画面识别 | 后续 |

官方本地接口：

- `GET https://127.0.0.1:2999/liveclientdata/gamestats`
- `GET https://127.0.0.1:2999/liveclientdata/activeplayer`
- `GET https://127.0.0.1:2999/liveclientdata/playerlist`

官方文档：<https://developer.riotgames.com/docs/lol>

不能把 Live Client Data API 当作强化候选来源。公开文档没有承诺该字段，已有同类开源工具也仍需通过画面识别读取候选。

### 3. 推荐知识数据

这部分由项目维护，不从胜率榜复制。

#### 英雄画像

```json
{
  "championId": "Aatrox",
  "roles": ["持续作战", "回复", "技能型战士"],
  "preferredStats": ["技能急速", "攻击力", "生命值", "治疗增益"],
  "antiPatterns": ["纯攻速依赖"],
  "patch": "16.16.1"
}
```

#### 强化画像

```json
{
  "augmentId": 93,
  "tags": ["成长", "持续作战", "伤害增幅"],
  "triggers": ["主动引导"],
  "benefits": ["通用伤害"],
  "conflicts": [],
  "sourcePatch": "16.16.1"
}
```

#### 协同边

```json
{
  "subject": "champion:Aatrox",
  "predicate": "synergizes_with",
  "object": "augment:93",
  "weight": 2,
  "reason": "剑魔适合持续作战，完整引导后能放大多段技能和回复收益",
  "evidence": ["mechanics"],
  "patch": "16.16.1"
}
```

每条推荐都必须能还原为若干条协同边和冲突边，不能只保存一个黑盒分数。

### 4. 反馈与验证数据

第一版只收本地、最小必要数据：

- 识别出的三个候选和识别置信度；
- 推荐顺序与理由；
- 玩家最终选择；
- 玩家对推荐的“有用 / 没用”反馈；
- 可选的最终名次；
- 客户端版本、分辨率和界面缩放。

这些数据主要用来修正识别和规则，不用于展示强化或装备胜率。

## 推荐的数据方案

### 方案 A：只用 Riot 官方数据

优点是来源最稳、合规边界最清楚。缺点是没有完整斗魂强化数据，无法完成核心体验。

### 方案 B：官方数据 + CommunityDragon + 可审查规则

这是推荐方案。Data Dragon 管英雄和装备，CommunityDragon 补强化，官方版本公告补斗魂专属改动，项目自己维护协同规则。来源可追踪、版本可冻结，也能离线运行。

### 方案 C：抓取第三方胜率榜或大规模 Match-V5 训练

不作为第一版方案。除了 API Key、采样偏差和数据质量问题，Riot 当前政策还禁止展示强化符文和斗魂装备胜率；Match-V5 的第 5、6 个强化字段也存在长期为 `0` 的公开问题。

## 本地标准数据合同

建议所有来源最终归一为以下目录，不让推荐引擎直接读取外部 JSON：

```text
data/
  raw/
    16.16.1/
      ddragon/
      communitydragon/
      patch-notes/
  normalized/
    16.16.1/
      champions.json
      items-arena.json
      augments.json
      arena-balance.json
  knowledge/
    champion-profiles.json
    augment-profiles.json
    synergy-edges.json
  fixtures/
    contexts/
    screenshots/
    expected-recommendations/
```

每份标准化文件必须包含：

- `schemaVersion`
- `gamePatch`
- `locale`
- `generatedAt`
- `sources`
- `sourceSha256`
- `records`

## 数据更新与校验

同步器按以下顺序工作：

1. 获取版本号并创建新版本目录，不覆盖旧快照。
2. 下载原始文件并保存 SHA-256。
3. 只保留 `maps[30] == true` 的斗魂装备。
4. 把强化说明中的 HTML 标签和参数占位符标准化，同时保留原文。
5. 检查 ID 唯一、中文名非空、图标存在、记录数变化幅度。
6. 对比上一个版本，输出新增、删除、改名、数值变化报告。
7. 发现异常时保持上一版可用数据，不自动发布坏快照。

最低数据测试：

- 英雄 ID 唯一，且必须包含 `Aatrox`、`Darius`；
- 斗魂装备的 `maps[30]` 必须为 `true`；
- 强化 `id` 和 `apiName` 唯一，名称与图标不能为空；
- 推荐知识中的所有英雄、装备、强化外键必须存在；
- 每条协同关系必须有中文理由和版本号；
- 同一截图在固定识别模型下应生成同一标准上下文。

## 仍需在 Windows 真机验证

以下事实不能在当前 Mac 上假装已完成：

1. 斗魂对局中 Live Client Data API 的真实返回字段和可用时机。
2. 无边框窗口、窗口模式和不同分辨率下强化卡片区域的位置。
3. 图标匹配与中文文字识别的准确率，以及界面动画的影响。
4. 已选强化是否能从 HUD 稳定复核。
5. 国服客户端版本如何可靠检测。

## 第一版数据闭环

先只覆盖剑魔和诺手：

1. 自动同步当前版本的英雄、地图 30 装备和 225 个强化。
2. 人工标注剑魔、诺手和全部强化的机制标签。
3. 建立可解释协同边，先覆盖每名英雄至少 20 个高相关强化。
4. 用构造的上下文 JSON 跑推荐结果测试。
5. 再进入 Windows 真机采样，把截图识别结果接到同一个上下文合同。

这样即使画面识别尚未完成，数据与推荐内核也可以先独立开发和测试。

## 政策与已知限制

- Riot 产品政策与 Live Client Data API：<https://developer.riotgames.com/docs/lol>
- Match-V5 第 5、6 个强化字段问题：<https://github.com/RiotGames/developer-relations/issues/1059>
- 2026 年 3v3 斗魂队列 `1750` 缺少官方队列定义：<https://github.com/RiotGames/developer-relations/issues/1159>
- CommunityDragon 数据生成方式：<https://github.com/CommunityDragon/CDTB/blob/master/cdtb/arenadata.py>

公开发布前还需要按 Riot 要求注册产品，并在产品中展示其要求的法律声明。
