# 服务器连接信息

## 通过 SSH 反向隧道访问内网服务器

### 公网跳板机

| 项目 | 值 |
|-----|---|
| 公网 IP | <jump-host> |
| 隧道用户 | tunnel |
| 隧道用户密码 | Tunnel@2025! |

### 内网服务器连接信息

| 节点 | 主机名 | 连接命令 | 服务状态 |
|-----|-------|---------|---------|
| <worker-node> | hbp-wlfzzz-pro-07 | `ssh -p <worker-port> devops@<jump-host>` | 持久化 |
| <frontend-node> | hbp-wlfzzz-pro-08 | `ssh -p <frontend-port> devops@<jump-host>` | 持久化 |
| <api-node> | hbp-wlfzzz-pro-09 | `ssh -p <api-port> devops@<jump-host>` | 持久化 |
| 10.16.139.51 | hyb-f0b0f8d9f0cb | `ssh -p 16005 devops@<jump-host>` | 持久化 |

**devops 用户密码**:
- <worker-node> / <frontend-node> / <api-node>: `Fanzha@2025`
- 10.16.139.51: `fanzha@2024`

### SSH Config 配置

添加到 `~/.ssh/config`:

```
Host <worker-alias>
    HostName <jump-host>
    Port 16002
    User devops

Host <frontend-alias>
    HostName <jump-host>
    Port 16003
    User devops

Host <api-alias>
    HostName <jump-host>
    Port 16004
    User devops

Host hbp-51
    HostName <jump-host>
    Port 16005
    User devops
```

之后可直接使用 `ssh <worker-alias>`、`ssh <frontend-alias>`、`ssh <api-alias>`、`ssh hbp-51` 连接。

---

## 持久化隧道配置

四台内网服务器已配置 systemd + autossh 持久化隧道服务：

- **服务名称**: `ssh-tunnel.service`
- **服务用户**: root
- **自动重连**: 是 (autossh)
- **开机自启**: 是 (systemd enabled)

### 服务管理命令

```bash
# 查看状态
sudo systemctl status ssh-tunnel

# 重启服务
sudo systemctl restart ssh-tunnel

# 停止服务
sudo systemctl stop ssh-tunnel

# 查看日志
sudo journalctl -u ssh-tunnel -f
```

### 服务配置文件

位置: `/etc/systemd/system/ssh-tunnel.service`

```ini
[Unit]
Description=SSH Reverse Tunnel to Public Server
After=network.target

[Service]
Type=simple
User=root
Environment="AUTOSSH_GATETIME=0"
ExecStart=/usr/bin/autossh -M 0 -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -i /root/.ssh/tunnel_key -N -R <PORT>:127.0.0.1:60002 tunnel@<jump-host>
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

各节点端口：
- worker 节点: `<PORT>` = 16002
- frontend 节点: `<PORT>` = 16003
- api 节点: `<PORT>` = 16004
- 51 节点: `<PORT>` = 16005

### 密钥位置

- 内网服务器: `/root/.ssh/tunnel_key`
- 公网服务器: `/home/tunnel/.ssh/authorized_keys` (包含各节点服务器的公钥)

---

---

## 四节点统一升级（server.js/run.sh）

目标：四个节点同时升级到同一份 `server.js` / `run.sh`，并通过 `/healthz.serverJsSha` 与响应头 `X-Server-JS-Sha` 校验节点是否一致，避免“混跑旧版本”。

前置：
- 本机 `~/.ssh/config` 已配置 `<worker-alias>/08/09/51`（见上方）
- 四台节点 `devops` 用户已加入 `docker` 组（`id -nG` 包含 `docker`），否则执行 docker 会失败/需要 sudo
- 节点镜像 tag 已对齐（示例：`screenshot-api:1.0.2`），如不一致请先对齐镜像 tag

### 一键升级（从本机仓库目录执行）

```bash
cd "/Users/liubo/Desktop/重要项目/工程项目/高效网站截图工具"
node --check server.js && bash -n run.sh

for h in <worker-alias> <frontend-alias> <api-alias> hbp-51; do
  echo "==> upgrading $h"
  scp server.js run.sh "$h:/home/devops/"
  ssh "$h" 'set -e;
    chmod 644 /home/devops/server.js;
    chmod +x /home/devops/run.sh;
    EXTERNAL_SERVER_JS=/home/devops/server.js IMAGE_TAG=1.0.2 /home/devops/run.sh'
  ssh "$h" 'curl -s -D - http://localhost:3000/healthz -o /dev/null | tr -d "\r" | grep -i "^x-server-js-sha:"; curl -s http://localhost:3000/healthz'
done
```

说明：
- `IMAGE_TAG=1.0.2`：按需替换为当前生产镜像版本。
- `EXTERNAL_SERVER_JS=/home/devops/server.js`：容器挂载外部 `server.js`，做到“不重建镜像即可升级代码”。
- 若某节点启动报 `EACCES`，确保 `server.js` 权限至少为 `0644`（可读）。

## 故障排查

### 隧道无法连接

1. 检查服务状态: `sudo systemctl status ssh-tunnel`
2. 检查进程: `ps aux | grep autossh`
3. 查看日志: `sudo journalctl -u ssh-tunnel --since "1 hour ago"`
4. 检查公网服务器端口: `ssh tunnel@<jump-host> "sudo netstat -tlnp | grep 1600"`

### 重启隧道服务

```bash
# 在内网服务器上
sudo systemctl restart ssh-tunnel
```

### 公网服务器防火墙

```bash
# 检查 iptables
sudo iptables -L INPUT -n | grep 1600

# 如果端口未开放
sudo iptables -I INPUT -p tcp --dport 16002 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 16003 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 16004 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 16005 -j ACCEPT
```
