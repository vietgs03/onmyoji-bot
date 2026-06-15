// FILE TU DONG SINH boi tools/gen_pages_embed.py - DUNG SUA TAY.
// Nhung manifest + template PNG vao binary (.exe doc lap).

pub const MANIFEST: &str = include_str!(
    concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/manifest.json"));

const T0: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_area_boss.png"));
const T1: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_awake_zones.png"));
const T2: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_collection.png"));
const T3: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_daily.png"));
const T4: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_delegation.png"));
const T5: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_demon_encounter.png"));
const T6: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_demon_encounter_realworld.png"));
const T7: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_draft_duel.png"));
const T8: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_duel.png"));
const T9: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_exploration.png"));
const T10: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_friends.png"));
const T11: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_goryou_realm.png"));
const T12: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_guild.png"));
const T13: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_heian_kitan.png"));
const T14: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_hero_test.png"));
const T15: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_hunt.png"));
const T16: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_hunt_kirin.png"));
const T17: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_hyakkisen.png"));
const T18: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_hyakkiyakou.png"));
const T19: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_kekkai_toppa.png"));
const T20: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_login.png"));
const T21: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_main.png"));
const T22: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_onmyodo.png"));
const T23: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_realm_raid.png"));
const T24: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_secret_zones.png"));
const T25: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_shikigami_records.png"));
const T26: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_six_gates.png"));
const T27: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_soul_zones.png"));
const T28: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_summon.png"));
const T29: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_team.png"));
const T30: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_town.png"));
const T31: &[u8] = include_bytes!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../assets/pages/page_travel.png"));

pub fn template_bytes(name: &str) -> Option<&'static [u8]> {
    match name {
        "page_area_boss.png" => Some(T0),
        "page_awake_zones.png" => Some(T1),
        "page_collection.png" => Some(T2),
        "page_daily.png" => Some(T3),
        "page_delegation.png" => Some(T4),
        "page_demon_encounter.png" => Some(T5),
        "page_demon_encounter_realworld.png" => Some(T6),
        "page_draft_duel.png" => Some(T7),
        "page_duel.png" => Some(T8),
        "page_exploration.png" => Some(T9),
        "page_friends.png" => Some(T10),
        "page_goryou_realm.png" => Some(T11),
        "page_guild.png" => Some(T12),
        "page_heian_kitan.png" => Some(T13),
        "page_hero_test.png" => Some(T14),
        "page_hunt.png" => Some(T15),
        "page_hunt_kirin.png" => Some(T16),
        "page_hyakkisen.png" => Some(T17),
        "page_hyakkiyakou.png" => Some(T18),
        "page_kekkai_toppa.png" => Some(T19),
        "page_login.png" => Some(T20),
        "page_main.png" => Some(T21),
        "page_onmyodo.png" => Some(T22),
        "page_realm_raid.png" => Some(T23),
        "page_secret_zones.png" => Some(T24),
        "page_shikigami_records.png" => Some(T25),
        "page_six_gates.png" => Some(T26),
        "page_soul_zones.png" => Some(T27),
        "page_summon.png" => Some(T28),
        "page_team.png" => Some(T29),
        "page_town.png" => Some(T30),
        "page_travel.png" => Some(T31),
        _ => None,
    }
}
