# 项目文档导航

## 📚 核心文档

### 产品设计
- **PRD.md** - 产品需求文档 v2.0
  - 产品概述和目标
  - 功能模块需求
  - 技术指标
  - 实施状态

### 技术架构
- **ARCHITECTURE.md** - 系统架构文档 v2.0
  - 系统架构设计
  - 核心模块实现
  - 技术栈说明
  - API设计

### 运维指南
- **OPERATIONS.md** - 运维操作指南
  - 环境准备
  - 数据库初始化
  - 服务启动
  - Android 模拟器配置
  - 网络诊断
  - 常见问题

---

## 📖 项目说明

- **根目录 README.md** - 项目概述、快速开始、使用指南

---

## 📂 项目结构

```
智能APP分析系统/
├── README.md              # 项目入口文档
├── CLAUDE.md              # 文档规范
│
├── docs/
│   ├── README.md          # 本文件 - 文档导航
│   ├── PRD.md             # 产品需求文档
│   ├── ARCHITECTURE.md    # 系统架构文档
│   └── OPERATIONS.md      # 运维指南
│
├── api/                   # API接口
├── core/                  # 核心配置
├── models/                # 数据模型
├── modules/               # 功能模块
├── workers/               # Celery任务
└── tests/                 # 单元测试
```

---

## 🚀 快速开始

1. **了解项目** - 阅读 `README.md`
2. **查看需求** - 参考 `docs/PRD.md`
3. **了解架构** - 查看 `docs/ARCHITECTURE.md`
4. **开始开发** - 按照文档指引进行

---

## 📝 文档使用指南

### 新手入门
1. 阅读根目录 `README.md` 了解项目概况
2. 查看 `docs/PRD.md` 了解产品需求
3. 参考 `docs/ARCHITECTURE.md` 了解技术架构

### 开发参考
- 功能需求 → `docs/PRD.md`
- 架构设计 → `docs/ARCHITECTURE.md`
- 实现细节 → `docs/ARCHITECTURE.md` 中的模块说明
- 运维操作 → `docs/OPERATIONS.md`

---

## 📋 文档维护

### 文档更新

- **PRD.md** - 新增功能需求时更新
- **ARCHITECTURE.md** - 架构变更时更新
- **README.md** - 使用方式变更时更新
- **OPERATIONS.md** - 运维操作变更时更新

### 版本历史

- **v2.0** (2026-02-20) - 融合所有设计文档和实施计划
- **v1.0** (2026-02-18) - 初始版本

---

**最后更新**: 2026-02-20
**文档数量**: 3个核心文档
**维护建议**: 保持文档与代码实现同步
