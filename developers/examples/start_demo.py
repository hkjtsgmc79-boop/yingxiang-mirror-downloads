#!/usr/bin/env python3
"""One-command real HTTP integration; temporary tokens remain in memory."""
import argparse
from pathlib import Path
from integration_check import run_checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("integration-results"))
    args = parser.parse_args()
    report = run_checks(args.output)
    print(f"接入验证完成：{report['passed']}项通过，记录保存在 {args.output}")
    print("输出为固定参考SVG；已执行真实HTTP请求，未调用模型生成。")


if __name__ == "__main__":
    main()
