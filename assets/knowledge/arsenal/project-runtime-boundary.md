# 项目级 .redcap 运行边界

外部项目使用 RedCap 时，项目根目录下的 `.redcap/` 是唯一运行目录。任务事实、证据、日志、临时文件和安装清单都应写入该目录，不能写回 RedCap 源仓库。

RedCap 自开发是显式例外：只有当前工作区就是 RedCap 源仓库时，证据才可以进入 `assets/evidence/`。
