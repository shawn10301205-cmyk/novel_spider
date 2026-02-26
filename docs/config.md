# 配置说明

项目使用两层配置文件：

## config.yaml（已提交到仓库）
通用配置模板，包含所有配置项的结构，敏感值留空。

## config.local.yaml（本地专用，不提交）
存放敏感信息（飞书 webhook_url、app_url 等），会**深度合并覆盖** `config.yaml` 中的同名字段。

### 首次部署
复制以下内容到 `config.local.yaml`，填入真实值：

```yaml
feishu:
  webhook_url: "你的飞书webhook地址"
  app_url: "你的飞书应用链接"
```
