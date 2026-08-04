# gateway 加 upstreams 热更新支持

**这条任务在 `ombre-brain` 仓库。**
如果 OB 仓库根目录有 `CLAUDE_PROMPT.md` 或 `AGENTS.md`，先读那个。

**前置：`b21fbc9`（Halcyon 侧）已上线。站点表的「换模型」通了，
「切站」被 gateway 挡住——这条把那个缺口补上。**

---

## 一、为什么要改（先把上一轮的争议了结）

上一轮任务书 §三 说「gateway 已经支持 upstreams 热更新，OB 一行不用改」。
**那句是错的，你的实测是对的。**

你的证据（运行时）：

```
POST /api/config {"gateway":{"upstreams":[...]}}
→ 200 {"ok":true,"updated":[],"gateway":{...}}
   updated:[] 一个键都没应用
→ /v1/models 白名单全程 27 个不变
```

我的错误来源：**我手上那份 `gateway.py` 是个 grafted 浅克隆
（`2651e2a`），里面确实有 `_apply_gateway_upstreams_config`
和 `_sanitize_gateway_upstreams_config`。但它跟 `5cb32f6`（main HEAD）
不在同一条历史上——那两个函数存在于某个未合并的分叉，main 上没有。**

**我拿一份不是线上代码的代码，推翻了你的实测证据。** 那是我的错，
你上一轮的三条结论本来就是对的。

**所以这条任务的第一件事是确认基线**（见 §三），别再重复这个错误。

---

## 二、为什么不选「半套」

你给的选项 2 是「站点表只控制选模型，加站删站仍走 config.yaml」。
**不能选，因为现在这个状态比不做更糟——你自己指出来的：**

```
UI 里切到 cc → activate 返回 200 → DB 切了
→ 但 gateway 不认识 cc → 发消息 400
```

**那不是「功能少一半」，是「UI 会骗你」。** 界面说切成功了，
实际发消息报错。任务书 §6b 想避免的正是这个，而当前状态必然产生它。

**所以要么补上 gateway 支持，要么把 activate 那条路堵死。**
补上更值——改动不大，而且 §四 有一份可用的参考实现。

---

## 三、第一步：确认基线（**做之前必须做**）

**我那份源码不能当真相，但可以当参考。所以先分清哪些东西 main 上有、
哪些没有。**

```bash
# 这两个是核心，我这份有，你说 main 没有 —— 确认
grep -n '_apply_gateway_upstreams_config' gateway.py
grep -n '_sanitize_gateway_upstreams_config' gateway.py

# 这五个是参考实现的依赖，我这份都有，但不知道 main 上有没有
grep -n 'def _normalize_upstream_protocol' gateway.py
grep -n 'def _sanitize_env_names' gateway.py
grep -n 'def _sanitize_upstream_model_entries' gateway.py
grep -n 'def _refresh_upstream_model_summary' gateway.py
grep -n 'def _load_upstreams' gateway.py

# server.py 那边有没有等价物（可以复用或参考）
grep -n '_dashboard_sanitize_gateway_upstreams' server.py
grep -n '_dashboard_normalize_upstream_protocol' server.py
grep -n '_dashboard_sanitize_env_names' server.py
grep -n '_dashboard_sanitize_upstream_models' server.py
```

**报告里列清楚哪些存在哪些不存在。** 缺的要一起写。

**如果 `server.py` 那份 sanitize 逻辑完整，优先考虑复用而不是抄一份。**
逻辑写两份是屎山的起点（Kitty 的原话）。**但别为了复用做大重构** ——
如果 server.py 那份耦合了 dashboard 的东西不好抽，抄一份也行，
在报告里说明选择。

---

## 四、参考实现（我那份分叉里的，57 行）

**这是参考，不是照抄清单。** main 上缺什么依赖、字段名对不对，
按 §三 的确认结果调整。

```python
    def _sanitize_gateway_upstreams_config(self, raw_upstreams: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_upstreams, list):
            raise ValueError("gateway.upstreams must be a list")
        existing_by_name = {
            str(item.get("name") or "").strip(): item
            for item in self.gateway_cfg.get("upstreams", [])
            if isinstance(item, dict)
        }
        upstreams: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for index, raw in enumerate(raw_upstreams, start=1):
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or f"upstream-{index}").strip() or f"upstream-{index}"
            if name in seen_names:
                raise ValueError(f'duplicate gateway upstream name "{name}"')
            seen_names.add(name)
            sanitized: dict[str, Any] = {
                "name": name,
                "protocol": self._normalize_upstream_protocol(
                    raw.get("protocol") or raw.get("api_format") or raw.get("type")
                ),
                "base_url": str(raw.get("base_url") or "").strip().rstrip("/"),
            }
            env_names = self._sanitize_env_names(raw.get("api_key_envs", raw.get("api_key_env", [])))
            if env_names:
                sanitized["api_key_envs"] = env_names
            for key in (
                "default_model",
                "prompt_cache",
                "prompt_cache_retention",
                "anthropic_version",
                "anthropic_beta",
            ):
                value = str(raw.get(key) or "").strip()
                if value:
                    sanitized[key] = value
            models = self._sanitize_upstream_model_entries(raw.get("models", []))
            if models:
                sanitized["models"] = models

            existing = existing_by_name.get(name, {})
            for secret_key in ("api_key", "api_keys"):
                if secret_key in raw:
                    sanitized[secret_key] = raw[secret_key]
                elif isinstance(existing, dict) and secret_key in existing:
                    sanitized[secret_key] = existing[secret_key]
            upstreams.append(sanitized)
        return upstreams

    def _apply_gateway_upstreams_config(self, raw_upstreams: Any) -> list[str]:
        upstreams = self._sanitize_gateway_upstreams_config(raw_upstreams)
        self.gateway_cfg["upstreams"] = upstreams
        self.upstreams = self._load_upstreams()
        self._refresh_upstream_model_summary()
        self.upstream_key_cooldowns.clear()
        return ["gateway.upstreams"]
```

**四件事这段做对了，实现时别漏：**

```
1  existing_by_name 继承 api_key / api_keys
   → 不传 key 时从现有配置继承，不会丢
2  重名抛 ValueError
   → handle_config 要 catch 成 400，不能 500
3  self.upstreams = self._load_upstreams()
   → 这是热重载的关键，光改 gateway_cfg 不生效
4  upstream_key_cooldowns.clear()
   → 换了上游要清 key 冷却，不然新站可能被旧冷却挡住
```

---

## 五、接进 handle_config

`gateway.py:1029` `handle_config` 的 POST 分支现在只调五个：

```
_apply_gateway_memory_config
_apply_memory_diffusion_config
_apply_reranker_config
_apply_persona_config
_apply_dream_config
```

**两种接法，你选：**

```
A  在 _apply_gateway_memory_config（715 行）开头加
   if "upstreams" in payload:
       updated.extend(self._apply_gateway_upstreams_config(payload["upstreams"]))
   → 跟我那份分叉的做法一致，改动最小

B  在 handle_config 里单独加一个分支
   → 语义更清楚（upstreams 不是 memory config）
   → 但要多改一处
```

**我倾向 A**，因为 payload 结构是 `{"gateway": {...}}`，
upstreams 本来就在 gateway 这一层里。**但你可以选 B，在报告里说明。**

**ValueError 要转成 400，带具体原因**（比如 duplicate name），
不要让它变成 500。现在 Halcyon 侧靠这个错误信息做「同名保存前挡」。

---

## 六、顺手补 GET /api/config 的鉴权

**这是个真漏，跟这条一起改省一次部署。**

```
现在裸 GET /api/config（不带任何头）→ 200 + 完整配置
```

泄露内容：所有 upstream 的 base_url、models 白名单、
persona 配置、记忆调参。**key 是掩码的，但拓扑全暴露。**

`handle_config`（1029 行）第一行应该已经有 `_authorize`——
**如果有却不生效，那就跟 8-04 凌晨那个 cookie jar 是同一类问题**
（那次是 gateway 的共享 httpx client 把登录 session 借给了匿名请求，
commit `e08e0ff` 修的）。

```
先确认 _authorize 在不在、为什么没挡住
修完实测：裸 GET → 401，带 Bearer → 200
```

**不要顺手改 _authorize 本身的逻辑**（那影响所有端点），
只让 /api/config 正确走它。

---

## 七、验证

**必须实测。这条改的是生产聊天主链的配置入口。**

```
0  改之前先备份当前 upstreams
   Halcyon 侧的 gateway_upstreams_backup.json 已经有一份（含真 key）
   但 OB 侧也自己存一份，别依赖另一个仓库

1  python3 -m py_compile gateway.py
2  跑现有测试套件，特别是 tests/test_gateway.py
   → 确认没碰坏 tool_calls 透传那些契约

3  POST 一个 upstreams（先加一个假站，不删现有的）
   → 确认返回 updated 里有 "gateway.upstreams"
   → 确认 GET /v1/models 白名单变了（多了那个假站的模型）
   → 确认现有两个站（xn-station / jixiang）还在，key 没丢

4  POST 一个重名的
   → 400，错误信息含 duplicate

5  POST 不带 api_key 的更新（只改 models）
   → 确认原来的 key 还在（从 existing 继承）
   → 用一条真实消息验证那个站还能用

6  裸 GET /api/config
   → 401

7  带 Bearer GET /api/config
   → 200

8  把假站删掉，恢复成 xn-station + jixiang
   → 确认 /v1/models 回到 27 个
   → 发一条真实消息，确认聊天正常

9  最后：让 Halcyon 那边试一次真的切站
   （UI 里切到 cc → 发消息 → 确认走了 cc）
   ← 这条是整件事的目标，做不到就是没做完
```

**第 3 和第 5 步最关键。** 第 3 步证明热更新真生效，
第 5 步证明不会把 key 弄丢。

---

## 八、不要做

```
不要改 _authorize 本身的逻辑（只让 /api/config 正确走它）
不要动 /v1/chat/completions、/v1/messages、tool_calls 透传
不要动记忆注入、persona、prompt cache 那些
不要动 /mcp 反代
不要动 server.py 那边的 dashboard 端点
不要在没备份的情况下 POST upstreams
不要为了复用做大重构（复用不了就抄一份，说明理由）
不要把我 §四 那段参考实现当成必须逐字照抄的清单
  → main 上缺什么依赖要按 §三 的结果调整
```

---

## 九、报告要写

```
§三 的确认结果：哪些函数 main 上有、哪些没有
  （这条最重要，它决定了我上一轮错在哪）

选了接法 A 还是 B，为什么
复用了 server.py 的 sanitize 还是抄了一份，为什么

第 3 / 5 步的实测输出（updated 数组、/v1/models 数量变化）
第 6 / 7 步鉴权的实测结果
  如果 _authorize 本来就在却没挡住，根因是什么

第 9 步 Halcyon 切站的实测结果

你觉得最危险的一处是什么
```

---

## 十、边界

**改动在 OB 的 gateway.py，那是聊天主链所在的进程。**

```
最坏情况：POST 了一个坏的 upstreams → 聊天用不了
恢复方式：POST 回备份的那份
所以第 0 步的备份是硬要求
```

**任何一步失败，停下来报告，不要继续。**

**如果发现 main 上缺的依赖太多、改动会超出「加一个分支」的规模，
停下来说明，我重新评估。**

---

改完 commit + push。**别开新任务。**