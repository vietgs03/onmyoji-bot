# KẾ HOẠCH HỆ THỐNG - Onmyoji Bot (build tối nay)

Mục tiêu: hệ thống Kiến thức + ML/Training + Automation + Vector DB hoàn chỉnh,
để tối nay học/automation tiếp.

## GIAI ĐOẠN A - Hệ thống Kiến thức (knowledge/)
- [x] LEARNINGS.md - tổng kết mọi thứ đã học (single source of truth)
- [x] game_kb.py - gộp data/fandom + exploration graph thành KB thống nhất, tra cứu được
- [x] Kiểm tra KB thiếu gì: cơ chế chiến đấu, thao tác UI mỗi mode, meta team/soul build

## GIAI ĐOẠN B - Hệ thống ML/Training (ml/)
- [x] dataset.py - featurize observations.jsonl (594 click samples) thành X,y
- [x] affordance.py - model dự đoán "click (x,y) ở màn này dẫn đi đâu / có tác dụng không"
- [x] screen_clf.py - phân loại màn từ ảnh (HOG/color hist + sklearn) bổ trợ dhash
- [x] ocr.py - đọc text nút + số liệu (AP/tiền/vé) bằng tesseract
- [x] train.py - pipeline train + eval, lưu model ml/models/

## GIAI ĐOẠN C - Hệ thống Automation (automation/, tasks/)
- [x] agent.py - lớp điều phối: nhận diện màn -> navigate (BFS) -> thực thi task
- [x] tasks: daily_signin, farm_exploration, summon, ... (mỗi task = sequence + verify)

## GIAI ĐOẠN D - Research kiến thức bổ sung
- [x] Kiểm tra KB hiện có vs cần: liệt kê gap
- [x] Crawl bổ sung: cơ chế battle, skill chi tiết, team/meta, thao tác mỗi mode
- [x] Lưu structured + raw

## GIAI ĐOẠN E - Vector Database (knowledge/vectordb/)
- [x] Chọn embedding (local: sentence-transformers, hoặc TF-IDF nếu nhẹ)
- [x] Index toàn bộ KB (shikigami/soul/mode/screen/learnings) thành vector
- [x] query.py - tra cứu ngữ nghĩa: "soul nào tốt cho ATK shikigami?", "làm sao farm soul?"
- [x] Tích hợp vào agent (bot tự hỏi KB khi cần quyết định)

## Nguyên tắc
- Mỗi thành phần PHẢI có validation/test riêng (in số liệu, eval accuracy).
- Dùng .venv/bin/python. Commit từng giai đoạn.
