# Module 2 Execution Guide

## 快速启动指南

### 1. 当前环境状态

**工作目录**: `/Users/liubo/Desktop/重要项目/工程项目/智能APP分析系统`

**已完成准备**:
- ✅ 设计文档已创建
- ✅ 实施计划已创建
- ✅ Git提交完成

**实施计划位置**: `docs/plans/2026-02-21-module2-implementation-plan.md`

### 2. 启动新会话执行

**步骤1**: 打开新的终端窗口

**步骤2**: 进入项目目录
```bash
cd /Users/liubo/Desktop/重要项目/工程项目/智能APP分析系统
```

**步骤3**: 激活虚拟环境
```bash
source venv/bin/activate
```

**步骤4**: 启动Claude Code并使用executing-plans技能
```
/executing-plans docs/plans/2026-02-21-module2-implementation-plan.md
```

### 3. 执行过程中注意事项

#### 测试策略
- 每个任务遵循TDD：先写测试，再实现
- 确保每个步骤的测试通过后再继续
- 运行测试命令：`pytest tests/test_<module>.py -v`

#### 提交策略
- 每个子任务完成后立即提交
- 使用语义化提交信息
- 提交前确保测试通过

#### 验收标准
- [ ] 所有测试通过
- [ ] 测试覆盖率 > 85%
- [ ] 代码符合PEP 8
- [ ] 函数有完整文档字符串
- [ ] 类型注解完整

### 4. 任务优先级

**P0任务（立即执行）**:
- Task 1: 静态分析集成

**P1任务（重要）**:
- Task 2: 动态分析场景测试
- Task 3: AI决策优化

**P2任务（优化）**:
- Task 4: 流量监控增强

### 5. 验收检查点

**Task 1完成后（P0验收）**:
```bash
# 运行测试
pytest tests/test_risk_scorer.py tests/test_apk_analyzer_integration.py -v --cov

# 检查覆盖率
pytest --cov=modules/apk_analyzer --cov-report=term-missing

# 验证静态分析集成
pytest tests/test_static_analyzer_integration.py -v
```

**Task 2-4完成后（P1/P2批量验收）**:
```bash
# 运行完整测试套件
pytest tests/ -v --cov=modules --cov=workers --cov-report=html

# 检查代码质量
pylint modules/
mypy modules/

# 运行集成测试
pytest tests/test_module2_integration.py -v
```

### 6. 故障排查

**问题1: 测试失败**
```bash
# 查看详细错误
pytest tests/test_<name>.py -v -s

# 查看覆盖率报告
pytest --cov --cov-report=html
open htmlcov/index.html
```

**问题2: 导入错误**
```bash
# 确保在项目根目录
pwd

# 确保虚拟环境激活
which python

# 重新安装依赖
pip install -r requirements.txt
```

**问题3: Git冲突**
```bash
# 查看状态
git status

# 暂存当前更改
git stash

# 拉取最新代码
git pull

# 恢复暂存
git stash pop
```

### 7. 完成后验证

运行完整验收检查：
```bash
# 1. 运行所有测试
pytest tests/ -v

# 2. 检查覆盖率
pytest --cov=. --cov-report=term-missing | grep TOTAL

# 3. 代码质量检查
pylint modules/ workers/ --max-line-length=120

# 4. 类型检查
mypy modules/ workers/

# 5. 验证文档完整性
grep -r "TODO\|FIXME" modules/ workers/ || echo "No TODOs found"
```

### 8. 预期成果

完成Module 2后，您将拥有：

✅ **静态分析集成**
- RiskScorer模块（风险评分）
- APK解析缓存（性能优化）
- 完整的风险评估系统

✅ **场景测试**
- 登录场景检测和测试
- 支付场景检测和测试
- 分享场景检测和测试

✅ **AI决策优化**
- 探索深度控制（最多50步）
- 循环检测（相同界面3次触发）
- 智能回退策略

✅ **流量监控增强**
- WebSocket消息拦截
- gRPC协议解析
- 自定义协议识别

✅ **质量保证**
- 测试覆盖率 > 85%
- 完整的单元测试
- 集成测试套件
- 更新的文档

### 9. 下一步

完成Module 2后，建议继续：

1. **Module 8: 测试与质量保证** - 提升整体测试覆盖率到90%+
2. **Module 1: 基础设施层** - 优化数据库连接池和缓存
3. **Module 5: API层增强** - 性能优化和安全加固

---

**准备就绪！**

现在您可以：
1. 打开新终端窗口
2. 进入项目目录
3. 激活虚拟环境
4. 运行: `/executing-plans docs/plans/2026-02-21-module2-implementation-plan.md`

祝开发顺利！🚀
