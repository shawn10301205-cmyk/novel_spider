#!/usr/bin/env python3
"""一次性迁移脚本：将旧 JSON 数据导入 SQLite"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage import migrate_json_data

if __name__ == "__main__":
    print("🚀 开始迁移 JSON 数据到 SQLite...")
    count = migrate_json_data()
    print(f"\n✅ 迁移完成，共导入 {count} 条记录")
