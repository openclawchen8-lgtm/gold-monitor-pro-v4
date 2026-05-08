#!/usr/bin/env python3
"""
執行所有測試

用法：
  python3 run_all.py
"""
import subprocess
import sys
import os

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    print("=" * 60)
    print("Gold Monitor Pro v4 - 測試套件")
    print("=" * 60)
    print()
    
    test_files = sorted([f for f in os.listdir(TESTS_DIR) if f.startswith("test_") and f.endswith(".py")])
    
    results = {}
    
    for test_file in test_files:
        test_path = os.path.join(TESTS_DIR, test_file)
        test_num = test_file.replace("test_", "").replace(".py", "")
        
        print(f"\n{'─' * 60}")
        print(f"執行: {test_file}")
        print(f"{'─' * 60}")
        
        result = subprocess.run(
            ["python3", test_path],
            capture_output=False
        )
        
        results[test_file] = "✅" if result.returncode == 0 else "❌"
    
    print(f"\n{'=' * 60}")
    print("測試結果")
    print(f"{'=' * 60}\n")
    
    for test_file, status in results.items():
        print(f"  {status} {test_file}")
    
    passed = sum(1 for v in results.values() if v == "✅")
    total = len(results)
    
    print(f"\n通過: {passed}/{total}")
    
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()