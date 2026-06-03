#!/usr/bin/env python3
"""
train.py - Pipeline train + eval TAT CA model ML cua bot.

Chay 1 lenh de:
  1. Build dataset tu observations
  2. Train + eval affordance model (click co tac dung?)
  3. Train + eval screen classifier (man hinh la gi?)
  4. In bao cao tong hop

Dung: python train.py
Chay lai moi khi explorer thu them data (observations.jsonl / world.json cap nhat).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    print("=" * 60)
    print("ONMYOJI BOT - TRAIN PIPELINE")
    print("=" * 60)

    print("\n[1/3] Dataset affordance")
    import dataset
    X, y, meta = dataset.build_dataset()
    print(f"  {X.shape[0]} mau, {X.shape[1] if len(X) else 0} features, "
          f"{int(y.sum())} positive / {int((y==0).sum())} negative")

    print("\n[2/3] Affordance model")
    import affordance
    affordance.evaluate()
    affordance.train()

    print("\n[3/3] Screen classifier")
    import screen_clf
    screen_clf.evaluate()
    screen_clf.train()

    print("\n" + "=" * 60)
    print("XONG. Models luu o ml/models/")
    print("=" * 60)


if __name__ == "__main__":
    main()
