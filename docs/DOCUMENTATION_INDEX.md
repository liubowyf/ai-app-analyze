# 项目文档导航索引

**项目名称**: APK 智能动态分析平台
**更新日期**: 2026-02-21

---

## 📚 文档结构总览

```
项目根目录/
├── CLAUDE.md                              # Claude Code 开发指南
├── README.md                              # 项目入口文档
│
├── docs/                                  # 📁 文档目录
│   ├── PROJECT_TASK_BREAKDOWN.md         # 📋 项目任务拆解与实施规划
│   ├── PROJECT_TASK_TRACKER.md           # 📊 项目任务追踪看板
│   ├── TEST_CASES_COMPLETION_SUMMARY.md  # ✅ 测试用例完成总结
│   ├── TESTING_GUIDE.md                  # 🧪 测试执行指南
│   ├── TEST_QUICK_REFERENCE.md           # 📖 测试快速参考卡
│   ├── ARCHITECTURE.md                   # 🏗️ 系统架构文档
│   ├── OPERATIONS.md                     # 🚀 运维操作手册
│   ├── TESTING.md                        # 🧪 原有测试框架说明
│   └── PRD.md                            # 📝 产品需求文档
│
└── tests/                                # 📁 测试目录
    └── task_tests/                       # 📁 任务测试用例
        ├── test_module_01_infrastructure.py    # 基础设施层测试
        ├── test_module_02_core_analysis.py     # 核心分析引擎测试
        └── TEST_CASES_SUMMARY.py               # 测试用例汇总统计
```

---

## 🎯 快速导航

### 项目规划类文档

#### 1. 📋 项目任务拆解与实施规划
**文件**: `docs/PROJECT_TASK_BREAKDOWN.md`

**内容概要**:
- 10个功能模块详细拆解
- 29个独立任务实施步骤
- 每个任务的技术要求和测试用例
- 优先级矩阵和实施路线图
- 资源需求和风险评估

**适用场景**:
- ✅ 了解项目全貌和任务分解
- ✅ 制定开发计划
- ✅ 分配任务和资源
- ✅ 评估项目风险

**核心内容**:
- 第一阶段（1-2周）：核心功能完善
- 第二阶段（3-10周）：重要功能开发
- 第三阶段（11-16周）：优化增强
- 第四阶段（17-18周）：文档与交付

---

#### 2. 📊 项目任务追踪看板
**文件**: `docs/PROJECT_TASK_TRACKER.md`

**内容概要**:
- 任务实时状态追踪
- 里程碑管理
- 风险和问题追踪
- 团队成员分配
- 变更日志

**适用场景**:
- ✅ 查看任务进度
- ✅ 更新任务状态
- ✅ 记录问题和风险
- ✅ 周会进度汇报

**状态标识**:
- ⏸️ 待开始
- 🚀 进行中
- ✅ 已完成
- ⚠️ 有风险
- ❌ 已取消

---

### 测试类文档

#### 3. ✅ 测试用例完成总结
**文件**: `docs/TEST_CASES_COMPLETION_SUMMARY.md`

**内容概要**:
- 已完成的47个测试用例详情
- 测试覆盖情况统计
- 验收标准清单
- 后续工作建议

**适用场景**:
- ✅ 查看测试完成情况
- ✅ 了解测试质量
- ✅ 规划后续测试工作

**完成统计**:
- 模块一：基础设施层 - 21个测试用例 ✅
- 模块二：核心分析引擎 - 26个测试用例 ✅
- 总体完成率：30% (47/157)

---

#### 4. 🧪 测试执行指南
**文件**: `docs/TESTING_GUIDE.md`

**内容概要**:
- 环境准备步骤
- 测试执行方法
- 详细测试用例执行命令
- 验收标准说明
- 常见问题解决

**适用场景**:
- ✅ 第一次运行测试
- ✅ 查看测试执行方法
- ✅ 解决测试问题
- ✅ 生成测试报告

**关键命令**:
```bash
# 运行所有测试
pytest tests/task_tests/ -v

# 生成覆盖率报告
pytest tests/task_tests/ --cov=. --cov-report=html
```

---

#### 5. 📖 测试快速参考卡
**文件**: `docs/TEST_QUICK_REFERENCE.md`

**内容概要**:
- 所有测试用例清单表格
- 快速执行命令
- 验收标准速查
- 测试统计信息

**适用场景**:
- ✅ 快速查找测试用例
- ✅ 查看测试验收标准
- ✅ 获取执行命令

**特点**: 适合打印或快速查阅

---

### 架构与设计类文档

#### 6. 🏗️ 系统架构文档
**文件**: `docs/ARCHITECTURE.md`

**内容概要**:
- 系统整体架构设计
- 模块划分和职责
- 技术选型说明
- 数据流设计
- 接口设计规范

**适用场景**:
- ✅ 理解系统设计
- ✅ 技术方案评审
- ✅ 新人培训

---

#### 7. 🚀 运维操作手册
**文件**: `docs/OPERATIONS.md`

**内容概要**:
- 部署指南
- 配置管理
- 监控告警
- 故障排查
- 日常运维操作

**适用场景**:
- ✅ 系统部署
- ✅ 运维操作
- ✅ 故障处理

---

#### 8. 📝 产品需求文档
**文件**: `docs/PRD.md`

**内容概要**:
- 产品定位和目标
- 功能需求详细说明
- 用户场景描述
- 非功能需求
- 产品路线图

**适用场景**:
- ✅ 了解产品需求
- ✅ 功能设计参考
- ✅ 验收标准制定

---

### 开发指南类文档

#### 9. 🧪 原有测试框架说明
**文件**: `docs/TESTING.md`

**内容概要**:
- 原有测试框架介绍
- 测试结构和规范
- 测试最佳实践
- CI/CD集成

**适用场景**:
- ✅ 了解原有测试体系
- ✅ 学习测试规范

---

#### 10. 📖 Claude Code 开发指南
**文件**: `CLAUDE.md`

**内容概要**:
- 项目概览
- 开发命令速查
- 架构说明
- 配置要点
- 开发工作流

**适用场景**:
- ✅ Claude Code 开发指导
- ✅ 快速上手项目

---

## 📊 文档使用场景指南

### 场景一：新成员入职

**推荐阅读顺序**:
1. `README.md` - 项目简介
2. `CLAUDE.md` - 开发指南
3. `docs/ARCHITECTURE.md` - 系统架构
4. `docs/PROJECT_TASK_BREAKDOWN.md` - 任务规划
5. `docs/TESTING_GUIDE.md` - 测试指南

---

### 场景二：开始新任务开发

**推荐步骤**:
1. 查看 `docs/PROJECT_TASK_BREAKDOWN.md` 找到任务详情
2. 查看 `docs/PROJECT_TASK_TRACKER.md` 更新任务状态
3. 阅读 `docs/ARCHITECTURE.md` 了解架构设计
4. 参考已有测试用例编写测试
5. 运行测试确保质量

---

### 场景三：测试执行

**推荐步骤**:
1. 阅读 `docs/TESTING_GUIDE.md` 了解环境准备
2. 查阅 `docs/TEST_QUICK_REFERENCE.md` 找到测试命令
3. 执行测试并查看报告
4. 参考 `docs/TEST_CASES_COMPLETION_SUMMARY.md` 查看测试详情

---

### 场景四：项目进度汇报

**推荐使用**:
1. `docs/PROJECT_TASK_TRACKER.md` - 查看任务进度
2. `docs/TEST_CASES_COMPLETION_SUMMARY.md` - 测试完成情况
3. `docs/PROJECT_TASK_BREAKDOWN.md` - 对比计划进度

---

### 场景五：故障排查

**推荐使用**:
1. `docs/OPERATIONS.md` - 运维手册
2. `docs/ARCHITECTURE.md` - 架构理解
3. `docs/TESTING_GUIDE.md` - 常见问题解决

---

## 🔍 按角色分类

### 项目经理
- 📋 `PROJECT_TASK_BREAKDOWN.md` - 任务规划
- 📊 `PROJECT_TASK_TRACKER.md` - 进度追踪
- ✅ `TEST_CASES_COMPLETION_SUMMARY.md` - 完成情况

### 开发工程师
- 📖 `CLAUDE.md` - 开发指南
- 🏗️ `ARCHITECTURE.md` - 架构设计
- 🧪 `TESTING_GUIDE.md` - 测试指南
- 📖 `TEST_QUICK_REFERENCE.md` - 测试参考

### 测试工程师
- 🧪 `TESTING_GUIDE.md` - 测试执行
- 📖 `TEST_QUICK_REFERENCE.md` - 测试速查
- ✅ `TEST_CASES_COMPLETION_SUMMARY.md` - 测试总结

### 运维工程师
- 🚀 `OPERATIONS.md` - 运维手册
- 🏗️ `ARCHITECTURE.md` - 架构理解
- 🧪 `TESTING_GUIDE.md` - 故障排查

### 产品经理
- 📝 `PRD.md` - 产品需求
- 📋 `PROJECT_TASK_BREAKDOWN.md` - 功能规划
- 📊 `PROJECT_TASK_TRACKER.md` - 项目进度

---

## 📈 文档更新记录

| 日期 | 文档 | 更新内容 | 更新人 |
|------|------|---------|--------|
| 2026-02-21 | 全部文档 | 初始创建项目文档体系 | Claude Code |
| 2026-02-21 | 测试文档 | 完成47个测试用例编写 | Claude Code |

---

## 📞 文档反馈

如发现文档问题或有改进建议，请：
1. 在项目仓库提交 Issue
2. 联系项目负责人
3. 提交文档改进 PR

---

## 🎯 快速链接

### 最常用文档

1. **开始开发**: `CLAUDE.md` + `docs/ARCHITECTURE.md`
2. **查看任务**: `docs/PROJECT_TASK_BREAKDOWN.md`
3. **执行测试**: `docs/TESTING_GUIDE.md`
4. **更新进度**: `docs/PROJECT_TASK_TRACKER.md`

### 关键统计数据

- **总任务数**: 29个
- **已编写测试**: 47个
- **文档总数**: 10个
- **项目周期**: 18周

---

**文档维护者**: 技术架构团队
**最后更新**: 2026-02-21
**文档版本**: v1.0
