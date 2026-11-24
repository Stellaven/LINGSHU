"""认证鉴权域：登录、续期、退出、改密与统一鉴权拦截

设计要点（详见 JWT 登录与令牌生命周期管理技术设计方案）：
- Access Token：短效JWT，无状态，带 token_version；
- Refresh Token：随机字符串，一次一用，服务端只存哈希；
- 撤销能力：Redis Session + TokenVersion + JTI 黑名单（无Redis时降级为进程内存存储）；
- 改密走版本号，退出走黑名单，职责分离。
"""
