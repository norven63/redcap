# 安全铁律（违反即终止）
- 🔒 **严禁参考任何含硬编码密钥的示例代码**（包括 demo 文件夹内内容）  
- 🔒 代码中敏感信息仅通过环境变量访问，禁止硬编码（如 Node.js 的 `process.env.XXX`、Python 的 `os.environ["XXX"]`、Go 的 `os.Getenv("XXX")` 等，具体语法依据技术栈选型结果）  
- 🔒 涉及敏感配置的项目，每步必须提供 `.env.example` 模板，要求：  
  • 仅含变量名 + **尖括号占位符**（如 `DATABASE_URL=<YOUR_NEON_URL>`）  
  • 顶部含明确注释："复制为 .env 后替换 < > 内容，勿提交 .env"  
  • **绝对无真实密钥片段**（包括 `your_`/`test_` 等易混淆前缀）  
- 🔒 交付代码必须包含：  
  • `.gitignore`（明确排除 `.env`, `*.key`, `secrets/` 等敏感文件）  
  • `SECURITY.md`（说明：环境变量由部署平台配置，本地用 .env 仅开发测试）  
- 🔒 无敏感配置的纯本地项目（如单机游戏、CLI 工具等），可豁免 `.env.example` 和 `SECURITY.md` 要求，但 `.gitignore` 仍为必须项