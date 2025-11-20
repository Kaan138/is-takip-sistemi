import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import uuid

# --- AYARLAR ---
st.set_page_config(page_title="Bulut İş Takip", layout="wide", page_icon="☁️")


# --- GOOGLE SHEETS BAĞLANTISI ---
# Streamlit Cloud'da "Secrets", Yerelde "credentials.json" kullanılır
def baglanti_kur():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # Eğer Streamlit Cloud üzerindeysek Secrets'tan oku
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Yerel bilgisayarda credentials.json dosyasından oku
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        except:
            st.error("credentials.json dosyası bulunamadı!")
            st.stop()

    client = gspread.authorize(creds)

    # Tabloyu Aç (Adı tam olarak 'Is_Takip_Verileri' olmalı)
    try:
        sheet = client.open("Is_Takip_Verileri")
        return sheet
    except:
        st.error(
            "Google Sheet dosyası bulunamadı. Lütfen adının 'Is_Takip_Verileri' olduğundan ve bot maili ile paylaşıldığından emin olun.")
        st.stop()


# --- YARDIMCI FONKSİYONLAR ---
def sayfalari_hazirla(sheet):
    # Başvurular sayfası var mı kontrol et, yoksa oluştur
    try:
        ws_basvuru = sheet.worksheet("Basvurular")
    except:
        ws_basvuru = sheet.add_worksheet(title="Basvurular", rows="100", cols="20")
        ws_basvuru.append_row(["ID", "Sirket", "Pozisyon", "Durum", "Tarih", "Notlar"])  # Başlıklar

    # Geçmiş sayfası var mı kontrol et
    try:
        ws_gecmis = sheet.worksheet("Gecmis")
    except:
        ws_gecmis = sheet.add_worksheet(title="Gecmis", rows="100", cols="20")
        ws_gecmis.append_row(["Basvuru_ID", "Islem", "Detay", "Tarih"])  # Başlıklar

    return ws_basvuru, ws_gecmis


def veri_ekle(ws_b, ws_g, sirket, pozisyon, durum, notlar):
    tarih = datetime.now().strftime("%d-%m-%Y %H:%M")
    yeni_id = str(uuid.uuid4())[:8]  # Benzersiz ID oluştur

    # Başvurulara ekle
    ws_b.append_row([yeni_id, sirket, pozisyon, durum, tarih, notlar])

    # Geçmişe ekle
    ws_g.append_row([yeni_id, "YENİ KAYIT", f"Durum: {durum}", tarih])


def veri_guncelle(ws_b, ws_g, id, sirket, pozisyon, durum, notlar):
    tarih = datetime.now().strftime("%d-%m-%Y %H:%M")

    # ID'nin olduğu satırı bul
    cell = ws_b.find(id)
    row_num = cell.row

    # Eski durumu al (karşılaştırma için - 4. sütun)
    eski_durum = ws_b.cell(row_num, 4).value

    # Satırı güncelle
    ws_b.update_cell(row_num, 2, sirket)
    ws_b.update_cell(row_num, 3, pozisyon)
    ws_b.update_cell(row_num, 4, durum)
    ws_b.update_cell(row_num, 5, tarih)
    ws_b.update_cell(row_num, 6, notlar)

    # Değişikliği geçmişe işle
    if eski_durum != durum:
        ws_g.append_row([id, "GÜNCELLEME", f"{eski_durum} -> {durum}", tarih])
    elif notlar:
        ws_g.append_row([id, "NOT GÜNCELLEME", f"Not: {notlar}", tarih])


def veri_sil(ws_b, ws_g, id):
    # ID'nin olduğu satırı bul ve sil
    try:
        cell = ws_b.find(id)
        ws_b.delete_rows(cell.row)
        # Not: Geçmiş kayıtları silinmiyor, arşiv olarak kalıyor.
    except:
        st.error("Silinirken hata oluştu.")


# --- ARAYÜZ ---
sheet = baglanti_kur()
ws_basvuru, ws_gecmis = sayfalari_hazirla(sheet)

st.title("☁️ Bulut Tabanlı İş Takip")

# Sidebar - Ekleme
with st.sidebar:
    st.header("Yeni Başvuru")
    s_sirket = st.text_input("Şirket Adı")
    s_pozisyon = st.text_input("Pozisyon")
    s_durum = st.selectbox("Durum", ["Başvuruldu", "Görüşüldü", "Mülakat Bekleniyor", "Teklif Alındı", "Reddedildi"])
    s_not = st.text_area("Notlar")

    if st.button("Kaydet", type="primary"):
        if s_sirket and s_pozisyon:
            with st.spinner("Google Sheets'e kaydediliyor..."):
                veri_ekle(ws_basvuru, ws_gecmis, s_sirket, s_pozisyon, s_durum, s_not)
            st.success("Kaydedildi!")
            st.rerun()
        else:
            st.warning("Şirket ve Pozisyon zorunludur.")

# Verileri Çek
data = ws_basvuru.get_all_records()
df = pd.DataFrame(data)

if not df.empty:
    # İstatistikler
    col1, col2, col3 = st.columns(3)
    col1.metric("Toplam Başvuru", len(df))
    col2.metric("Mülakat Bekleyen", len(df[df['Durum'] == 'Mülakat Bekleniyor']))
    col3.metric("Teklifler", len(df[df['Durum'] == 'Teklif Alındı']))
    st.divider()

    # Listeleme
    # DataFrame ID'leri string olarak algılasın diye
    df['ID'] = df['ID'].astype(str)

    for index, row in df.iterrows():
        icon = "⚪"
        if row['Durum'] == "Reddedildi":
            icon = "🔴"
        elif row['Durum'] == "Teklif Alındı":
            icon = "🟢"
        elif row['Durum'] == "Mülakat Bekleniyor":
            icon = "🟠"

        with st.expander(f"{icon} **{row['Sirket']}** - {row['Pozisyon']} ({row['Durum']})"):
            col_info, col_action = st.columns([3, 2])

            with col_info:
                st.write(f"**Son İşlem:** {row['Tarih']}")
                st.info(f"**Not:** {row['Notlar']}")

                # Bu başvuruya ait geçmişi çek
                gecmis_data = ws_gecmis.get_all_records()
                gdf = pd.DataFrame(gecmis_data)
                if not gdf.empty:
                    gdf['Basvuru_ID'] = gdf['Basvuru_ID'].astype(str)
                    bu_gecmis = gdf[gdf['Basvuru_ID'] == row['ID']]
                    if not bu_gecmis.empty:
                        st.caption("Süreç Geçmişi")
                        st.dataframe(bu_gecmis[['Islem', 'Detay', 'Tarih']], hide_index=True)

            with col_action:
                st.write("### İşlemler")
                y_durum = st.selectbox("Durum",
                                       ["Başvuruldu", "Görüşüldü", "Mülakat Bekleniyor", "Teklif Alındı", "Reddedildi"],
                                       key=f"sel_{row['ID']}",
                                       index=["Başvuruldu", "Görüşüldü", "Mülakat Bekleniyor", "Teklif Alındı",
                                              "Reddedildi"].index(row['Durum']))
                y_not = st.text_input("Not Güncelle", value=row['Notlar'], key=f"not_{row['ID']}")

                if st.button("Güncelle", key=f"btn_up_{row['ID']}"):
                    with st.spinner("Güncelleniyor..."):
                        veri_guncelle(ws_basvuru, ws_gecmis, row['ID'], row['Sirket'], row['Pozisyon'], y_durum, y_not)
                    st.success("Güncellendi!")
                    st.rerun()

                if st.button("Sil", key=f"btn_del_{row['ID']}", type="primary"):
                    with st.spinner("Siliniyor..."):
                        veri_sil(ws_basvuru, ws_gecmis, row['ID'])
                    st.rerun()

else:
    st.info("Henüz hiç başvuru kaydı yok. Soldan ekleyebilirsiniz.")