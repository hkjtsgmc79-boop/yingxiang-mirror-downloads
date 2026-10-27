# 本地接入服务

Python 3.12 标准库实现。服务仅监听 `127.0.0.1`；任务返回固定参考 SVG，`execution_mode=fixture_replay`，不调用模型服务、不接收真实人像。

在仓库根目录运行一键验证：

```bash
python3 developers/examples/start_demo.py
```

脚本会在内存中产生临时客户端令牌、启动一个随机端口的 HTTP 服务、执行正常与异常请求、调用独立客户端、保存记录，然后停止服务。令牌不会打印或保存到记录中。

结果保存在 `integration-results/`：`integration-summary.json`、`http-requests.jsonl`、`checked-result.svg`，以及独立客户端的 `client-result.json` 和 `result.svg`。

单独启动服务时，请在本机环境变量中提供长度不少于24字符的随机 `MIRROR_API_TOKEN`，再运行：

```bash
python3 developers/api/service.py --port 8791
```

服务读取 `developers/catalog.json`。运行令牌对应 `local-demo-client`，客户端身份由服务器映射。多客户端隔离验证由集成脚本设置仅在子进程环境中的 `MIRROR_API_TOKENS_JSON`。

健康检查 `GET /v1/health` 无需鉴权。模板、任务和结果接口要求 `Authorization: Bearer <运行时令牌>`。创建任务还要求 `Idempotency-Key`。请求体只接受 `template_id` 和 `input_asset_ref`；后者固定为 `fixture:portrait-01`。JSON请求体上限4096字节，单次进程最多保存128个任务，状态和幂等记录随进程退出清除。

本目录是可运行的接入基础。公网推理服务的部署、计费、持久化、业务素材授权与实际合作方接入另行约定；GitHub Pages 用于公开说明和资料目录。
