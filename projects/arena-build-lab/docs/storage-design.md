# 数据存储设计

## 结论

项目采用“JSON 快照 + SQLite 内容库”的两层结构：

1. `data/normalized/<版本>/` 保存可审查、可比较的标准化 JSON，是内容库的构建输入。
2. `dist/arena-content-<版本>.db` 是应用直接查询的只读 SQLite 数据库，由脚本生成，不提交到 Git。

SQLite 不是缩小版 MySQL。两者都使用关系模型和 SQL，但 SQLite 是嵌入应用的单文件数据库，不需要单独部署数据库服务，适合 Windows 本地助手。

## 内容库

`database/content-schema.sql` 把数据分成两类。

游戏事实表：

- `champions`：英雄基础信息。
- `champion_abilities`：英雄被动和 Q/W/E/R 技能。
- `items`：斗魂装备及其属性、合成关系和购买状态。
- `augments`：强化名称、说明、等级、参数和图标路径。
- `content_metadata`：游戏版本、语言、schema 版本和来源清单。

推荐知识表：

- `tags`：持续作战、治疗、护盾、移速等标准标签。
- `entity_tags`：英雄、装备、强化与标签之间的关系。
- `synergy_rules`：构筑之间的协同或冲突规则、权重、理由和证据。

事实表由同步数据生成；知识表后续由我们维护。推荐逻辑只引用两类数据，不改写游戏事实。

## 本地位置

开发阶段生成到：

```text
projects/arena-build-lab/dist/arena-content-16.16.1.db
```

Windows 客户端发布后，内容库计划安装到：

```text
%LOCALAPPDATA%\ArenaBuildLab\content\arena-content-<版本>.db
```

用户设置、识别纠错和本地历史以后单独保存到 `user.db`。内容升级时只替换内容库，不覆盖用户数据。

## 更新流程

```text
拉取指定版本数据
  -> 标准化 JSON
  -> 校验版本与数量
  -> 构建临时 SQLite
  -> 完整性检查
  -> 原子替换正式内容库
```

构建命令：

```bash
python3 scripts/build_database.py --patch 16.16.1
```

脚本只在全部导入和完整性检查成功后替换目标文件，构建失败不会留下半成品正式库。
