# Cơ chế roll dòng phụ Ngự Hồn (Onmyoji, bản Steam EN), đọc từ RAM

Ngày: 2026-10-14. Nguồn: dữ liệu `com.data.cdata_en.*` và code object dump từ process `client.exe` đang chạy.
Toàn bộ số liệu dưới đây lấy trực tiếp từ bảng của game. Phần nào là suy luận thì có ghi rõ.

## 1. Bảng dữ liệu (file trong `research/npk/data/cdata/`)

| Bảng | File | Nội dung |
|---|---|---|
| `DATA_EQUIP_ATTR` | `cdata_en.equip_attr.json` | 145 "rand_id": danh sách dòng phụ, ngưỡng cộng dồn, hệ số `rang_rand` |
| `EQUIP_UPGRADE` | `cdata_en.equip_upgrade.json` | theo cấp +1..+15: tăng chỉ số chính theo sao, `rattr_id` theo sao |
| `DATA_EQUIP_INIT` | `cdata_en.equip_init.json` | 834 mẫu ngự hồn: `quality` (sao), `base_attr_v`, `rand_rep` |
| `EQUIP_SUIT` | `cdata_en.equip_suit.json` | bộ ngự hồn, hiệu ứng 2/4 món |
| `rune_random_attr` | `cdata_en.rune_random_attr.json` | dòng ngẫu nhiên của rune (6 dòng, mỗi dòng 10/60) |

## 2. Thuật toán (decompile nguyên văn `com/utils/helpers.py::allitem_randEquipAttr`)

```python
def allitem_randEquipAttr(rand_id, rand_count, rand_rep):
    from DynamicConfigData import DATA_EQUIP_ATTR
    import random
    data = {}
    if rand_count and rand_id:
        rand_attr = []
        equip_attr = DATA_EQUIP_ATTR.data.get(rand_id)
        if equip_attr:
            rand_list = list(equip_attr.get('attr_list', []))   # [(tên, giá_trị_gốc, ngưỡng_cộng_dồn), ...]
            rate_list = list(equip_attr.get('rate', []))
            while len(rate_list) < len(rand_list):
                rate_list.append(10)
            total_rate = equip_attr.get('total_rate', 1)
            rang_rand = equip_attr.get('rang_rand', None)
            for x in range(0, rand_count):
                if total_rate <= 0:
                    break
                rand_value = random.randint(1, total_rate)
                index = 0
                for x in rand_list:
                    if len(x) > 2:
                        if rand_value <= x[2]:
                            value = random.uniform(rang_rand[0], rang_rand[1])
                            rand_attr.append([x[0], value])
                            if rand_rep <= 0 and rand_count > 1:      # không cho trùng dòng
                                ... trừ trọng số dòng vừa ra khỏi các ngưỡng phía sau
                                total_rate -= rate_list[index]
                                del rand_list[index]; del rate_list[index]
                            break
                        else:
                            index += 1
        if len(rand_attr) > 0:
            data['rattr'] = rand_attr
    return data
```

Ý nghĩa:
1. Chọn **loại dòng** bằng `randint(1, total_rate)` so với ngưỡng cộng dồn (cột thứ 3 của `attr_list`).
2. Chọn **độ lớn** của dòng là `uniform(rang_rand[0], rang_rand[1])`. Số lưu trong `rattr` là **hệ số** này. Chỉ số thực tế bằng `giá_trị_gốc * hệ số` (xem `get_equip_attr_rand_param` và `calc_attr_hit_cnt`).
3. Khi roll nhiều dòng cùng lúc (`rand_count > 1`) và `rand_rep = 0` (mọi ngự hồn thường đều là 0), dòng đã ra bị loại khỏi pool, nên các dòng ban đầu **không trùng nhau**.

## 3. Số liệu cụ thể

### 3.1 Tỉ lệ loại dòng (rand_id 1..6 và 1001..1006)
11 loại dòng, mỗi loại 10/110, tức **đều nhau 1/11 ≈ 9.09%**:

| Dòng | Giá trị gốc (100%) |
|---|---|
| HP (cộng thẳng) maxHpAdditionVal | 114 |
| Thủ (cộng thẳng) defenseAdditionVal | 5 |
| Công (cộng thẳng) attackAdditionVal | 27 |
| HP% | 3% |
| Thủ% | 3% |
| Công% | 3% |
| Tốc | 3 |
| Tỉ lệ bạo | 3% |
| Bạo thương | 4% |
| Hiệu quả kháng (debuffEnhance) | 4% |
| Kháng hiệu quả (debuffResist) | 4% |

### 3.2 Hệ số độ lớn theo sao (`rang_rand`)
| Sao | rand_id lúc rơi | rand_id khi cường hóa | rang_rand |
|---|---|---|---|
| 1★ | 1 | 1001 | 0.3 – 0.4 |
| 2★ | 2 | 1002 | 0.4 – 0.5 |
| 3★ | 3 | 1003 | 0.5 – 0.6 |
| 4★ | 4 | 1004 | 0.6 – 0.7 |
| 5★ | 5 | 1005 | 0.7 – 0.8 |
| **6★** | 6 | **1006** | **0.8 – 1.0** |

Ví dụ ngự hồn 6★: mỗi lần trúng dòng Tốc sẽ cộng `3 × U(0.8, 1.0)` = **2.4 – 3.0** tốc (phân phối đều).

### 3.3 Cường hóa (`EQUIP_UPGRADE.rattr_id`)
Chỉ ở **+3, +6, +9, +12, +15** mới có `rattr_id = [1001..1006]` (chọn theo sao). Các cấp khác có rattr_id bằng 0, chỉ tăng chỉ số chính.
`getEuipStrengthAttrInfo` xác nhận: tổng số lần roll khi cường hóa là `strongLevel // 3`, và các lần roll được nối vào cuối `rattr`.
Một ngự hồn +15 có 9 phần tử trong `rattr` (`getEuipLuckyAttr` kiểm tra `len(rattr) >= 9`), gồm 4 dòng ban đầu và 5 lần cường hóa.

### 3.4 Các bảng rand_id khác
- `2001..2147` (~130 bảng): dùng cho ngự hồn đặc biệt hoặc sự kiện. Pool bị giới hạn (vd 2001 chỉ có Tốc/Bạo/Bạo thương/Hiệu quả/Kháng), có trọng số riêng, `rang_rand` cố định (1.0, 0.87, 0.75).
- Dữ liệu đầy đủ của từng bảng nằm trong `cdata_en.equip_attr.json`.

## 4. Giới hạn và phần suy luận
- `allitem_randEquipAttr` là code **phía client**, dùng cho preview, sự kiện và ngự hồn tạo sẵn. Lần roll thật khi cường hóa diễn ra **trên server** và không có trong client.
  Phía client có mô phỏng ngược (`BatchStrengthenLogic.calc_attr_hit_cnt`) dùng đúng `EQUIP_UPGRADE.rattr_id` và `rang_rand` như trên, nên khả năng cao server dùng cùng bảng. Đây là suy luận, chưa có bằng chứng trực tiếp.
- Client không cho biết quy tắc "khi cường hóa, nếu chưa đủ 4 dòng thì thêm dòng mới, ngược lại thì nâng một dòng đã có". Quy tắc này nằm ở server.
- 6 blob bindict khác không parse được (skin_fx, skill_ai, ...). Chúng không liên quan đến ngự hồn.
