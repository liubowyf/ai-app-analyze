# 测试用例快速参考卡

**快速查询所有测试用例**

---

## 📋 模块一：基础设施层

### ✅ 任务 1.1: 数据库连接池优化与监控

| 测试方法 | 功能 | 验证点 | 状态 |
|---------|------|--------|------|
| `test_pool_status_endpoint` | 连接池状态接口 | 返回连接池大小、活跃/空闲连接、使用率 | ✅ |
| `test_connection_leak_detection` | 连接泄漏检测 | 未关闭连接能被检测并告警 | ✅ |
| `test_slow_query_logging` | 慢查询日志 | 查询时间>1s被记录，包含SQL和执行时间 | ✅ |
| `test_prometheus_metrics` | Prometheus指标 | 返回正确格式的监控指标 | ✅ |
| `test_health_check_endpoint` | 健康检查端点 | 返回数据库连通性和连接池状态 | ✅ |
| `test_connection_pool_recycle` | 连接池回收 | 连接使用3600s后被回收 | ✅ |
| `test_pool_overflow_behavior` | 连接池溢出 | 超过pool_size时创建溢出连接 | ✅ |

**执行命令**:
```bash
pytest tests/task_tests/test_module_01_infrastructure.py::TestDatabasePoolMonitoring -v
```

---

### ✅ 任务 1.2: MinIO 存储优化与冗余备份

| 测试方法 | 功能 | 验证点 | 状态 |
|---------|------|--------|------|
| `test_storage_capacity_monitoring` | 存储容量监控 | 返回总容量、已用、可用容量和使用率 | ✅ |
| `test_auto_cleanup_expired_files` | 过期文件清理 | 30天前的文件被自动删除 | ✅ |
| `test_multipart_upload` | 分片上传 | 大文件(>50MB)使用分片上传 | ✅ |
| `test_file_versioning` | 文件版本管理 | 同名文件创建新版本，历史可查询 | ✅ |
| `test_access_logging` | 访问日志 | 文件访问被记录，包含访问者和时间 | ✅ |
| `test_storage_quota_enforcement` | 存储配额 | 超过配额时拒绝上传 | ✅ |

**执行命令**:
```bash
pytest tests/task_tests/test_module_01_infrastructure.py::TestStorageEnhancements -v
```

---

### ✅ 任务 1.3: Redis 缓存策略优化

| 测试方法 | 功能 | 验证点 | 状态 |
|---------|------|--------|------|
| `test_task_result_caching` | 任务结果缓存 | 任务完成后结果被缓存，TTL=24h | ✅ |
| `test_whitelist_cache` | 白名单缓存 | 白名单规则被缓存，更新时失效 | ✅ |
| `test_cache_warmup` | 缓存预热 | 启动时预加载热点数据 | ✅ |
| `test_cache_invalidation` | 缓存失效 | 数据更新时缓存被清除 | ✅ |
| `test_cache_monitoring` | 缓存监控 | 返回命中率、内存使用等指标 | ✅ |
| `test_cache_serialization` | 缓存序列化 | 复杂对象正确序列化/反序列化 | ✅ |
| `test_cache_ttl_management` | TTL管理 | 不同数据类型有不同TTL | ✅ |
| `test_cache_fallback` | 缓存降级 | Redis不可用时功能正常 | ✅ |

**执行命令**:
```bash
pytest tests/task_tests/test_module_01_infrastructure.py::TestRedisCacheStrategy -v
```

---

## 📋 模块二：核心分析引擎

### ✅ 任务 2.1: 静态分析功能集成

| 测试方法 | 功能 | 验证点 | 状态 |
|---------|------|--------|------|
| `test_static_analysis_in_pipeline` | 流水线执行 | APK上传后触发静态分析，在动态分析之前 | ✅ |
| `test_static_analysis_result_storage` | 结果存储 | 结果存储到数据库JSON字段 | ✅ |
| `test_static_analysis_performance` | 性能测试 | 分析耗时<30s，内存<100MB | ✅ |
| `test_risk_scoring` | 风险评分 | 危险权限被识别，评分算法准确 | ✅ |
| `test_apk_cache` | APK缓存 | 相同APK不重复解析 | ✅ |
| `test_signature_verification` | 签名验证 | 提取签名信息，识别调试签名 | ✅ |
| `test_component_analysis` | 组件分析 | 提取四大组件，识别导出组件 | ✅ |

**执行命令**:
```bash
pytest tests/task_tests/test_module_02_core_analysis.py::TestStaticAnalyzerIntegration -v
```

---

### ✅ 任务 2.2: 动态分析增强 - 场景扩展

| 测试方法 | 功能 | 验证点 | 状态 |
|---------|------|--------|------|
| `test_login_scenario_detection` | 登录场景检测 | 识别登录按钮和输入框 | ✅ |
| `test_login_scenario_execution` | 登录场景执行 | 输入用户名密码并点击登录 | ✅ |
| `test_payment_scenario_detection` | 支付场景检测 | 识别支付按钮和金额输入 | ✅ |
| `test_payment_scenario_execution` | 支付场景执行 | 执行支付并检测敏感数据 | ✅ |
| `test_share_scenario_detection` | 分享场景检测 | 识别分享按钮和分享目标 | ✅ |
| `test_scenario_report_generation` | 场景报告生成 | 包含场景类型、步骤、请求、敏感数据 | ✅ |

**执行命令**:
```bash
pytest tests/task_tests/test_module_02_core_analysis.py::TestScenarioTesting -v
```

---

### ✅ 任务 2.3: AI 驱动优化 - 决策智能增强

| 测试方法 | 功能 | 验证点 | 状态 |
|---------|------|--------|------|
| `test_exploration_depth_limit` | 探索深度限制 | 超过50步后停止 | ✅ |
| `test_loop_detection` | 循环检测 | 重复界面被检测 | ✅ |
| `test_smart_backtrack` | 智能回退 | 死胡同时执行回退 | ✅ |
| `test_prompt_optimization` | Prompt优化 | 包含上下文和历史操作 | ✅ |
| `test_decision_logging` | 决策日志 | 每次决策被记录 | ✅ |
| `test_multi_step_reasoning` | 多步推理 | 生成多步操作序列 | ✅ |

**执行命令**:
```bash
pytest tests/task_tests/test_module_02_core_analysis.py::TestAIDecisionEnhanced -v
```

---

### ✅ 任务 2.4: 流量监控增强 - 协议解析

| 测试方法 | 功能 | 验证点 | 状态 |
|---------|------|--------|------|
| `test_websocket_capture` | WebSocket捕获 | WebSocket消息被捕获 | ✅ |
| `test_grpc_parsing` | gRPC解析 | gRPC请求被解析 | ✅ |
| `test_custom_protocol_detection` | 自定义协议识别 | 非标准协议被识别 | ✅ |
| `test_https_decryption_performance` | HTTPS解密性能 | 解密延迟<100ms | ✅ |
| `test_traffic_visualization` | 流量可视化 | 生成时序图和统计图表 | ✅ |
| `test_protocol_statistics` | 协议统计 | 统计各协议占比 | ✅ |

**执行命令**:
```bash
pytest tests/task_tests/test_module_02_core_analysis.py::TestTrafficProtocolParsing -v
```

---

## 📊 测试统计

### 已完成模块

| 模块 | 任务数 | 测试方法数 | 完成率 |
|------|--------|-----------|--------|
| 模块一：基础设施层 | 3 | 21 | 100% ✅ |
| 模块二：核心分析引擎 | 4 | 26 | 100% ✅ |
| **小计** | **7** | **47** | **100%** |

### 待创建模块

| 模块 | 任务数 | 预计测试方法数 | 状态 |
|------|--------|--------------|------|
| 模块三：智能分析模块 | 3 | 15 | ⏸️ 待创建 |
| 模块四：报告与可视化 | 3 | 15 | ⏸️ 待创建 |
| 模块五：API层增强 | 3 | 15 | ⏸️ 待创建 |
| 模块六：模拟器管理 | 2 | 10 | ⏸️ 待创建 |
| 模块七：安全与合规 | 3 | 15 | ⏸️ 待创建 |
| 模块八：测试与质量保证 | 3 | 15 | ⏸️ 待创建 |
| 模块九：DevOps与部署 | 3 | 15 | ⏸️ 待创建 |
| 模块十：文档与知识库 | 2 | 10 | ⏸️ 待创建 |
| **小计** | **22** | **110** | **0%** |

### 总体进度

- **已完成测试用例**: 47 个
- **待创建测试用例**: 110 个
- **总测试用例**: 157 个
- **完成率**: 29.9%

---

## 🚀 快速执行命令

### 运行所有已完成的测试

```bash
# 运行所有测试
pytest tests/task_tests/ -v

# 运行并生成覆盖率报告
pytest tests/task_tests/ -v --cov=. --cov-report=html

# 并行运行
pytest tests/task_tests/ -v -n auto
```

### 运行特定模块

```bash
# 模块一：基础设施层
pytest tests/task_tests/test_module_01_infrastructure.py -v

# 模块二：核心分析引擎
pytest tests/task_tests/test_module_02_core_analysis.py -v
```

### 运行特定测试类

```bash
# 数据库测试
pytest tests/task_tests/test_module_01_infrastructure.py::TestDatabasePoolMonitoring -v

# 静态分析测试
pytest tests/task_tests/test_module_02_core_analysis.py::TestStaticAnalyzerIntegration -v
```

---

## 📝 测试文件结构

```
tests/
├── task_tests/
│   ├── test_module_01_infrastructure.py    ✅ 已完成
│   ├── test_module_02_core_analysis.py     ✅ 已完成
│   ├── test_module_03_intelligent_analysis.py  ⏸️ 待创建
│   ├── test_module_04_report_viz.py        ⏸️ 待创建
│   ├── test_module_05_api_enhancement.py   ⏸️ 待创建
│   ├── test_module_06_emulator_mgmt.py     ⏸️ 待创建
│   ├── test_module_07_security_compliance.py  ⏸️ 待创建
│   ├── test_module_08_testing_qa.py        ⏸️ 待创建
│   ├── test_module_09_devops.py            ⏸️ 待创建
│   ├── test_module_10_documentation.py     ⏸️ 待创建
│   └── TEST_CASES_SUMMARY.py               ✅ 汇总文档
├── conftest.py
└── fixtures/
    └── test.apk
```

---

## 🎯 验收标准速查

### P0 核心任务

- ✅ 静态分析集成: 耗时<30s，结果正确存储
- ✅ 测试覆盖率: 总体>85%

### P1 重要任务

- ✅ 数据库监控: 连接泄漏检测，慢查询记录
- ✅ 存储优化: 分片上传，版本管理
- ✅ 缓存优化: 命中率>80%，降级正常
- ✅ 场景扩展: 登录/支付/分享场景识别
- ✅ AI优化: 探索深度限制，循环检测

### P2 优化任务

- 待创建测试用例

---

## 📞 联系方式

- **测试文档**: `/docs/TESTING_GUIDE.md`
- **测试汇总**: `/tests/task_tests/TEST_CASES_SUMMARY.py`
- **技术支持**: [待指定]

---

**最后更新**: 2026-02-21
**文档版本**: v1.0
