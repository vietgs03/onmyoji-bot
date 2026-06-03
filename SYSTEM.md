# HỆ THỐNG Onmyoji Bot - Tổng quan (build xong, sẵn sàng học tối nay)

> Đọc `knowledge/LEARNINGS.md` để biết MỌI bài học chi tiết. File này = bản đồ hệ thống.

## 4 hệ thống đã xây

```mermaid
graph LR
    subgraph CTRL[1. Điều khiển]
        SRV[ps/server.ps1<br/>fgclick/bgshot/restore] --> CC[control_client.py]
    end
    subgraph PERCEPT[2. Tri giác + Bản đồ]
        CC --> P[perception.py<br/>dhash/buttons/loading]
        P --> WM[world_model.py<br/>graph 105 state/185 edge]
        WM --> EXP[explorer.py<br/>tự khám phá + né trận]
    end
    subgraph ML[3. ML/Training]
        OBS[594 click samples] --> AFF[affordance AUC.77]
        IMG[88 labeled screens] --> SCLF[screen_clf acc.70]
        TES[tesseract] --> OCR[ocr.py đọc text/AP/vàng]
    end
    subgraph KNOW[4. Kiến thức + Vector DB]
        KB[game_kb.py: 430 docs<br/>269 shiki+913 skills+69 soul<br/>+26 mode+9 battle+24 guide] --> VDB[vectordb.py<br/>semantic search]
    end
    EXP --> AGENT[automation/agent.py<br/>where/goto/tap/resources/ask]
    AFF --> AGENT
    SCLF --> AGENT
    OCR --> AGENT
    VDB --> AGENT
    AGENT --> TASKS[tasks/run.py]
```

## Lệnh nhanh (đều dùng .venv/bin/python)

| Việc | Lệnh |
|------|------|
| Tổng kết kiến thức | `cat knowledge/LEARNINGS.md` |
| Tra cứu KB | `python knowledge/game_kb.py stats\|shikigami <q>\|soul <q>\|skill <name>\|mode <q>` |
| Hỏi KB (ngữ nghĩa) | `python knowledge/vectordb.py query "câu hỏi"` |
| Train lại ML | `python ml/train.py` |
| Khám phá game | `python -u scripts/explorer.py 300` (game phải chạy) |
| Agent: đang ở đâu | `python automation/agent.py where` |
| Agent: đi tới màn | `python automation/agent.py goto HOME` |
| Agent: đọc tài nguyên | `python automation/agent.py resources` |
| Agent: hỏi KB | `python automation/agent.py ask "best ATK soul"` |
| Chạy task | `python tasks/run.py daily_signin` |

## Số liệu hiện tại
- **Graph UI**: 105 state vật lý, 185 edge, 18 chức năng game logic.
- **KB**: 430 documents (269 shikigami + 913 skills + 69 souls + 26 modes + 9 battle + 24 guide + 18 screen + ...).
- **ML**: affordance AUC 0.765, screen classifier acc 0.697 (vượt baseline rõ rệt).
- **Vector DB**: TF-IDF 430 docs, vocab ~30k, trả lời ngữ nghĩa tốt.

## Việc cho tối nay (khi game chạy)
1. Chạy explorer phủ nốt game (label thêm state, thu thêm data ML).
2. Re-train ML với data mới (affordance/screen_clf sẽ tốt hơn).
3. Học thao tác từng mode (Exploration/Soul Zone farm) -> viết task thật.
4. (Tùy) nâng vector DB lên embedding thật (sentence-transformers) nếu cần độ chính xác cao hơn.
