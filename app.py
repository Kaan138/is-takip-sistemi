import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import uuid
import os
import plotly.express as px # Grafik kütüphanesi

# --- AYARLAR ---
st.set_page_config(page_title="Kariyer Takip 360", layout="wide", page_icon="🚀")

# --- RENK AYARLARI (Burası Grafikleri Yönetir) ---
RENK_HARITASI = {
    "Teklif Alındı": "#2ECC71",      # Parlak Yeşil
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
    
    if creds is None: st.stop()
    client = gspread.authorize(creds)
    try: sheet = client.open("Is_Takip_Verileri")
    except: st.stop()
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

# --- CRUD FONKSİYONLARI ---
def veri_ekle(ws_b, ws_g, sirket, pozisyon, durum, notlar):
    tarih = datetime.now().strftime("%d-%m-%Y %H:%M")
    yeni_id = str(uuid.uuid4())[:8]
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
    except: pass

def veri_sil(ws_b, ws_g, id):
    try:
        cell = ws_b.find(id)
        ws_b.delete_rows(cell.row)
    except: pass

# --- ANA UYGULAMA ---
sheet = baglanti_kur()
ws_basvuru, ws_gecmis = sayfalari_hazirla(sheet)

st.title("🚀 Kariyer Takip Merkezi")

# Verileri Çek
data = ws_basvuru.get_all_records()
df = pd.DataFrame(data)
if not df.empty and 'ID' in df.columns:
    df['ID'] = df['ID'].astype(str)
    # Tarih formatını datetime objesine çevir (Analiz için gerekli)
    df['Tarih_Obj'] = pd.to_datetime(df['Tarih'], format="%d-%m-%Y %H:%M", errors='coerce')

# --- SEKMELER ---
tab1, tab2 = st.tabs(["📋 Başvurular & İşlemler", "📊 Analiz & Dashboard"])

# --- TAB 1: LİSTE VE İŞLEMLER ---
with tab1:
    col_form, col_list = st.columns([1, 2])

    # SOL PANEL: Yeni Ekleme ve Filtreler
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
                    st.success("Eklendi!")
                    st.rerun()
                else:
                    st.error("Şirket/Pozisyon giriniz.")
        
        st.divider()
        st.subheader("🔍 Filtrele")
        if not df.empty:
            # Mevcut durumları al
            mevcut_durumlar = df['Durum'].unique()
            secilen_durumlar = st.multiselect("Duruma Göre Filtrele", mevcut_durumlar)
            arama_terimi = st.text_input("Şirket Ara")

    # SAĞ PANEL: Liste
    with col_list:
        if df.empty:
            st.info("Henüz kayıt yok.")
        else:
            # Filtreleme Mantığı
            df_goster = df.copy()
            if secilen_durumlar:
                df_goster = df_goster[df_goster['Durum'].isin(secilen_durumlar)]
            if arama_terimi:
                df_goster = df_goster[df_goster['Sirket'].str.contains(arama_terimi, case=False)]

            st.write(f"**Gösterilen Kayıt:** {len(df_goster)}")

            for index, row in df_goster.iterrows():
                # Renk ve İkon Ayarı
                durum = row['Durum']
                icon = "⚪"
                
                if durum == "Reddedildi": icon="🔴"
                elif durum == "Teklif Alındı": icon="🟢"
                elif durum == "Mülakat Bekleniyor": icon="🟠"
                elif durum == "Görüşüldü": icon="🟡"

                # Ghosting Dedektörü (14 Gündür ses yoksa uyar)
                uyari = ""
                if pd.notnull(row['Tarih_Obj']):
                    gecen_gun = (datetime.now() - row['Tarih_Obj']).days
                    if gecen_gun > 14 and durum == "Başvuruldu":
                        uyari = "⚠️ **(14+ gün)**"

                with st.expander(f"{icon} {row['Sirket']} - {row['Pozisyon']} {uyari}"):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.caption(f"Son Güncelleme: {row['Tarih']}")
                        if uyari: st.warning("Bu başvuruya uzun süredir güncelleme gelmedi.")
                        st.info(f"Not: {row['Notlar']}")
                    
                    with c2:
                        y_durum = st.selectbox("Güncelle", ["Başvuruldu", "Görüşüldü", "Mülakat Bekleniyor", "Teklif Alındı", "Reddedildi"], key=f"s_{row['ID']}", index=["Başvuruldu", "Görüşüldü", "Mülakat Bekleniyor", "Teklif Alındı", "Reddedildi"].index(durum) if durum in ["Başvuruldu", "Görüşüldü", "Mülakat Bekleniyor", "Teklif Alındı", "Reddedildi"] else 0)
                        y_not = st.text_input("Not", value=row['Notlar'], key=f"n_{row['ID']}")
                        if st.button("Kaydet", key=f"b_{row['ID']}"):
                             with st.spinner("..."):
                                veri_guncelle(ws_basvuru, ws_gecmis, row['ID'], row['Sirket'], row['Pozisyon'], y_durum, y_not)
                             st.rerun()
                        if st.button("Sil", key=f"del_{row['ID']}", type="primary"):
                             with st.spinner("..."):
                                veri_sil(ws_basvuru, ws_gecmis, row['ID'])
                             st.rerun()

# --- TAB 2: ANALİZ ---
with tab2:
    if df.empty:
        st.info("Analiz için veri gerekli.")
    else:
        st.subheader("📊 Başvuru Analizleri")
        
        col_grafik1, col_grafik2 = st.columns(2)
        
        with col_grafik1:
            # 1. Durum Dağılımı (Pasta Grafiği) - RENKLİ
            st.write("**Başvuru Durumları**")
            
            # Pasta Grafiği (Renk Haritasını Burada Kullanıyoruz)
            fig_pie = px.pie(df, names='Durum', hole=0.4, 
                             color='Durum',
                             color_discrete_map=RENK_HARITASI)
            
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col_grafik2:
            # 2. Şirket Bazlı Başvurular
            st.write("**Şirketlere Göre Yoğunluk**")
            sirket_counts = df['Sirket'].value_counts().reset_index()
            sirket_counts.columns = ['Sirket', 'Adet']
            fig_bar = px.bar(sirket_counts, x='Sirket', y='Adet')
            st.plotly_chart(fig_bar, use_container_width=True)

        st.divider()
        
        # 3. Zaman Çizelgesi (Timeline) - RENKLİ
        if 'Tarih_Obj' in df.columns and pd.notnull(df['Tarih_Obj']).any():
            st.write("**Zaman İçinde Başvurular**")
            df_sorted = df.sort_values(by='Tarih_Obj')
            
            # Scatter Grafiği (Renk Haritasını Burada da Kullanıyoruz)
            fig_line = px.scatter(df_sorted, x='Tarih_Obj', y='Sirket', 
                                  color='Durum', 
                                  size_max=15,
                                  color_discrete_map=RENK_HARITASI,
                                  title="Tarihsel Süreç")
            
            st.plotly_chart(fig_line, use_container_width=True)
