# 映像魔镜安卓内测版

**[打开专用下载页](https://hkjtsgmc79-boop.github.io/yingxiang-mirror-downloads/)**　|　**[分享短链接](https://is.gd/yxmojing)**

扫码打开下载页，或保存二维码供现场使用：

<img src="./assets/download-qr.png" alt="映像魔镜下载页二维码" width="180" height="180">

[下载PNG二维码](https://hkjtsgmc79-boop.github.io/yingxiang-mirror-downloads/assets/download-qr.png) · [下载SVG矢量二维码](https://hkjtsgmc79-boop.github.io/yingxiang-mirror-downloads/assets/download-qr.svg)


映像魔镜面向横屏安卓魔镜设备，提供传统文化妆造模板浏览、相机拍摄和照片导入等基础体验。本仓库提供安装包下载和安装说明。

**[下载安卓安装包（约72.5 MB）](https://github.com/hkjtsgmc79-boop/yingxiang-mirror-downloads/releases/download/v4.0.0-dev.2-android.1/yingxiang-mirror-4.0.0-dev.2-android.1.apk)**　|　**[查看版本发布页](https://github.com/hkjtsgmc79-boop/yingxiang-mirror-downloads/releases/tag/v4.0.0-dev.2-android.1)**

当前版本：`4.0.0-dev.2-android.1`（设备内测版）。

## 安装与体验

1. 从上方链接或发布页的 **Assets** 下载 `.apk` 文件；也可复制到U盘，再在魔镜设备安装。
2. 按安卓系统提示允许该来源安装应用，打开“映像魔镜”。
3. 体验界面、触摸、妆造模板、相机拍摄或照片导入；相机需相应硬件支持和权限。

主要测试目标为安卓12、1080p横屏触摸一体机，其他设备需另行验证适配。详细步骤见发布附件 `INSTALL.txt`。

## 版本范围

- 安装、界面、触摸和摄像头已有项目方基础正常反馈。
- 真实照片、视频生成及作品领取需要另行配置配套后端、设备连接和模型服务额度；默认生成次数为0。
- 发布附件中的 `SHA256SUMS.txt` 可用于核对下载文件。APK与已归档dev2测试包字节一致。

## 下载文件

| 文件 | 用途 |
|---|---|
| `yingxiang-mirror-4.0.0-dev.2-android.1.apk` | 安卓设备内测安装包 |
| `INSTALL.txt` | 安装及功能条件说明 |
| `SHA256SUMS.txt` | 文件完整性校验值 |

模型API Key由工作人员在配套后端配置。请勿将API Key、设备配对码或个人照片提交到公开仓库或公开反馈中。

项目主体：杭州市新青年歌舞团股份有限公司。

## 开发者接入

[打开开发者中心](https://hkjtsgmc79-boop.github.io/yingxiang-mirror-downloads/developers/) · [快速开始](./developers/quickstart.md) · [接入约定](./developers/terms.md)

公开文档、模板目录和独立客户端代码已放在 `developers/`。接入服务使用固定参考响应，可在本地或 GitHub Actions 中运行；生产模型服务需另行部署并授权。接入验证不需要模型 API Key。
