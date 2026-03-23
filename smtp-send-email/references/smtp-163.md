# 163 邮箱 SMTP 参考

## 推荐配置

- SMTP Host: `smtp.163.com`
- SSL Port: `465`
- STARTTLS Port: `587`
- Username: 你的 163 邮箱账号（完整地址）
- Password: 163 开启 SMTP 后生成的客户端授权码（专属密码）

## 常见故障

1. `535 Error: authentication failed`
- 原因: 使用了登录密码，或授权码错误。
- 处理: 在 163 邮箱后台重新生成客户端授权码后重试。

2. `Connection timed out`
- 原因: 网络策略拦截了 SMTP 端口。
- 处理: 优先尝试 `465 SSL`；若不通再试 `587 + STARTTLS`。

3. 附件乱码或类型异常
- 原因: 邮件客户端对 MIME 推断不同。
- 处理: 保持文件扩展名正确，脚本会自动基于扩展名设置 MIME 类型。
