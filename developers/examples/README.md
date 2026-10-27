# 独立客户端与接入验证

在仓库根目录运行：

```bash
python3 developers/examples/start_demo.py
```

这会实际创建本地 HTTP 服务并调用独立客户端，无需安装依赖或管理运行令牌。输出是固定参考 SVG，验证接口请求、任务查询、资源获取及异常行为，不产生AI图片。

已单独启动服务时，客户端读取环境变量 `MIRROR_API_BASE`（默认 `http://127.0.0.1:8791`）和 `MIRROR_API_TOKEN`：

```bash
python3 developers/examples/run_client.py --output integration-results/client
```

`client-result.json` 记录实际请求ID、任务ID、耗时和输出文件校验值，不保存令牌。`integration_check.py` 还覆盖缺失/错误鉴权、幂等复用与冲突、无效输入、伪造客户端字段、超限请求体、跨客户端任务和结果访问、404及Host检查。

客户端由项目方提供作为开发接入样例，不登记为其他机构已经接入。
