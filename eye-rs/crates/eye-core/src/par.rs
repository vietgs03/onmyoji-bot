//! par.rs - tien ich song song bang std thread (khong them crate).
//! Dung cho cac vong lap theo hang doc lap (median, vote, morph...).

use std::sync::OnceLock;

/// So core kha dung (cache 1 lan). Mac dinh 1 neu khong xac dinh duoc.
pub fn num_cpus() -> usize {
    static N: OnceLock<usize> = OnceLock::new();
    *N.get_or_init(|| {
        std::thread::available_parallelism()
            .map(|n| n.get())
            .unwrap_or(1)
    })
}

/// So luong (band) hop ly cho `work_rows` hang: khong vuot qua so core, va moi
/// band toi thieu MIN_ROWS hang de overhead spawn khong an het loi. Tra >=1.
pub fn nthreads(work_rows: usize) -> usize {
    const MIN_ROWS: usize = 24; // duoi nguong nay chay tuan tu cho re
    let by_rows = (work_rows / MIN_ROWS).max(1);
    by_rows.min(num_cpus()).max(1)
}

/// Nhu `nthreads` nhung gioi han them so band toi da `cap` (cho cac op co chi phi
/// merge ti le voi so band, vi du vote accumulator).
pub fn nthreads_capped(work_rows: usize, cap: usize) -> usize {
    nthreads(work_rows).min(cap.max(1))
}
