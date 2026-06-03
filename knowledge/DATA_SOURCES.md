# Data Sources - Onmyoji Bot

Tong hop moi nguon data da thu thap cho bot (Global/EN, Steam PC).

## 1. Text / Knowledge (Global EN - khop 100%)
| Nguon | Noi dung | File |
|-------|----------|------|
| Fandom EN wiki | 269 shikigami, 913 skills, 69 souls, 26 modes, battle mechanics, progression | `data/fandom/*.json` |
| OAS (CN) | 52 chuc nang/hoat dong game + tuy chon tu dong hoa | `knowledge/oas_features.json` |

-> Nap vao `knowledge/game_kb.py` (482 docs) + vector DB semantic search.

## 2. Anh / Image data sources
| Nguon | So luong | Server | Dung de | Vi tri (local, gitignored) |
|-------|----------|--------|---------|------|
| Fandom shikigami portrait | 265 | **EN** | nhan dien nhan vat (ten chuan) | `data/fandom_images/` |
| Game loading art (Steam) | 257 | **EN** | augment / nhan dien loading | `data/game_assets/en_loading/` |
| res.npk UI sprite | 370 | game | UI element / background | `data/game_assets/res_npk/png/` |
| face_big + headicon | 41 | EN | avatar | `data/game_assets/face_big`, `headicon` |
| **Screenshot cua ban** | 130 | **EN** | ground truth UI (quan trong nhat) | `exploration/screens/` |

## 3. UI Layout goc - "code dinh vi" (DAC BIET GIA TRI)
Giai ma tu **res.npk** (NetEase NXPK, key XOR=150 + flag&1 zlib, ref `zhouhang95/neox_tools`):
- **1579 UI panel** (CocoStudio widgetTree), he toa do **1136x640** (goc duoi-trai).
- **11252 button co ten + toa do + anh** (vd `button_auto` x=55 y=52, `buttonExit`, `closeBtn`...).
- File: `knowledge/ui_layouts.json`.
- LUU Y: toa do 1136x640 goc CocoStudio -> can scale sang client Steam 1152x679 + flip Y khi dung.

### Cach giai ma lai (neu game update):
```
.venv/bin/python scripts/nxpk_extract.py extract "<game>/res.npk" /tmp/out --filter json
.venv/bin/python scripts/parse_ui_layout.py /tmp/out/json   # -> knowledge/ui_layouts.json
```

## 4. Vi tri folder game Steam
`C:\Program Files (x86)\Steam\steamapps\common\Onmyoji` (appid 551170, 27GB)
- NPK assets: `res.npk`(UI/config), `tex_res.npk`(5GB texture KTX/PVR - GPU encoded, can PVRTexTool), `model2.npk`, `script.npk`(NeoX bytecode `e4 b1...`), `sound.npk`.
- Asset EN lo thien: `Documents/mulnation/en/` (loading art), `Documents/face_big`, `headicon`.

## 5. Nguon da kiem tra - KHONG dung
- `tex_res.npk` textures: KTX/PVR nen GPU + atlas .plist -> cong suc lon, gia tri thap.
- `script.npk`: NeoX VM bytecode -> can decompile sau, it gia tri thuc tien cho bot.
- HuggingFace/Kaggle: khong co dataset Onmyoji.
- Cac bot khac (AcademicDog 380*, yys-auto): deu CN/Android, anh CN -> chi augment.

## 6. Nguon anh EN BO SUNG (GitHub - tim phien 2)
| Nguon | So luong | Server | Dung de | Vi tri |
|-------|----------|--------|---------|--------|
| trmzaiu/onmyoji_wiki | **582** (461 shiki icon + 65 soul + 38 stats + 12 onmyoji + 6 rarity) | **EN** | nhan dien shikigami/soul icon nho trong UI | `data/external/wiki/` |
| qiduQD/Onmyoji-Auto-Assistant | 44 button template | CN | augment button recog | `data/external/qidu_templates/` |

Repo `trmzaiu/onmyoji_wiki` co TONG 6005 anh EN (ten file = ten EN chuan):
shikigami icons(461)/images(458)/skills(933)/skins(713)/shards(270)/bios(61) + souls + onmyoji + effects(373).
Co the keo them skill/skins neu can. Regen: `rebuild_assets.py wiki`.
