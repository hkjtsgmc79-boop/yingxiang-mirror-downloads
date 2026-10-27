# 映像魔镜开发者接入

版本：0.1.0 · 编制日期：2026年10月27日

公开页面提供目录、接口文档和源码。本地服务用于验证接口创建、查询与结果领取，返回固定参考SVG，运行模式为`fixture_replay`。运行不需要模型API Key，不上传真实照片。

## 一键开始

电脑安装Python 3.12后，下载本仓库ZIP并解压，在仓库根目录运行：

```bash
python3 developers/examples/start_demo.py
```

不需要安装第三方依赖。程序在内存中产生临时访问凭证、启动本机服务、执行独立客户端请求和异常检查，随后自动停止服务。临时凭证不打印、不保存。

结果保存在`integration-results/`：

| 文件 | 内容 |
|---|---|
| `integration-summary.json` | 每项检查的预期、实际结果和判定 |
| `http-requests.jsonl` | 实际HTTP请求编号、路径、状态和耗时，不含凭证 |
| `checked-result.svg` | 明确注明固定参考输出的返回资源 |
| `client/client-result.json` | 独立客户端的任务编号与资源校验记录，具体子目录以运行输出为准 |

## 公开目录

直接访问[公开模板目录](./catalog.json)，或在开发者首页点击“读取公开目录”。公开目录中的`id`对应任务请求中的`template_id`。本机API的模板响应同时提供规范化`template_id`字段。

## 单独启动与调用

需要持续调试时，在本机环境中设置不少于24字符的随机`MIRROR_API_TOKEN`，运行：

```bash
python3 developers/api/service.py --port 8791
```

服务仅监听`http://127.0.0.1:8791`。独立客户端读取`MIRROR_API_BASE`和`MIRROR_API_TOKEN`环境变量：

```bash
python3 developers/examples/run_client.py --output integration-results/client
```

健康检查无需凭证。模板、任务、结果接口均需Bearer凭证。请求结构如下，占位符不是真实密钥：

```http
POST /v1/tasks
Authorization: Bearer <RUNTIME_TOKEN>
Idempotency-Key: example-client-001
Content-Type: application/json

{"template_id":"opera-qingyi","input_asset_ref":"fixture:portrait-01"}
```

首次创建返回201；同一客户端、同一幂等键和相同请求返回200及原任务。相同键的内容不同返回409。按返回的`task_id`查询`GET /v1/tasks/{task_id}`，状态为`succeeded`后，使用相同凭证获取`output_asset_ref`对应的SVG。

支持3个模板编号：`opera-qingyi`、`opera-wusheng`、`opera-hualian`。输入仅接受固定引用`fixture:portrait-01`，不接收外部URL或人像内容。JSON请求上限4096字节，每次进程最多保存128个任务。进程退出后任务和幂等记录清除。

## 自动复现与接入范围

[GitHub Actions检查](https://github.com/hkjtsgmc79-boop/yingxiang-mirror-downloads/actions/workflows/developer-integration.yml)会执行同一套真实HTTP检查，成功后保留脱敏记录。

独立客户端由项目方提供，用于说明如何接入。它不表示已有其他机构签署或接入。公开GitHub Pages承载静态页面和目录；本机任务服务不是公网推理服务。生产部署、正式素材、模型授权和接入条件按[技术接入约定](./terms.md)另行确认。

