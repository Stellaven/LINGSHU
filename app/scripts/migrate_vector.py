"""向量数据迁移脚本，TODO: 补充具体迁移逻辑"""
import sys
from pathlib import Path

# 保证以 python scripts/migrate_vector.py 运行时可导入项目包（app根目录入sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    # TODO: 旧集合 -> 新集合的向量数据迁移
    pass


if __name__ == "__main__":
    main()
