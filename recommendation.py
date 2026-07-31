import mysql.connector
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# =========================
# TOKEN MAPS
# =========================

# Token TF-IDF per tipe harga
HARGA_TOKEN = {
    "murah":    "harga_murah",
    "menengah": "harga_menengah",
    "mahal":    "harga_mahal",
}

# Nilai kisaran_harga di DB yang termasuk tiap tipe
HARGA_DB_VALUES = {
    "murah":    ["10.000 - 25.000"],
    "menengah": ["25.000 - 50.000"],
    "mahal":    ["50.000 - 75.000", "75.000 - 100.000"],
}

AREA_TOKEN = {
    "bekasi utara":   "area_bekasi_utara",
    "bekasi selatan": "area_bekasi_selatan",
    "bekasi timur":   "area_bekasi_timur",
    "bekasi barat":   "area_bekasi_barat",
}

FASILITAS_TOKEN = {
    "wifi":         "wifi",
    "ac":           "ac",
    "outdoor":      "outdoor",
    "semi_outdoor": "semi outdoor",
    "mushola":      "mushola",
    "live_music":   "live music",
}

# =========================
# LIKERT THRESHOLD
# =========================

LIKERT_SCALE = [
    (81.0, 100.0, "Sangat Kuat (Sangat Sesuai)"),
    (61.0, 80.0,  "Kuat (Sesuai)"),
    (41.0, 60.0,  "Cukup"),
    (21.0, 40.0,  "Lemah (Kurang Sesuai)"),
    (0.0,  20.0,  "Sangat Lemah (Tidak Sesuai)"),
]


def _kategori_kecocokan(persen: float) -> str:
    """Petakan skor similarity (0-100) ke kategori kualitatif standar."""
    for low, high, label in LIKERT_SCALE:
        if low <= persen <= high:
            return label
    return "Sangat Lemah (Tidak Sesuai)"


def _rating_token(r: float) -> str:
    return "rating_tinggi" if r >= 4.5 else "rating_bagus"


def _norm_harga(h) -> str:
    if pd.isna(h):
        return ""
    return str(h).lower().replace("rp", "").replace(" ", "").replace(".", "").strip()


def _has_fasilitas(fitur_cbf, token: str) -> bool:
    if fitur_cbf is None:
        return False
    doc_words = set(str(fitur_cbf).lower().split())
    return all(w in doc_words for w in token.lower().split())


def _count_fasilitas(fitur_cbf) -> int:
    count = 0
    for tok in FASILITAS_TOKEN.values():
        if _has_fasilitas(fitur_cbf, tok):
            count += 1
    return count


def _filter_harga(data: pd.DataFrame, harga_tipe: str) -> pd.DataFrame:
    db_values = HARGA_DB_VALUES.get(harga_tipe, [])
    if not db_values:
        return data
    norm_values = [_norm_harga(v) for v in db_values]
    return data[data["kisaran_harga"].apply(_norm_harga).isin(norm_values)]

def _harga_tipe_from_db(kisaran_harga: str):
    norm = _norm_harga(kisaran_harga)
    for tipe, db_values in HARGA_DB_VALUES.items():
        if norm in [_norm_harga(v) for v in db_values]:
            return tipe
    return None


def build_fitur_cbf(rating, kisaran_harga, area, fasilitas_keys):
    tokens = []

    try:
        tokens.append(_rating_token(float(rating)))
    except (TypeError, ValueError):
        print(f"[WARNING] rating '{rating}' tidak valid, token rating dilewati.")

    harga_tipe = _harga_tipe_from_db(kisaran_harga)
    if harga_tipe:
        tokens.append(HARGA_TOKEN[harga_tipe])
    else:
        print(f"[WARNING] kisaran_harga '{kisaran_harga}' tidak cocok HARGA_DB_VALUES manapun.")

    area_key   = str(area).strip().lower()
    area_token = AREA_TOKEN.get(area_key)
    if area_token:
        tokens.append(area_token)
    else:
        fallback = "area_" + area_key.replace(" ", "_")
        tokens.append(fallback)
        print(f"[WARNING] area '{area}' tidak ada di AREA_TOKEN, dipakai fallback '{fallback}'.")

    for key in fasilitas_keys:
        tokens.append(FASILITAS_TOKEN.get(key, key))

    return " ".join(tokens)

# =========================
# FUNGSI REKOMENDASI
# =========================

def get_recommendations(rating="", area="", harga="", fasilitas="", top_n=5):
    try:
        # 1. Ambil data
        db = mysql.connector.connect(
            host="localhost", user="root", password="", database="coffeeshop_project"
        )
        df = pd.read_sql(
            "SELECT *, ROUND(rating, 1) AS rating_rounded FROM coffeeshops", db
        )
        db.close()

        if df.empty:
            return []

        # --- Jaminan kolom wajib selalu ada, agar tidak pernah KeyError ---
        if "fitur_cbf" not in df.columns:
            print("[WARNING] Kolom 'fitur_cbf' tidak ditemukan di tabel coffeeshops. "
                  "Pastikan kolom ini sudah dibuat (ALTER TABLE coffeeshops ADD COLUMN fitur_cbf TEXT).")
            df["fitur_cbf"] = ""
        if "kisaran_harga" not in df.columns:
            print("[WARNING] Kolom 'kisaran_harga' tidak ditemukan di tabel coffeeshops.")
            df["kisaran_harga"] = ""
        if "area" not in df.columns:
            print("[WARNING] Kolom 'area' tidak ditemukan di tabel coffeeshops.")
            df["area"] = ""

        df["fitur_cbf"]     = df["fitur_cbf"].fillna("").astype(str)
        df["kisaran_harga"] = df["kisaran_harga"].fillna("").astype(str)
        df["area"]          = df["area"].fillna("").astype(str)

        # 2. Parse preferensi aktif
        rating_val = None
        area_val   = None
        harga_tipe = None   # "murah" / "menengah" / "mahal"
        fasil_list = []

        _r = str(rating).strip()
        if _r not in ("", "Semua", "4.0"):
            try:
                rating_val = round(float(_r), 1)
            except ValueError:
                pass

        _a = str(area).strip()
        if _a not in ("", "Semua"):
            area_val = _a.lower()

        # Form mengirim "murah" / "menengah" / "mahal" / "Semua"
        _h = str(harga).strip().lower()
        if _h in ("murah", "menengah", "mahal"):
            harga_tipe = _h

        _f = str(fasilitas).strip()
        if _f:
            for tok_html in _f.split():
                tok_db = FASILITAS_TOKEN.get(tok_html)
                if tok_db:
                    fasil_list.append(tok_db)

        # 4. Filter rating: EXACT MATCH
        if rating_val is not None:
            filtered = df[df["rating_rounded"] == rating_val].copy()
        else:
            filtered = df.copy()

        if filtered.empty:
            return []

        filtered["jumlah_fasilitas"] = filtered["fitur_cbf"].apply(_count_fasilitas)

        # 5. Filter tambahan: area, harga, fasilitas
        def _apply_extra(data, use_a=True, use_h=True, use_f=True):
            f = data.copy()
            if use_a and area_val is not None:
                f = f[f["area"].str.strip().str.lower() == area_val]
            if use_h and harga_tipe is not None:
                f = _filter_harga(f, harga_tipe)
            if use_f and fasil_list:
                for tok_db in fasil_list:
                    f = f[f["fitur_cbf"].apply(lambda x: _has_fasilitas(x, tok_db))]
            return f

        pool = _apply_extra(filtered)

        if pool.empty:
            return []

        # 6. Bangun query TF-IDF
        parts = []
        if area_val:
            t = AREA_TOKEN.get(area_val, "")
            if t: parts.append(t)
        if harga_tipe:
            t = HARGA_TOKEN.get(harga_tipe, "")
            if t: parts.append(t)
        if rating_val is not None:
            parts.append(_rating_token(rating_val))
        if fasil_list:
            parts.append(" ".join(fasil_list))

        # 7. Hitung similarity 
        if parts:
            user_query = " ".join(parts)
            tfidf      = TfidfVectorizer(min_df=1)

            # Jaga-jaga: kalau semua fitur_cbf kosong, TfidfVectorizer akan
            # error ("empty vocabulary"). Tangani dengan fallback skor 0.
            try:
                all_matrix = tfidf.fit_transform(df["fitur_cbf"])
                user_vec   = tfidf.transform([user_query])

                idx      = pool.index.tolist()
                raw_sims = cosine_similarity(user_vec, all_matrix[idx])[0]
            except ValueError:
                raw_sims = np.zeros(len(pool))

            pool = pool.copy()
            pool["similarity"] = np.round(raw_sims * 100, 1)

        else:
            # Tidak ada preferensi aktif sama sekali → tidak ada query untuk
            # dibandingkan, similarity tidak terdefinisi secara CBF (0).
            pool = pool.copy()
            pool["similarity"] = 0.0

        # 7b. Kategorisasi kualitatif (label interpretasi, lihat LIKERT_SCALE)
        pool["kategori_kecocokan"] = pool["similarity"].apply(_kategori_kecocokan)

        # 8. Sort: similarity DESC → rating DESC → jumlah_fasilitas DESC → nama ASC
        hasil = (
            pool
            .sort_values(
                by=["similarity", "rating_rounded", "jumlah_fasilitas", "nama"],
                ascending=[False, False, False, True]
            )
            .head(top_n)
            .copy()
        )

        return hasil.to_dict(orient="records")

    except Exception as e:

        import traceback
        print("[ERROR get_recommendations]:", e)
        traceback.print_exc()
        return []