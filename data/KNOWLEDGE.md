# KNOWLEDGE BASE - Onmyoji (nap tu Fandom + nghien cuu)

> Cap nhat: 2026-06-02. Nguon chinh: onmyoji.fandom.com (MediaWiki API).
> Data structured nam o `data/fandom/*.json`.

## Nguon data (da thu nghiem)
| Nguon | Trang thai | Ghi chu |
|-------|-----------|---------|
| onmyoji.fandom.com (API) | OK | Nguon chinh, data day du, co ten EN/CN/JP |
| guidemyoji.com | CHAN (Cloudflare 403) | WP API /categories ok nhung /posts bi chan |
| yys.huijiwiki.com | CHAN (Cloudflare) | wiki TQ lon, bi challenge |
| wiki.biligame.com/yys | OK (mot phan) | wiki TQ Bilibili, encoding category TQ kho |

## 1. SHIKIGAMI (式神) - 269 con
File: `data/fandom/shikigami_parsed.json` (id, name_en, name_cn, name_jp, name_gl, rarity)
- Phan bo: **SP 48, SSR 82, SR 68, R 38, N 30**.
- Co ca ten EN (dung cho ban Global cua minh) va ten CN/JP (doi chieu wiki TQ).
- VD: {id:200, name_en:"Momo no Sei", name_cn:"桃花妖", rarity:"SR"}
- **Full wikitext**: `data/fandom/shikigami_full.json` (271 con: skill, evolve element,
  CV, intro, summon method, SP version, link kamigame JP). 55 con co SP version.
  Parsed: `shikigami_full_parsed.json`.

## TOOL TRA CUU
`python3 scripts/kb.py stats | shikigami <ten> | soul <ten> | rarity SSR`

## 2. SOULS / 御魂 (Mitama) - 69 bo
File: `data/fandom/souls_parsed.json` (no, name_en/cn/jp, type, combo2, combo4)
- type = thuoc tinh (ATK/DEF/HP/Crit/Resist/Speed...).
- combo2 = hieu ung 2 mon, combo4 = hieu ung 4 mon (set bonus).
- Day la he thong trang bi cot loi de farm (mode "Soul Zones": Orochi, Sougenbi, Sea of Eternity).

## 3. GAME MODES (che do choi) - 26 trang
File: `data/fandom/game_modes.json` (wikitext)
- Exploration (探索), Realm Raid (突破), Soul/御魂 zones, Secret Zone (秘闻),
  Area Boss, Bondling (契灵), Hunt (悬赏), Demon Encounter (逢魔),
  Hyakki Yakou (百鬼夜行), Duel (斗技), Kekkai (结界), Orochi (八岐大蛇),
  Six Realms Gates, Totem (图腾), Story Retrospect...
- Day la cac UI/hoat dong minh se can map trong UI state-graph.

## 4. CORE MECHANICS - 5 trang
File: `data/fandom/core_pages.json`
- Onmyoji (gioi thieu), Courtyard (庭院/san nha), Soul (御魂), Demon Parade.

## 5. CATEGORY INDEX
File: `data/fandom/category_index.json`
- 12 category lon: danh sach ten trang theo SP/SSR/SR/R/N/Soul/Boss/Event(282)/Skill(322)...
- Dung lam "danh ba" de crawl sau.

## Lien ket voi UI automation
- Ten EN cua shikigami/soul/mode => dung de OCR/match nut trong game ban Global.
- Game modes => moi cai la 1 NODE trong ui_graph (xem ARCHITECTURE.md).
- Soul sets => logic chon doi hinh / farm sau nay.

## TODO nap them (vong sau)
- [ ] Crawl full wikitext tung shikigami (skill, evolve, soul build de xuat).
- [ ] Crawl Event guides (282 trang) co chon loc.
- [ ] Tim cach lay data TQ tu biligame (skill nang cap meta).
- [ ] guidemyoji: thu qua web archive (web.archive.org) de vuot Cloudflare.
