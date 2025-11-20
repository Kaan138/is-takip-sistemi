import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import uuid
import os
import plotly.express as px

# --- AYARLAR ---
st.set_page_config(page_title="Kariyer Takip 360", layout="wide", page_icon="🚀")

# --- RENK AYARLARI ---
RENK_HARITASI = {
    "Teklif Alındı": "#2ECC71",      # Yeşil
    "Reddedildi": "#E74C3C",         # Kırmızı
    "Mülakat Bekleniyor": "#F39C12", # Turuncu
    "Görüşüldü": "#F1C40F",          # Sarı
    "Başvuruldu": "#3498DB",         # Mavi
    "Bilinmiyor": "#95A5A6"          # Gri
}

# --- BAĞLANTILAR ---
def baglanti_kur():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = None
    if os.path.exists("credentials.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    else:
        try:
            if "gcp_service_account" in st.secrets:
                creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        except: pass
    
    if creds is None: st.error("Bağlantı hatası: Kimlik dosyası yok."); st.stop()
    client = gspread.authorize(creds)
    try: sheet = client.open("Is_Takip_Verileri")
    except: st.error("Google Sheet 'Is_Takip_Verileri' bulunamadı."); st.stop()
    return sheet

def sayfalari_hazirla(sheet):
    try: ws_basvuru = sheet.worksheet("Basvurular")
    except:
        ws_basvuru = sheet.add_worksheet(title="Basvurular", rows="100", cols="20")
        ws_basvuru.append_row(["ID", "Sirket", "Pozisyon", "Durum", "Tarih", "Notlar"])
    try: ws_gecmis = sheet.worksheet("Gecmis")
    except:
        ws_gecmis = sheet.add_worksheet(title="Gecmis", rows="100", cols="20")
        ws_gecmis.append_row(["Basvuru_ID", "Islem", "Detay", "Tarih"])
    return ws_basvuru, ws_gecmis

# --- CRUD İŞLEMLERİ ---
def veri_ekle(ws_b, ws_g, sirket, pozisyon, durum, notlar):
    tarih = datetime.now().strftime("%d-%m-%Y %H:%M")
    yeni_id = str(uuid.uuid4())[:8]
    # ID'yi string olarak kaydetmek için başına tırnak koymuyoruz ama okurken dikkat edeceğiz
    ws_b.append_row([yeni_id, sirket, pozisyon, durum, tarih, notlar])
    ws_g.append_row([yeni_id, "YENİ KAYIT", f"Durum: {durum}", tarih])

def veri_guncelle(ws_b, ws_g, id, sirket, pozisyon, durum, notlar):
    tarih = datetime.now().strftime("%d-%m-%Y %H:%M")
    try:
        cell = ws_b.find(id)
        row = cell.row
        eski_durum = ws_b.cell(row, 4).value
        ws_b.update_cell(row, 2, sirket)
        ws_b.update_cell(row, 3, pozisyon)
        ws_b.update_cell(row, 4, durum)
        ws_b.update_cell(row, 5, tarih)
        ws_b.update_cell(row, 6, notlar)
        
        if eski_durum != durum:
            ws_g.append_row([id, "GÜNCELLEME", f"{eski_durum} -> {durum}", tarih])
        elif notlar:
            ws_g.append_row([id, "NOT GÜNCELLEME", f"Not: {notlar}", tarih])
    except Exception as e:
        st.error(f"Güncelleme hatası: {e}")

def veri_sil(ws_b, ws_g, id):
    try:
        cell = ws_b.find(id)
        ws_b.delete_rows(cell.row)
    except: pass

# --- UYGULAMA BAŞLANGICI ---
sheet = baglanti_kur()
ws_basvuru, ws_gecmis = sayfalari_hazirla(sheet)

st.title("🚀 Kariyer Takip Merkezi")

# --- GÜVENLİ VERİ ÇEKME ---
# Başvuruları Çek
data_b = ws_basvuru.get_all_records()
df = pd.DataFrame(data_b)

# Geçmişi Çek
data_g = ws_gecmis.get_all_records()
df_gecmis = pd.DataFrame(data_g)

# Veri Tipi Düzeltmeleri (CRITICAL FIX)
if not df.empty:
    # ID sütunu varsa hepsini metne (string) çevir
    if 'ID' in df.columns:
        df['ID'] = df['ID'].astype(str)
    if 'Tarih' in df.columns:
        df['Tarih_Obj'] = pd.to_datetime(df['Tarih'], format="%d-%m-%Y %H:%M", errors='coerce')

if not df_gecmis.empty:
    # Başvuru ID sütunu varsa hepsini metne çevir
    if 'Basvuru_ID' in df_gecmis.columns:
        df_gecmis['Basvuru_ID'] = df_gecmis['Basvuru_ID'].astype(str)

# --- SEKMELER ---
tab1, tab2 = st.tabs(["📋 Başvurular & İşlemler", "📊 Analiz & Dashboard"])

# --- TAB 1: LİSTE ---
with tab1:
    col_form, col_list = st.columns([1, 2])

    # SOL PANEL
    with col_form:
        st.subheader("Yeni Ekle")
        with st.form("ekle_form", clear_on_submit=True):
            s_sirket = st.text_input("Şirket")
            s_pozisyon = st.text_input("Pozisyon")
            s_durum = st.selectbox("Durum", ["Başvuruldu", "Görüşüldü", "Mülakat Bekleniyor", "Teklif Alındı", "Reddedildi"])
            s_not = st.text_area("Not")
            if st.form_submit_button("Kaydet"):
                if s_sirket and s_pozisyon:
                    with st.spinner("Kaydediliyor..."):
                        veri_ekle(ws_basvuru, ws_gecmis, s_sirket, s_pozisyon, s_durum, s_not)
                    st.rerun()
                else:
                    st.error("Eksik bilgi.")
        
        st.divider()
        st.subheader("🔍 Filtrele")
        secilen_durumlar = []
        arama_terimi = ""
        if not df.empty:
            secilen_durumlar = st.multiselect("Durum Seç", df['Durum'].unique())
            arama_terimi = st.text_input("Şirket Ara")

    # SAĞ PANEL
    with col_list:
        if df.empty:
            st.info("Kayıt bulunamadı.")
        else:
            df_goster = df.copy()
            if secilen_durumlar:
                df_goster = df_goster[df_goster['Durum'].isin(secilen_durumlar)]
            if arama_terimi:
                df_goster = df_goster[df_goster['Sirket'].str.contains(arama_terimi, case=False)]

            st.write(f"**Kayıt Sayısı:** {len(df_goster)}")

            for index, row in df_goster.iterrows():
                # Güvenli veri okuma
                row_id = str(row['ID'])
                durum = row['Durum']
                
                icon = "⚪"
                if durum == "Reddedildi": icon="🔴"
                elif durum == "Teklif Alındı": icon="🟢"
                elif durum == "Mülakat Bekleniyor": icon="🟠"
                elif durum == "Görüşüldü": icon="🟡"

                # Expander
                with st.expander(f"{icon} {row['Sirket']} - {row['Pozisyon']}"):
                    # İki sütuna böl: Sol (Geçmiş), Sağ (Güncelleme)
                    c_gecmis, c_guncelle = st.columns([1, 1])
                    
                    # --- SOL: GEÇMİŞ ---
                    with c_gecmis:
                        st.markdown("##### 🕒 İşlem Geçmişi")
                        
                        # Geçmiş verisi var mı kontrol et
                        gecmis_var = False
                        if not df_gecmis.empty:
                            # ID eşleşmesi yap
                            bu_gecmis = df_gecmis[df_gecmis['Basvuru_ID'] == row_id]
                            
                            if not bu_gecmis.empty:
                                gecmis_var = True
                                # Tabloyu temizle ve göster
                                st.dataframe(
                                    bu_gecmis[['Tarih', 'Islem', 'Detay']].sort_index(ascending=False),
                                    hide_index=True,
                                    use_container_width=True
                                )
                        
                        if not gecmis_var:
                            st.info("Henüz geçmiş kaydı yok.")
                            
                        st.markdown("---")
                        st.caption(f"Güncel Not: {row['Notlar']}")

                    # --- SAĞ: GÜNCELLEME ---
                    with c_guncelle:
                        st.markdown("##### ⚙️ Güncelleme")
                        
                        secenekler = ["Başvuruldu", "Görüşüldü", "Mülakat Bekleniyor", "Teklif Alındı", "Reddedildi"]
                        idx = 0
                        if durum in secenekler:
                            idx = secenekler.index(durum)
                            
                        y_durum = st.selectbox("Yeni Durum", secenekler, key=f"s_{row_id}", index=idx)
                        y_not = st.text_input("Not Güncelle", value=row['Notlar'], key=f"n_{row_id}")
                        
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button("💾 Kaydet", key=f"save_{row_id}"):
                                with st.spinner("..."):
                                    veri_guncelle(ws_basvuru, ws_gecmis, row_id, row['Sirket'], row['Pozisyon'], y_durum, y_not)
                                st.rerun()
                        with col_btn2:
                            if st.button("🗑️ Sil", key=f"del_{row_id}", type="primary"):
                                with st.spinner("..."):
                                    veri_sil(ws_basvuru, ws_gecmis, row_id)
                                st.rerun()

# --- TAB 2: ANALİZ ---
with tab2:
    if df.empty:
        st.info("Analiz için veri gerekli.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Durum Dağılımı")
            fig = px.pie(df, names='Durum', hole=0.4, color='Durum', color_discrete_map=RENK_HARITASI)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader("Şirket Yoğunluğu")
            df_count = df['Sirket'].value_counts().reset_index()
            df_count.columns = ['Sirket', 'Adet']
            fig2 = px.bar(df_count, x='Sirket', y='Adet')
            st.plotly_chart(fig2, use_container_width=True)
