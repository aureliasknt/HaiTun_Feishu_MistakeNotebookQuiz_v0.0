# 后台副 Agent 双场景破圈实验报告

## 证据真实性说明

本报告优先尝试真实 LLM。下列完整场景标记为 `DETERMINISTIC MOCK`，用于在上游不可用时验证协议、画像、热力图、知识地图和破圈信息流；不得视为真实模型质量证据。

### 真实调用错误

- `APIConnectionError('Connection error.') — 真实 DeepSeek 上游连接失败`

## CEO：是否采用 CI/CD

- user_id: `demo-ceo-cicd`
- profile_id: `executive-decision`
- user_hash: `fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36`

### 第 1 轮 — DETERMINISTIC MOCK

#### 用户

我是公司的 CEO。我们是否应该使用 CI/CD？请先给我一个直接判断。

#### 主 Agent

直接判断：应该采用 CI/CD，但不要把它理解为一次性采购工具；应从最小流水线开始。当前先确认发布痛点、测试基础和回滚能力。

#### 副 Agent 行为

- 是否破圈：`False`
- 类型：`none`
- 分数：`0.0`
- 原因：当前是首轮信号，先回答直接问题并观察。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 1,
  "current_user_question": "我是公司的 CEO。我们是否应该使用 CI/CD？请先给我一个直接判断。",
  "stage_profile": {
    "depth": 0.15,
    "goal": 0.45,
    "familiarity": 0.2,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ],
    "breakout_count": 6
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-ceo-cicd-1",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 1,
  "classification": {
    "is_learning": true,
    "domain": "software_delivery_governance",
    "topic": "cicd_decision",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.15,
    "goal": 0.45,
    "familiarity": 0.2,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": false,
    "type": "none",
    "score": 0.0,
    "reason": "当前是首轮信号，先回答直接问题并观察。",
    "directions": [],
    "evidence": [
      "我是公司的 CEO。我们是否应该使用 CI/CD？请先给我一个直接判断。"
    ]
  },
  "latent_need": {
    "detected": false,
    "need": "",
    "missing_dimensions": [],
    "confidence": 0.0
  },
  "profile_shift": {
    "detected": false,
    "from": "",
    "to": "",
    "evidence": [],
    "confidence": 0.0
  },
  "response_strategy": {
    "answer_depth": "concise",
    "answer_scope": "framework",
    "goal_mode": "decide",
    "terminology": "explain_key_terms",
    "breakout_integration": "none",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "cicd_decision"
    ],
    "branch_additions": []
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 0,
    "visited_nodes": [],
    "breakout_count": 0
  },
  "after": {
    "question_count": 1,
    "visited_nodes": [
      "cicd_decision"
    ],
    "breakout_count": 0
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "",
    "nodes": []
  },
  "after": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision"
    ]
  }
}
```

### 第 2 轮 — DETERMINISTIC MOCK

#### 用户

实施它要花多少钱，短期内能给业务带来什么收益？

#### 主 Agent

短期成本主要是工程时间、流水线环境和测试补齐；收益是减少人工发布、缩短反馈周期并降低事故恢复成本。决策前应把发布事故损失和等待时间计入成本，而不只看工具订阅费。

💡 破圈效果：把是否采用工具重构为交付风险和投资回报决策；先评估自动化测试、回滚能力和变更失败率。

#### 副 Agent 行为

- 是否破圈：`True`
- 类型：`reframe`
- 分数：`0.6799999999999999`
- 原因：用户已进入第 2 个认知节点，需要用 reframe 补足决策或治理维度。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 2,
  "current_user_question": "实施它要花多少钱，短期内能给业务带来什么收益？",
  "stage_profile": {
    "depth": 0.27,
    "goal": 0.55,
    "familiarity": 0.28,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ],
    "breakout_count": 6
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-ceo-cicd-2",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 2,
  "classification": {
    "is_learning": true,
    "domain": "software_delivery_governance",
    "topic": "cicd_economics",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.27,
    "goal": 0.55,
    "familiarity": 0.28,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": true,
    "type": "reframe",
    "score": 0.6799999999999999,
    "reason": "用户已进入第 2 个认知节点，需要用 reframe 补足决策或治理维度。",
    "directions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率"
    ],
    "evidence": [
      "实施它要花多少钱，短期内能给业务带来什么收益？"
    ]
  },
  "latent_need": {
    "detected": true,
    "need": "把是否采用工具重构为交付风险和投资回报决策",
    "missing_dimensions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率"
    ],
    "confidence": 0.82
  },
  "profile_shift": {
    "detected": false,
    "from": "",
    "to": "",
    "evidence": [],
    "confidence": 0.0
  },
  "response_strategy": {
    "answer_depth": "balanced",
    "answer_scope": "framework",
    "goal_mode": "decide",
    "terminology": "explain_key_terms",
    "breakout_integration": "integrated_section",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "cicd_economics"
    ],
    "branch_additions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率"
    ]
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 1,
    "visited_nodes": [
      "cicd_decision"
    ],
    "breakout_count": 0
  },
  "after": {
    "question_count": 2,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics"
    ],
    "breakout_count": 1
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision"
    ]
  },
  "after": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率"
    ]
  }
}
```

### 第 3 轮 — DETERMINISTIC MOCK

#### 用户

我们有 24 名研发，每两周发布一次，自动化测试覆盖率约 30%，过去半年发生过三次发布事故。

#### 主 Agent

你们具备试点价值但不适合立刻全面自动发布：24 人团队和三次事故说明收益空间明显，30% 测试覆盖率则意味着应先建设 CI、质量门禁和一键回滚，再逐步开放 CD。

💡 破圈效果：把是否采用工具重构为交付风险和投资回报决策；先评估自动化测试、回滚能力和变更失败率；用最小可行流水线替代一次性全面改造。

#### 副 Agent 行为

- 是否破圈：`True`
- 类型：`broaden`
- 分数：`0.74`
- 原因：用户已进入第 3 个认知节点，需要用 broaden 补足决策或治理维度。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 3,
  "current_user_question": "我们有 24 名研发，每两周发布一次，自动化测试覆盖率约 30%，过去半年发生过三次发布事故。",
  "stage_profile": {
    "depth": 0.39,
    "goal": 0.65,
    "familiarity": 0.36,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ],
    "breakout_count": 6
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-ceo-cicd-3",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 3,
  "classification": {
    "is_learning": true,
    "domain": "software_delivery_governance",
    "topic": "delivery_baseline",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.39,
    "goal": 0.65,
    "familiarity": 0.36,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": true,
    "type": "broaden",
    "score": 0.74,
    "reason": "用户已进入第 3 个认知节点，需要用 broaden 补足决策或治理维度。",
    "directions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ],
    "evidence": [
      "我们有 24 名研发，每两周发布一次，自动化测试覆盖率约 30%，过去半年发生过三次发布事故。"
    ]
  },
  "latent_need": {
    "detected": true,
    "need": "把是否采用工具重构为交付风险和投资回报决策",
    "missing_dimensions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ],
    "confidence": 0.82
  },
  "profile_shift": {
    "detected": true,
    "from": "概念了解",
    "to": "落地决策",
    "evidence": [
      "连续问题从定义转向风险、控制或实施。"
    ],
    "confidence": 0.8
  },
  "response_strategy": {
    "answer_depth": "balanced",
    "answer_scope": "framework",
    "goal_mode": "decide",
    "terminology": "explain_key_terms",
    "breakout_integration": "integrated_section",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "delivery_baseline"
    ],
    "branch_additions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ]
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 2,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics"
    ],
    "breakout_count": 1
  },
  "after": {
    "question_count": 3,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline"
    ],
    "breakout_count": 2
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率"
    ]
  },
  "after": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造"
    ]
  }
}
```

### 第 4 轮 — DETERMINISTIC MOCK

#### 用户

基于这些情况，请明确建议：现在全面采用、暂缓，还是分阶段采用？

#### 主 Agent

明确建议：分阶段采用。第一阶段自动构建、测试和安全扫描；第二阶段自动部署测试环境；达到门槛后再对低风险服务启用生产发布，高风险变更保留人工批准。

💡 破圈效果：把是否采用工具重构为交付风险和投资回报决策；先评估自动化测试、回滚能力和变更失败率；用最小可行流水线替代一次性全面改造。

#### 副 Agent 行为

- 是否破圈：`True`
- 类型：`operationalize`
- 分数：`0.8`
- 原因：用户已进入第 4 个认知节点，需要用 operationalize 补足决策或治理维度。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 4,
  "current_user_question": "基于这些情况，请明确建议：现在全面采用、暂缓，还是分阶段采用？",
  "stage_profile": {
    "depth": 0.51,
    "goal": 0.75,
    "familiarity": 0.44,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ],
    "breakout_count": 6
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-ceo-cicd-4",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 4,
  "classification": {
    "is_learning": true,
    "domain": "software_delivery_governance",
    "topic": "adoption_decision",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.51,
    "goal": 0.75,
    "familiarity": 0.44,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": true,
    "type": "operationalize",
    "score": 0.8,
    "reason": "用户已进入第 4 个认知节点，需要用 operationalize 补足决策或治理维度。",
    "directions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ],
    "evidence": [
      "基于这些情况，请明确建议：现在全面采用、暂缓，还是分阶段采用？"
    ]
  },
  "latent_need": {
    "detected": true,
    "need": "把是否采用工具重构为交付风险和投资回报决策",
    "missing_dimensions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ],
    "confidence": 0.82
  },
  "profile_shift": {
    "detected": true,
    "from": "概念了解",
    "to": "落地决策",
    "evidence": [
      "连续问题从定义转向风险、控制或实施。"
    ],
    "confidence": 0.8
  },
  "response_strategy": {
    "answer_depth": "balanced",
    "answer_scope": "framework",
    "goal_mode": "decide",
    "terminology": "explain_key_terms",
    "breakout_integration": "integrated_section",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "adoption_decision"
    ],
    "branch_additions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ]
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 3,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline"
    ],
    "breakout_count": 2
  },
  "after": {
    "question_count": 4,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision"
    ],
    "breakout_count": 3
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造"
    ]
  },
  "after": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision"
    ]
  }
}
```

### 第 5 轮 — DETERMINISTIC MOCK

#### 用户

给我一个 90 天试点方案，以及我在管理会上应该看的指标。

#### 主 Agent

90 天试点：第 1—30 天选一个低风险服务建立流水线；31—60 天补关键测试、回滚和审计；61—90 天扩大到两三个服务。管理会查看部署频率、交付周期、变更失败率、平均恢复时间、流水线通过率和每次发布人工耗时，并据此决定扩大投入。

💡 破圈效果：把是否采用工具重构为交付风险和投资回报决策；先评估自动化测试、回滚能力和变更失败率；用最小可行流水线替代一次性全面改造。

#### 副 Agent 行为

- 是否破圈：`True`
- 类型：`operationalize`
- 分数：`0.86`
- 原因：用户已进入第 5 个认知节点，需要用 operationalize 补足决策或治理维度。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 5,
  "current_user_question": "给我一个 90 天试点方案，以及我在管理会上应该看的指标。",
  "stage_profile": {
    "depth": 0.63,
    "goal": 0.8500000000000001,
    "familiarity": 0.52,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ],
    "breakout_count": 6
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-ceo-cicd-5",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 5,
  "classification": {
    "is_learning": true,
    "domain": "software_delivery_governance",
    "topic": "pilot_metrics",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.63,
    "goal": 0.8500000000000001,
    "familiarity": 0.52,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": true,
    "type": "operationalize",
    "score": 0.86,
    "reason": "用户已进入第 5 个认知节点，需要用 operationalize 补足决策或治理维度。",
    "directions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ],
    "evidence": [
      "给我一个 90 天试点方案，以及我在管理会上应该看的指标。"
    ]
  },
  "latent_need": {
    "detected": true,
    "need": "把是否采用工具重构为交付风险和投资回报决策",
    "missing_dimensions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ],
    "confidence": 0.82
  },
  "profile_shift": {
    "detected": true,
    "from": "概念了解",
    "to": "落地决策",
    "evidence": [
      "连续问题从定义转向风险、控制或实施。"
    ],
    "confidence": 0.8
  },
  "response_strategy": {
    "answer_depth": "balanced",
    "answer_scope": "framework",
    "goal_mode": "decide",
    "terminology": "explain_key_terms",
    "breakout_integration": "integrated_section",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "pilot_metrics"
    ],
    "branch_additions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ]
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 4,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision"
    ],
    "breakout_count": 3
  },
  "after": {
    "question_count": 5,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics"
    ],
    "breakout_count": 4
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision"
    ]
  },
  "after": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics"
    ]
  }
}
```

### 第 6 轮 — DETERMINISTIC MOCK

#### 用户

先不要展开技术细节，用三句话告诉我为什么不是全面采用。

#### 主 Agent

三句话：你们已有事故成本，值得采用；测试覆盖率只有 30%，不适合一步到位；先试点并用结果决定扩大，风险和投入都更可控。

#### 副 Agent 行为

- 是否破圈：`False`
- 类型：`none`
- 分数：`0.0`
- 原因：当前是首轮信号，先回答直接问题并观察。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 6,
  "current_user_question": "先不要展开技术细节，用三句话告诉我为什么不是全面采用。",
  "stage_profile": {
    "depth": 0.75,
    "goal": 0.95,
    "familiarity": 0.6000000000000001,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ],
    "breakout_count": 6
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-ceo-cicd-6",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 6,
  "classification": {
    "is_learning": true,
    "domain": "software_delivery_governance",
    "topic": "executive_summary",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.75,
    "goal": 0.95,
    "familiarity": 0.6000000000000001,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": false,
    "type": "none",
    "score": 0.0,
    "reason": "当前是首轮信号，先回答直接问题并观察。",
    "directions": [],
    "evidence": [
      "先不要展开技术细节，用三句话告诉我为什么不是全面采用。"
    ]
  },
  "latent_need": {
    "detected": false,
    "need": "",
    "missing_dimensions": [],
    "confidence": 0.0
  },
  "profile_shift": {
    "detected": true,
    "from": "概念了解",
    "to": "落地决策",
    "evidence": [
      "连续问题从定义转向风险、控制或实施。"
    ],
    "confidence": 0.8
  },
  "response_strategy": {
    "answer_depth": "balanced",
    "answer_scope": "framework",
    "goal_mode": "decide",
    "terminology": "explain_key_terms",
    "breakout_integration": "none",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "executive_summary"
    ],
    "branch_additions": []
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 5,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics"
    ],
    "breakout_count": 4
  },
  "after": {
    "question_count": 6,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary"
    ],
    "breakout_count": 4
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics"
    ]
  },
  "after": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary"
    ]
  }
}
```

### 第 7 轮 — DETERMINISTIC MOCK

#### 用户

现在重新深入：组织权限、审计和回滚责任应该怎么分？

#### 主 Agent

权限上由平台团队维护流水线，业务团队拥有服务，安全团队设置门禁；审计记录代码、批准、构建和部署；失败时服务负责人决定回滚，重大事故由统一指挥机制接管。

💡 破圈效果：把是否采用工具重构为交付风险和投资回报决策；先评估自动化测试、回滚能力和变更失败率；用最小可行流水线替代一次性全面改造。

#### 副 Agent 行为

- 是否破圈：`True`
- 类型：`deepen`
- 分数：`0.95`
- 原因：用户已进入第 7 个认知节点，需要用 deepen 补足决策或治理维度。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 7,
  "current_user_question": "现在重新深入：组织权限、审计和回滚责任应该怎么分？",
  "stage_profile": {
    "depth": 0.87,
    "goal": 1.0,
    "familiarity": 0.6799999999999999,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ],
    "breakout_count": 6
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-ceo-cicd-7",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 7,
  "classification": {
    "is_learning": true,
    "domain": "software_delivery_governance",
    "topic": "delivery_accountability",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.87,
    "goal": 1.0,
    "familiarity": 0.6799999999999999,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": true,
    "type": "deepen",
    "score": 0.95,
    "reason": "用户已进入第 7 个认知节点，需要用 deepen 补足决策或治理维度。",
    "directions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ],
    "evidence": [
      "现在重新深入：组织权限、审计和回滚责任应该怎么分？"
    ]
  },
  "latent_need": {
    "detected": true,
    "need": "把是否采用工具重构为交付风险和投资回报决策",
    "missing_dimensions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ],
    "confidence": 0.82
  },
  "profile_shift": {
    "detected": true,
    "from": "概念了解",
    "to": "落地决策",
    "evidence": [
      "连续问题从定义转向风险、控制或实施。"
    ],
    "confidence": 0.8
  },
  "response_strategy": {
    "answer_depth": "balanced",
    "answer_scope": "framework",
    "goal_mode": "decide",
    "terminology": "explain_key_terms",
    "breakout_integration": "integrated_section",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "delivery_accountability"
    ],
    "branch_additions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ]
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 6,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary"
    ],
    "breakout_count": 4
  },
  "after": {
    "question_count": 7,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability"
    ],
    "breakout_count": 5
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary"
    ]
  },
  "after": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability"
    ]
  }
}
```

### 第 8 轮 — DETERMINISTIC MOCK

#### 用户

把 CI/CD 决策和公司的整体风险治理联系起来，给我最终董事会建议。

#### 主 Agent

董事会建议：批准分阶段 CI/CD计划，把它纳入技术风险治理而非单纯工具采购；设定风险容忍度、责任人和季度指标；只有试点同时改善交付速度和变更失败率才扩大投资。

💡 破圈效果：把是否采用工具重构为交付风险和投资回报决策；先评估自动化测试、回滚能力和变更失败率；用最小可行流水线替代一次性全面改造。

#### 副 Agent 行为

- 是否破圈：`True`
- 类型：`cross_domain`
- 分数：`0.95`
- 原因：用户已进入第 8 个认知节点，需要用 cross_domain 补足决策或治理维度。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 8,
  "current_user_question": "把 CI/CD 决策和公司的整体风险治理联系起来，给我最终董事会建议。",
  "stage_profile": {
    "depth": 0.99,
    "goal": 1.0,
    "familiarity": 0.76,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ],
    "breakout_count": 6
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-ceo-cicd-8",
  "user_id_hash": "fbd00529fa0367fa39f898b4fca76cc1505ee4cec34a4cb3b544b5cf25339e36",
  "profile_id": "executive-decision",
  "turn_index": 8,
  "classification": {
    "is_learning": true,
    "domain": "software_delivery_governance",
    "topic": "enterprise_risk",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.99,
    "goal": 1.0,
    "familiarity": 0.76,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": true,
    "type": "cross_domain",
    "score": 0.95,
    "reason": "用户已进入第 8 个认知节点，需要用 cross_domain 补足决策或治理维度。",
    "directions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ],
    "evidence": [
      "把 CI/CD 决策和公司的整体风险治理联系起来，给我最终董事会建议。"
    ]
  },
  "latent_need": {
    "detected": true,
    "need": "把是否采用工具重构为交付风险和投资回报决策",
    "missing_dimensions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ],
    "confidence": 0.82
  },
  "profile_shift": {
    "detected": true,
    "from": "概念了解",
    "to": "落地决策",
    "evidence": [
      "连续问题从定义转向风险、控制或实施。"
    ],
    "confidence": 0.8
  },
  "response_strategy": {
    "answer_depth": "balanced",
    "answer_scope": "framework",
    "goal_mode": "decide",
    "terminology": "explain_key_terms",
    "breakout_integration": "integrated_section",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "enterprise_risk"
    ],
    "branch_additions": [
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "用最小可行流水线替代一次性全面改造"
    ]
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 7,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability"
    ],
    "breakout_count": 5
  },
  "after": {
    "question_count": 8,
    "visited_nodes": [
      "cicd_decision",
      "cicd_economics",
      "delivery_baseline",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ],
    "breakout_count": 6
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability"
    ]
  },
  "after": {
    "domain": "software_delivery_governance",
    "nodes": [
      "cicd_decision",
      "cicd_economics",
      "把是否采用工具重构为交付风险和投资回报决策",
      "先评估自动化测试、回滚能力和变更失败率",
      "delivery_baseline",
      "用最小可行流水线替代一次性全面改造",
      "adoption_decision",
      "pilot_metrics",
      "executive_summary",
      "delivery_accountability",
      "enterprise_risk"
    ]
  }
}
```

## 法律顾问：Agent 治理

- user_id: `demo-legal-agent-governance`
- profile_id: `legal-learning`
- user_hash: `82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3`

### 第 1 轮 — DETERMINISTIC MOCK

#### 用户

我是科技公司的法律顾问，懂法律但对 Agent 一无所知。请先解释 Agent 是什么。

#### 主 Agent

Agent 是能围绕目标持续观察、规划、调用工具并执行动作的软件主体。与只生成文字的模型相比，关键差别是它可能改变外部状态，因此法律分析必须关注权限、行为链和可追责证据。

#### 副 Agent 行为

- 是否破圈：`False`
- 类型：`none`
- 分数：`0.0`
- 原因：当前是首轮信号，先回答直接问题并观察。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 1,
  "current_user_question": "我是科技公司的法律顾问，懂法律但对 Agent 一无所知。请先解释 Agent 是什么。",
  "stage_profile": {
    "depth": 0.15,
    "goal": 0.45,
    "familiarity": 0.35,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ],
    "breakout_count": 7
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-legal-agent-governance-1",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 1,
  "classification": {
    "is_learning": true,
    "domain": "ai_agent_governance",
    "topic": "agent_basics",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.15,
    "goal": 0.45,
    "familiarity": 0.35,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": false,
    "type": "none",
    "score": 0.0,
    "reason": "当前是首轮信号，先回答直接问题并观察。",
    "directions": [],
    "evidence": [
      "我是科技公司的法律顾问，懂法律但对 Agent 一无所知。请先解释 Agent 是什么。"
    ]
  },
  "latent_need": {
    "detected": false,
    "need": "",
    "missing_dimensions": [],
    "confidence": 0.0
  },
  "profile_shift": {
    "detected": false,
    "from": "",
    "to": "",
    "evidence": [],
    "confidence": 0.0
  },
  "response_strategy": {
    "answer_depth": "concise",
    "answer_scope": "framework",
    "goal_mode": "explain",
    "terminology": "explain_key_terms",
    "breakout_integration": "none",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "agent_basics"
    ],
    "branch_additions": []
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 0,
    "visited_nodes": [],
    "breakout_count": 0
  },
  "after": {
    "question_count": 1,
    "visited_nodes": [
      "agent_basics"
    ],
    "breakout_count": 0
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "",
    "nodes": []
  },
  "after": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics"
    ]
  }
}
```

### 第 2 轮 — DETERMINISTIC MOCK

#### 用户

Agent 和普通聊天机器人、传统自动化程序到底有什么区别？

#### 主 Agent

聊天机器人通常一问一答；传统自动化按预写规则运行；Agent 会根据环境选择下一步并调用工具。边界不在名称，而在自主程度、可访问资源、影响范围和人类是否批准关键动作。

💡 破圈效果：用感知—规划—调用工具—执行—记录解释 Agent 生命周期；按自主程度和影响范围划分风险等级。

#### 副 Agent 行为

- 是否破圈：`True`
- 类型：`deepen`
- 分数：`0.6799999999999999`
- 原因：用户已进入第 2 个认知节点，需要用 deepen 补足决策或治理维度。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 2,
  "current_user_question": "Agent 和普通聊天机器人、传统自动化程序到底有什么区别？",
  "stage_profile": {
    "depth": 0.27,
    "goal": 0.55,
    "familiarity": 0.43,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ],
    "breakout_count": 7
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-legal-agent-governance-2",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 2,
  "classification": {
    "is_learning": true,
    "domain": "ai_agent_governance",
    "topic": "agent_autonomy",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.27,
    "goal": 0.55,
    "familiarity": 0.43,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": true,
    "type": "deepen",
    "score": 0.6799999999999999,
    "reason": "用户已进入第 2 个认知节点，需要用 deepen 补足决策或治理维度。",
    "directions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级"
    ],
    "evidence": [
      "Agent 和普通聊天机器人、传统自动化程序到底有什么区别？"
    ]
  },
  "latent_need": {
    "detected": true,
    "need": "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
    "missing_dimensions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级"
    ],
    "confidence": 0.82
  },
  "profile_shift": {
    "detected": false,
    "from": "",
    "to": "",
    "evidence": [],
    "confidence": 0.0
  },
  "response_strategy": {
    "answer_depth": "balanced",
    "answer_scope": "framework",
    "goal_mode": "explain",
    "terminology": "explain_key_terms",
    "breakout_integration": "integrated_section",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "agent_autonomy"
    ],
    "branch_additions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级"
    ]
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 1,
    "visited_nodes": [
      "agent_basics"
    ],
    "breakout_count": 0
  },
  "after": {
    "question_count": 2,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy"
    ],
    "breakout_count": 1
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics"
    ]
  },
  "after": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级"
    ]
  }
}
```

### 第 3 轮 — DETERMINISTIC MOCK

#### 用户

如果公司内部开始使用 Agent，可能涉及哪些法律领域和主要风险？

#### 主 Agent

主要领域包括隐私与数据保护、商业秘密、知识产权、网络安全、劳动管理、消费者与产品责任、合同和代理授权。建议按数据敏感度、工具权限、外部影响和可逆性做风险分级。

💡 破圈效果：用感知—规划—调用工具—执行—记录解释 Agent 生命周期；按自主程度和影响范围划分风险等级；连接隐私、商业秘密、知识产权、劳动和产品责任。

#### 副 Agent 行为

- 是否破圈：`True`
- 类型：`broaden`
- 分数：`0.74`
- 原因：用户已进入第 3 个认知节点，需要用 broaden 补足决策或治理维度。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 3,
  "current_user_question": "如果公司内部开始使用 Agent，可能涉及哪些法律领域和主要风险？",
  "stage_profile": {
    "depth": 0.39,
    "goal": 0.65,
    "familiarity": 0.51,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ],
    "breakout_count": 7
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-legal-agent-governance-3",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 3,
  "classification": {
    "is_learning": true,
    "domain": "ai_agent_governance",
    "topic": "legal_domains",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.39,
    "goal": 0.65,
    "familiarity": 0.51,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": true,
    "type": "broaden",
    "score": 0.74,
    "reason": "用户已进入第 3 个认知节点，需要用 broaden 补足决策或治理维度。",
    "directions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ],
    "evidence": [
      "如果公司内部开始使用 Agent，可能涉及哪些法律领域和主要风险？"
    ]
  },
  "latent_need": {
    "detected": true,
    "need": "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
    "missing_dimensions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ],
    "confidence": 0.82
  },
  "profile_shift": {
    "detected": true,
    "from": "概念了解",
    "to": "落地决策",
    "evidence": [
      "连续问题从定义转向风险、控制或实施。"
    ],
    "confidence": 0.8
  },
  "response_strategy": {
    "answer_depth": "balanced",
    "answer_scope": "framework",
    "goal_mode": "explain",
    "terminology": "explain_key_terms",
    "breakout_integration": "integrated_section",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "legal_domains"
    ],
    "branch_additions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ]
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 2,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy"
    ],
    "breakout_count": 1
  },
  "after": {
    "question_count": 3,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains"
    ],
    "breakout_count": 2
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级"
    ]
  },
  "after": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ]
  }
}
```

### 第 4 轮 — DETERMINISTIC MOCK

#### 用户

请把隐私、商业秘密、知识产权、劳动管理、产品责任和授权代理串成一个治理框架。

#### 主 Agent

治理框架可沿 Agent 生命周期展开：数据进入对应隐私和秘密；模型与内容对应知识产权；工具执行对应授权和责任；员工使用对应劳动管理；对外输出和产品行为对应合同、消费者保护与产品责任；日志贯穿举证和审计。

💡 破圈效果：用感知—规划—调用工具—执行—记录解释 Agent 生命周期；按自主程度和影响范围划分风险等级；连接隐私、商业秘密、知识产权、劳动和产品责任。

#### 副 Agent 行为

- 是否破圈：`True`
- 类型：`cross_domain`
- 分数：`0.8`
- 原因：用户已进入第 4 个认知节点，需要用 cross_domain 补足决策或治理维度。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 4,
  "current_user_question": "请把隐私、商业秘密、知识产权、劳动管理、产品责任和授权代理串成一个治理框架。",
  "stage_profile": {
    "depth": 0.51,
    "goal": 0.75,
    "familiarity": 0.59,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ],
    "breakout_count": 7
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-legal-agent-governance-4",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 4,
  "classification": {
    "is_learning": true,
    "domain": "ai_agent_governance",
    "topic": "governance_framework",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.51,
    "goal": 0.75,
    "familiarity": 0.59,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": true,
    "type": "cross_domain",
    "score": 0.8,
    "reason": "用户已进入第 4 个认知节点，需要用 cross_domain 补足决策或治理维度。",
    "directions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ],
    "evidence": [
      "请把隐私、商业秘密、知识产权、劳动管理、产品责任和授权代理串成一个治理框架。"
    ]
  },
  "latent_need": {
    "detected": true,
    "need": "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
    "missing_dimensions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ],
    "confidence": 0.82
  },
  "profile_shift": {
    "detected": true,
    "from": "概念了解",
    "to": "落地决策",
    "evidence": [
      "连续问题从定义转向风险、控制或实施。"
    ],
    "confidence": 0.8
  },
  "response_strategy": {
    "answer_depth": "balanced",
    "answer_scope": "framework",
    "goal_mode": "explain",
    "terminology": "explain_key_terms",
    "breakout_integration": "integrated_section",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "governance_framework"
    ],
    "branch_additions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ]
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 3,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains"
    ],
    "breakout_count": 2
  },
  "after": {
    "question_count": 4,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework"
    ],
    "breakout_count": 3
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ]
  },
  "after": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework"
    ]
  }
}
```

### 第 5 轮 — DETERMINISTIC MOCK

#### 用户

公司应该设置哪些审批、权限、日志和事故响应机制？

#### 主 Agent

控制机制应包括：风险分级、最小权限、敏感数据限制、关键动作人类批准、不可篡改日志、供应商审查、定期复核、异常暂停和事故响应。高风险 Agent必须指定业务负责人、技术负责人和法律审查人。

💡 破圈效果：用感知—规划—调用工具—执行—记录解释 Agent 生命周期；按自主程度和影响范围划分风险等级；连接隐私、商业秘密、知识产权、劳动和产品责任。

#### 副 Agent 行为

- 是否破圈：`True`
- 类型：`operationalize`
- 分数：`0.86`
- 原因：用户已进入第 5 个认知节点，需要用 operationalize 补足决策或治理维度。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 5,
  "current_user_question": "公司应该设置哪些审批、权限、日志和事故响应机制？",
  "stage_profile": {
    "depth": 0.63,
    "goal": 0.8500000000000001,
    "familiarity": 0.6699999999999999,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ],
    "breakout_count": 7
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-legal-agent-governance-5",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 5,
  "classification": {
    "is_learning": true,
    "domain": "ai_agent_governance",
    "topic": "controls",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.63,
    "goal": 0.8500000000000001,
    "familiarity": 0.6699999999999999,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": true,
    "type": "operationalize",
    "score": 0.86,
    "reason": "用户已进入第 5 个认知节点，需要用 operationalize 补足决策或治理维度。",
    "directions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ],
    "evidence": [
      "公司应该设置哪些审批、权限、日志和事故响应机制？"
    ]
  },
  "latent_need": {
    "detected": true,
    "need": "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
    "missing_dimensions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ],
    "confidence": 0.82
  },
  "profile_shift": {
    "detected": true,
    "from": "概念了解",
    "to": "落地决策",
    "evidence": [
      "连续问题从定义转向风险、控制或实施。"
    ],
    "confidence": 0.8
  },
  "response_strategy": {
    "answer_depth": "balanced",
    "answer_scope": "framework",
    "goal_mode": "explain",
    "terminology": "explain_key_terms",
    "breakout_integration": "integrated_section",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "controls"
    ],
    "branch_additions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ]
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 4,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework"
    ],
    "breakout_count": 3
  },
  "after": {
    "question_count": 5,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls"
    ],
    "breakout_count": 4
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework"
    ]
  },
  "after": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls"
    ]
  }
}
```

### 第 6 轮 — DETERMINISTIC MOCK

#### 用户

请起草一份简洁但能落地的《公司 AI Agent 使用管理规范》。

#### 主 Agent

《公司 AI Agent 使用管理规范（简版）》：一、适用于所有代表公司读取数据、调用工具或影响外部主体的 Agent；二、按低中高风险登记审批；三、仅授予完成任务所需权限；四、敏感数据和对外承诺须经授权；五、付款、签约、删除、生产变更等动作须人工批准；六、保存输入来源、计划、工具调用、批准和结果日志；七、第三方服务须审查数据、知识产权、跨境和审计条款；八、发现异常立即暂停、保全证据并上报；九、业务负责人承担使用责任，法务、安保和技术共同复核。

💡 破圈效果：用感知—规划—调用工具—执行—记录解释 Agent 生命周期；按自主程度和影响范围划分风险等级；连接隐私、商业秘密、知识产权、劳动和产品责任。

#### 副 Agent 行为

- 是否破圈：`True`
- 类型：`operationalize`
- 分数：`0.9199999999999999`
- 原因：用户已进入第 6 个认知节点，需要用 operationalize 补足决策或治理维度。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 6,
  "current_user_question": "请起草一份简洁但能落地的《公司 AI Agent 使用管理规范》。",
  "stage_profile": {
    "depth": 0.75,
    "goal": 0.95,
    "familiarity": 0.75,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ],
    "breakout_count": 7
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-legal-agent-governance-6",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 6,
  "classification": {
    "is_learning": true,
    "domain": "ai_agent_governance",
    "topic": "policy",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.75,
    "goal": 0.95,
    "familiarity": 0.75,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": true,
    "type": "operationalize",
    "score": 0.9199999999999999,
    "reason": "用户已进入第 6 个认知节点，需要用 operationalize 补足决策或治理维度。",
    "directions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ],
    "evidence": [
      "请起草一份简洁但能落地的《公司 AI Agent 使用管理规范》。"
    ]
  },
  "latent_need": {
    "detected": true,
    "need": "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
    "missing_dimensions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ],
    "confidence": 0.82
  },
  "profile_shift": {
    "detected": true,
    "from": "概念了解",
    "to": "落地决策",
    "evidence": [
      "连续问题从定义转向风险、控制或实施。"
    ],
    "confidence": 0.8
  },
  "response_strategy": {
    "answer_depth": "balanced",
    "answer_scope": "framework",
    "goal_mode": "explain",
    "terminology": "explain_key_terms",
    "breakout_integration": "integrated_section",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "policy"
    ],
    "branch_additions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ]
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 5,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls"
    ],
    "breakout_count": 4
  },
  "after": {
    "question_count": 6,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls",
      "policy"
    ],
    "breakout_count": 5
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls"
    ]
  },
  "after": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls",
      "policy"
    ]
  }
}
```

### 第 7 轮 — DETERMINISTIC MOCK

#### 用户

压力测试一下：如果采购 Agent 能自行读取报价、联系供应商并准备订单，这份规范还缺什么？

#### 主 Agent

采购 Agent 暴露了规范缺口：‘准备订单’和‘代表公司作出承诺’必须分开。还需加入供应商身份验证、利益冲突检查、报价保密、反商业贿赂、授权金额阈值、双人批准、禁止自行签约或付款、通信留痕、订单撤销机制以及供应商知情规则。

💡 破圈效果：用感知—规划—调用工具—执行—记录解释 Agent 生命周期；按自主程度和影响范围划分风险等级；连接隐私、商业秘密、知识产权、劳动和产品责任。

#### 副 Agent 行为

- 是否破圈：`True`
- 类型：`reframe`
- 分数：`0.95`
- 原因：用户已进入第 7 个认知节点，需要用 reframe 补足决策或治理维度。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 7,
  "current_user_question": "压力测试一下：如果采购 Agent 能自行读取报价、联系供应商并准备订单，这份规范还缺什么？",
  "stage_profile": {
    "depth": 0.87,
    "goal": 1.0,
    "familiarity": 0.83,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ],
    "breakout_count": 7
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-legal-agent-governance-7",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 7,
  "classification": {
    "is_learning": true,
    "domain": "ai_agent_governance",
    "topic": "procurement_agent",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.87,
    "goal": 1.0,
    "familiarity": 0.83,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": true,
    "type": "reframe",
    "score": 0.95,
    "reason": "用户已进入第 7 个认知节点，需要用 reframe 补足决策或治理维度。",
    "directions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ],
    "evidence": [
      "压力测试一下：如果采购 Agent 能自行读取报价、联系供应商并准备订单，这份规范还缺什么？"
    ]
  },
  "latent_need": {
    "detected": true,
    "need": "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
    "missing_dimensions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ],
    "confidence": 0.82
  },
  "profile_shift": {
    "detected": true,
    "from": "概念了解",
    "to": "落地决策",
    "evidence": [
      "连续问题从定义转向风险、控制或实施。"
    ],
    "confidence": 0.8
  },
  "response_strategy": {
    "answer_depth": "balanced",
    "answer_scope": "framework",
    "goal_mode": "explain",
    "terminology": "explain_key_terms",
    "breakout_integration": "integrated_section",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "procurement_agent"
    ],
    "branch_additions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ]
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 6,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls",
      "policy"
    ],
    "breakout_count": 5
  },
  "after": {
    "question_count": 7,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent"
    ],
    "breakout_count": 6
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls",
      "policy"
    ]
  },
  "after": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent"
    ]
  }
}
```

### 第 8 轮 — DETERMINISTIC MOCK

#### 用户

先简化成给全体员工看的五条规则，然后说明何时必须升级到法务审查。

#### 主 Agent

员工五条规则：只用已批准 Agent；不输入无权处理的数据；不授予超出任务的工具权限；付款、签约、删除和对外承诺必须人工批准；异常立即停止并报告。涉及敏感数据、高影响个人决策、外部承诺、跨境传输或高权限工具时必须升级到法务审查。

💡 破圈效果：用感知—规划—调用工具—执行—记录解释 Agent 生命周期；按自主程度和影响范围划分风险等级；连接隐私、商业秘密、知识产权、劳动和产品责任。

#### 副 Agent 行为

- 是否破圈：`True`
- 类型：`operationalize`
- 分数：`0.95`
- 原因：用户已进入第 8 个认知节点，需要用 operationalize 补足决策或治理维度。
- Advice 已注入主提示：`True`

#### 副 Agent 隔离输入

```json
{
  "event": "user_question",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 8,
  "current_user_question": "先简化成给全体员工看的五条规则，然后说明何时必须升级到法务审查。",
  "stage_profile": {
    "depth": 0.99,
    "goal": 1.0,
    "familiarity": 0.91,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "map_summary": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ]
  },
  "heatmap_summary": {
    "question_count": 8,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ],
    "breakout_count": 7
  }
}
```

#### 副 Agent 原始输出

```json
{
  "schema_version": "1.0",
  "advice_id": "mock-legal-agent-governance-8",
  "user_id_hash": "82fa5160acf457d366c4e5148716a3e168dd6f994ddb0b1c0518081ebaf0d9a3",
  "profile_id": "legal-learning",
  "turn_index": 8,
  "classification": {
    "is_learning": true,
    "domain": "ai_agent_governance",
    "topic": "employee_rules",
    "confidence": 0.95
  },
  "user_state": {
    "depth": 0.99,
    "goal": 1.0,
    "familiarity": 0.91,
    "evidence": [
      "用户问题显示认知或决策阶段发生推进。"
    ]
  },
  "breakout": {
    "needed": true,
    "type": "operationalize",
    "score": 0.95,
    "reason": "用户已进入第 8 个认知节点，需要用 operationalize 补足决策或治理维度。",
    "directions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ],
    "evidence": [
      "先简化成给全体员工看的五条规则，然后说明何时必须升级到法务审查。"
    ]
  },
  "latent_need": {
    "detected": true,
    "need": "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
    "missing_dimensions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ],
    "confidence": 0.82
  },
  "profile_shift": {
    "detected": true,
    "from": "概念了解",
    "to": "落地决策",
    "evidence": [
      "连续问题从定义转向风险、控制或实施。"
    ],
    "confidence": 0.8
  },
  "response_strategy": {
    "answer_depth": "balanced",
    "answer_scope": "framework",
    "goal_mode": "explain",
    "terminology": "explain_key_terms",
    "breakout_integration": "integrated_section",
    "instructions": []
  },
  "map_updates": {
    "proposed_map": null,
    "visited_nodes": [
      "employee_rules"
    ],
    "branch_additions": [
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "连接隐私、商业秘密、知识产权、劳动和产品责任"
    ]
  },
  "diagnostics": {
    "source": "live",
    "evidence": [
      "确定性演示夹具；并非真实 LLM 判断。"
    ]
  }
}
```

#### 热力图变化

```json
{
  "before": {
    "question_count": 7,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent"
    ],
    "breakout_count": 6
  },
  "after": {
    "question_count": 8,
    "visited_nodes": [
      "agent_basics",
      "agent_autonomy",
      "legal_domains",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ],
    "breakout_count": 7
  }
}
```

#### 知识地图变化

```json
{
  "before": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent"
    ]
  },
  "after": {
    "domain": "ai_agent_governance",
    "nodes": [
      "agent_basics",
      "agent_autonomy",
      "用感知—规划—调用工具—执行—记录解释 Agent 生命周期",
      "按自主程度和影响范围划分风险等级",
      "legal_domains",
      "连接隐私、商业秘密、知识产权、劳动和产品责任",
      "governance_framework",
      "controls",
      "policy",
      "procurement_agent",
      "employee_rules"
    ]
  }
}
```

## 破圈效果总结

- CEO 场景从工具是否采用，推进到交付风险、组织成熟度、分阶段投资和可量化试点。
- 法律顾问场景从 Agent 定义，推进到自主程度、法律责任、生命周期控制和采购 Agent 的制度压力测试。
- 两个用户使用不同 SHA-256 目录，热力图互不混用；知识地图按各自领域持续增加节点。
- 副 Agent输入不包含主 Agent回答、reasoning、tool_calls、工具结果或 messages 数组。

## 当前限制

- 确定性输出证明数据流和预期体验，不证明真实 LLM 在每次运行中都会给出同样建议。
- 当前环境真实 DeepSeek连接失败，因此完整真实多轮对话需要在网络恢复后重新执行。
- 法规草案是治理演示，不构成特定法域的正式法律意见。
