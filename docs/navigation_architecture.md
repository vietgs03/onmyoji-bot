# Kiến trúc Navigation Graph (chống "phình to → die")

## Vấn đề
Game có RẤT nhiều màn. Nếu xử lý bằng `if/elif` lồng nhau cho từng màn thì:
- Thêm màn mới = sửa nhiều chỗ, dễ sót, dễ vỡ.
- Không có thuật toán tìm đường → đi mò, lặp vô hạn.

## Nguyên tắc (như một GRAPH, không if lòng vòng)

Mỗi màn hình = **1 NODE** khai báo trong DATA (không phải code). Mọi logic đi
qua thuật toán chung (BFS), không hard-code từng cặp màn.

### Mỗi NODE (Screen) khai báo đúng 4 thứ:

```
SCREEN <ten> {
  identify : [tu khoa OCR / template] -> nhan dien "co phai dang o man nay"
  exits    : { <man_dich> : <how-to-click> }   # CANH (edge) di RA man khac
  dismiss  : how-to-thoat (back/close/cancel/skip) -> ve man CHA
  popups   : [cac popup co the chong len] -> cach dong
}
```

- `identify`: trả lời "tôi đang ở đâu?" (1 hàm chung quét mọi node).
- `exits`: các nút dẫn tới node khác. Đây là CẠNH của graph.
- `dismiss`: cách thoát node này (đa số = nút back/X/cancel; dùng `controls.find_dismiss`).
- `popups`: lớp phủ tạm (download, daily reward...) đóng bằng dismiss trước khi thao tác.

### 3 thao tác CHUNG (thuật toán, không phụ thuộc số node):

1. `where()`  : quét `identify` của mọi node → node hiện tại. O(N) đơn giản.
2. `goto(X)`  : **BFS** trên cạnh `exits` từ node hiện tại → X. Đi từng hop.
                Mỗi hop = click nút `exits[next]`. Drift → re-plan (BFS lại).
3. `escape()` : đệ quy `dismiss` đến khi về HOME. Không if từng màn.

### Quy tắc vàng (giữ clean khi phình to):

- **Thêm màn mới = thêm 1 entry DATA**, không sửa thuật toán.
- **Không có `if screen == 'X'`** trong logic điều hướng. Mọi khác biệt nằm trong DATA node.
- Nhận diện / click / thoát đều qua **3 lớp dùng chung**:
  `controls.py` (nút back/close/cancel), `screen_reader.py` (OCR text), `loading_db.py` (loading).
- Mỗi node thuộc đúng **1 cấp** (HOME → menu cấp 1 → màn cấp 2...). Cạnh chỉ nối cấp kề
  hoặc shortcut rõ ràng. Tránh cạnh chéo lung tung.

### Cấu trúc cây (để dễ hình dung, thực tế là graph có shortcut):

```
HOME
├── Explore (Exploration)
│   ├── Realm Raid
│   ├── Soul Zones
│   ├── Area Boss
│   └── ...
├── Town
│   ├── Duel
│   ├── Demon Encounter
│   └── ...
├── Summon (Summon Room)
├── Shikigami
├── Onmyodo
├── Friends / Guild
└── Shop / Mall
```

Mỗi mũi tên = 1 cạnh `exits`. Đi ngược mũi tên = `dismiss`. BFS lo phần "đường đi".

## File liên quan (mỗi file 1 trách nhiệm, không chồng chéo)
- `knowledge/screen_graph.json`  : DATA - khai báo mọi node + cạnh (nguồn sự thật DUY NHẤT).
- `automation/screen_graph.py`   : load graph + BFS/where/escape (thuật toán chung).
- `automation/controls.py`       : tìm nút back/close/cancel/skip (dùng chung).
- `automation/screen_reader.py`  : OCR text (dùng chung).
- `automation/loading_db.py`     : nhận diện loading (dùng chung).
- `automation/agent.py`          : thao tác cấp thấp (click/shot/wait). KHÔNG chứa logic màn.
