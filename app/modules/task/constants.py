"""任务模块常量：队列名、任务类型"""

# BullMQ 队列名（bull 前缀 key 与 JS 生态互通，可用 Node worker 并行消费）
QUEUE_FILE_PROCESS = 'file-process'

# 任务类型
TASK_FILE_PARSE = 'file.parse'  # 文件解析入库：解析→切分→向量化
