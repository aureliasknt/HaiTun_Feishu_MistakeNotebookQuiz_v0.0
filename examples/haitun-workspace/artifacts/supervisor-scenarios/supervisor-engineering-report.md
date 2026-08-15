# 副 Agent稳定性与工程评估报告

## 证据边界

本次完整场景为 DETERMINISTIC MOCK；真实上游错误单独保留，不能据此声称真实 LLM 稳定性已经达标。

## 样本

- 用户数：2
- 总轮次：16
- Advice来源分布：`{"live": 16}`
- 用户哈希隔离：通过
- Supervisor输入不含主回答/reasoning/tool results：通过

## 延迟策略

- 第一轮不等待实时 Advice，在 after-turn 预热。
- 第二轮起必须经过 live/cache/unavailable 路径。
- 同步预算：20 秒。
- 当前确定性模式不能提供真实 P50/P95；需真实 Session 指标后计算。

## 真实错误

- `APIConnectionError('Connection error.') — 真实 DeepSeek 上游连接失败`

## 当前工程成熟度

- 协议、身份隔离、缓存、地图版本、热力图历史：已有自动化覆盖。
- 真实多轮网络稳定性、跨进程恢复、后台 enrichment 生命周期：仍需实验。
- 不能仅凭 Mock 证明稳定超过单 Agent；需要同模型盲评和真实延迟数据。
