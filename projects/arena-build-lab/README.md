# 斗魂构筑实验室

状态：静态数据与本地内容库已可构建。

## 已确认目标

做一个能够结合当前对局上下文，为《英雄联盟》斗魂竞技场提供构筑选择解释和后续路线建议的本地游戏辅助工具。

## 已确认体验

- 助手需要获取当前游戏界面中的强化候选、已有构筑等信息。
- 不能把大量内容交给玩家手动录入。
- 纯网页查询不是目标形态。
- 推荐需要给出多个选择和理由，不自动操作游戏。

## 当前阶段

静态数据底座已经进入实现阶段。当前先固定英雄、斗魂装备和强化的数据同步、标准化及版本校验，再处理 Windows 游戏画面获取。

## 数据底座

当前数据来源：

- Riot Data Dragon：英雄、技能和地图 30 装备。
- CommunityDragon：斗魂强化的中文名称、说明、图标路径和参数。

同步结果统一写入 `data/normalized/<版本>/`，再构建为应用直接查询的 SQLite 内容库。

```bash
python3 scripts/sync_data.py
python3 scripts/build_database.py
python3 -m unittest discover -s tests -v
```

指定版本：

```bash
python3 scripts/sync_data.py --patch 16.16.1
python3 scripts/build_database.py --patch 16.16.1
```

生成结果位于 `dist/arena-content-16.16.1.db`。该文件是可重新生成的运行产物，不提交到 Git。

快速查询：

```bash
sqlite3 -header -column dist/arena-content-16.16.1.db \
  "SELECT id, name, title FROM champions WHERE id IN ('Aatrox', 'Darius');"
```

当前快照包含全部英雄摘要、剑魔与诺手技能详情、斗魂装备目录，以及全部斗魂强化。详细来源与字段见 `docs/data-foundation.md`，存储分层见 `docs/storage-design.md`。
