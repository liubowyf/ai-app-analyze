# 文档入口

默认只读这两份：

1. `docs/CURRENT_STATE.md`
   - 当前系统唯一真实状态
   - 架构、配置、运行、验收口径、成功样本都以此为准

2. `docs/CONTEXT_INDEX.md`
   - 压缩后的内容索引
   - 按问题直接定位到最小代码入口与最小文档入口

如果要核对 host-agent 节点宿主机 Agent 的真实部署方式，再看：

3. `deploy/redroid-host-agent/docker-compose.yml`
   - `redroid-host-agent` 的 compose 部署入口
   - 当前 host-agent 环境变量与挂载边界
