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

# --- RENK VE STİL AYARLARI ---
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
        ws_gecmis.append_row(["Gecmis_ID", "Basvuru_ID", "Islem", "Detay", "Tarih"])
    return ws_basvuru, ws_gecmis

# --- CRUD İŞLEMLERİ ---
def veri_ekle(ws_b, ws_g, sirket, pozisyon, durum, notlar):
    tarih = datetime.now().strftime("%d-%m-%Y %H:%M")
    basvuru_id = str(uuid.uuid4())[:8]
    gecmis_id = str(uuid.uuid4())[:8]
    
    ws_b.append_row([basvuru_id, sirket, pozisyon, durum, tarih, notlar])
    ws_g.append_row([gecmis_id, basvuru_id, "YENİ KAYIT", f"Durum: {durum}", tarih])

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
        
        gecmis_id = str(uuid.uuid4())[:8]
        if eski_durum != durum:
            ws_g.append_row([gecmis_id, id, "GÜNCELLEME", f"{eski_durum} -> {durum}", tarih])
        elif notlar:
            ws_g.append_row([gecmis_id, id, "NOT GÜNCELLEME", f"Not: {notlar}", tarih])
    except Exception as e:
        st.error(f"Güncelleme hatası: {e}")

def veri_sil(ws_b, ws_g, id):
    try:
        cell = ws_b.find(id)
        ws_b.delete_rows(cell.row)
    except: pass

def gecmis_tekil_sil(ws_g, gecmis_id):
    try:
        cell = ws_g.find(gecmis_id)
        ws_g.delete_rows(cell.row)
    except Exception as e:
        st.error(f"Silme hatası: {e}")

# --- UYGULAMA BAŞLANGICI ---
sheet = baglanti_kur()
ws_basvuru, ws_gecmis = sayfalari_hazirla(sheet)

st.title("🚀 Kariyer Takip Merkezi")

# --- VERİLERİ ÇEK ---
data_b = ws_basvuru.get_all_records()
df = pd.DataFrame(data_b)

data_g = ws_gecmis.get_all_records()
df_gecmis = pd.DataFrame(data_g)

# Veri Tipi Düzeltmeleri
if not df.empty:
    if 'ID' in df.columns: df['ID'] = df['ID'].astype(str)
    if 'Tarih' in df.columns: df['Tarih_Obj'] = pd.to_datetime(df['Tarih'], format="%d-%m-%Y %H:%M", errors='coerce')

if not df_gecmis.empty:
    if 'Basvuru_ID' in df_gecmis.columns: df_gecmis['Basvuru_ID'] = df_gecmis['Basvuru_ID'].astype(str)
    if 'Gecmis_ID' in df_gecmis.columns: df_gecmis['Gecmis_ID'] = df_gecmis['Gecmis_ID'].astype(str)

# --- SEKMELER ---
tab_goruntule, tab_duzenle, tab_analiz = st.tabs(["👀 Görüntüle & Geçmiş", "✏️ Düzenle & Yönet", "📊 Analiz"])

# ==========================================
# TAB 1: GÖRÜNTÜLEME (DETAYLI GEÇMİŞLİ)
# ==========================================
with tab_goruntule:
    st.markdown("### 🗂️ Başvuru Arşivi")
    st.caption("Başvuru detaylarını ve tarihçesini görmek için satırlara tıklayın.")
    
    if df.empty:
        st.info("Henüz veri yok.")
    else:
        # Filtreleme Alanı
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtre_durum = st.multiselect("Duruma Göre Filtrele", df['Durum'].unique(), key="view_filter")
        with col_f2:
            filtre_ara = st.text_input("Hızlı Arama (Şirket)", key="view_search")

        # Filtreleri Uygula
        df_view = df.copy()
        if filtre_durum:
            df_view = df_view[df_view['Durum'].isin(filtre_durum)]
        if filtre_ara:
            df_view = df_view[df_view['Sirket'].str.contains(filtre_ara, case=False)]

        st.divider()

        # Her satırı bir EXPANDER (Açılır Kutu) olarak listele
        for index, row in df_view.iterrows():
            row_id = str(row['ID'])
            durum = row['Durum']
            
            # İkon Belirle
            icon = "⚪"
            if durum == "Reddedildi": icon="🔴"
            elif durum == "Teklif Alındı": icon="🟢"
            elif durum == "Mülakat Bekleniyor": icon="🟠"
            elif durum == "Görüşüldü": icon="🟡"

            # Başlık
            baslik = f"{icon} **{row['Sirket']}** - {row['Pozisyon']}  |  *Durum: {durum}*"
            
            with st.expander(baslik):
                # İçerik Düzeni
                col_detay, col_tarihce = st.columns([1, 2])
                
                # SOL: Özet Bilgi
                with col_detay:
                    st.markdown("#### 📌 Özet")
                    st.write(f"**Tarih:** {row['Tarih']}")
                    st.info(f"**Not:** {row['Notlar']}")

                # SAĞ: Geçmiş Tablosu
                with col_tarihce:
                    st.markdown("#### 🕒 Süreç Geçmişi")
                    if not df_gecmis.empty:
                        bu_gecmis = df_gecmis[df_gecmis['Basvuru_ID'] == row_id].sort_values(by='Tarih', ascending=False)
                        if not bu_gecmis.empty:
                            # Sadece okuma amaçlı temiz bir tablo göster
                            st.dataframe(
                                bu_gecmis[['Tarih', 'Islem', 'Detay']], 
                                hide_index=True,
                                use_container_width=True
                            )
                        else:
                            st.caption("Geçmiş kaydı yok.")
                    else:
                        st.caption("Geçmiş verisi yok.")

# ==========================================
# TAB 2: DÜZENLEME & KARTLAR
# ==========================================
with tab_duzenle:
    col_form, col_list = st.columns([1, 2])

    # SOL PANEL (EKLEME)
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

    # SAĞ PANEL (KARTLAR)
    with col_list:
        st.subheader("Düzenle & Yönet")
        if df.empty:
            st.info("Kayıt bulunamadı.")
        else:
            arama_edit = st.text_input("Düzenlenecek Şirketi Ara", key="edit_search")
            df_edit = df.copy()
            if arama_edit:
                df_edit = df_edit[df_edit['Sirket'].str.contains(arama_edit, case=False)]

            for index, row in df_edit.iterrows():
                row_id = str(row['ID'])
                durum = row['Durum']
                icon = "⚪"
                if durum == "Reddedildi": icon="🔴"
                elif durum == "Teklif Alındı": icon="🟢"
                elif durum == "Mülakat Bekleniyor": icon="🟠"
                elif durum == "Görüşüldü": icon="🟡"

                with st.expander(f"{icon} {row['Sirket']} - {row['Pozisyon']}"):
                    c_gecmis, c_guncelle = st.columns([3, 2])
                    
                    # SOL: GEÇMİŞ YÖNETİMİ
                    with c_gecmis:
                        st.markdown("##### 🕒 İşlem Geçmişi (Yönet)")
                        if not df_gecmis.empty:
                            bu_gecmis = df_gecmis[df_gecmis['Basvuru_ID'] == row_id].sort_values(by='Tarih', ascending=False)
                            if not bu_gecmis.empty:
                                for idx, h_row in bu_gecmis.iterrows():
                                    g_id = str(h_row['Gecmis_ID'])
                                    with st.container():
                                        gc1, gc2 = st.columns([4, 1])
                                        with gc1:
                                            st.markdown(f"**{h_row['Tarih']}** | *{h_row['Islem']}*")
                                            st.caption(f"{h_row['Detay']}")
                                        with gc2:
                                            with st.popover("Sil", use_container_width=True):
                                                st.write("Silinsin mi?")
                                                if st.button("Evet", key=f"gs_{g_id}"):
                                                    with st.spinner("Siliniyor..."):
                                                        gecmis_tekil_sil(ws_gecmis, g_id)
                                                    st.rerun()
                                        st.divider()
                            else:
                                st.info("Geçmiş yok.")
                        else:
                            st.info("Geçmiş verisi yok.")

                    # SAĞ: GÜNCELLEME
                    with c_guncelle:
                        st.markdown("##### ⚙️ Güncelleme")
                        idx = 0
                        secenekler = ["Başvuruldu", "Görüşüldü", "Mülakat Bekleniyor", "Teklif Alındı", "Reddedildi"]
                        if durum in secenekler: idx = secenekler.index(durum)
                        
                        y_durum = st.selectbox("Durum", secenekler, key=f"s_{row_id}", index=idx)
                        y_not = st.text_input("Not", value=row['Notlar'], key=f"n_{row_id}")
                        
                        cb1, cb2 = st.columns(2)
                        with cb1:
                            if st.button("💾 Kaydet", key=f"save_{row_id}"):
                                with st.spinner("..."):
                                    veri_guncelle(ws_basvuru, ws_gecmis, row_id, row['Sirket'], row['Pozisyon'], y_durum, y_not)
                                st.rerun()
                        with cb2:
                            with st.popover("🗑️ Sil", use_container_width=True):
                                st.error("Başvuru tamamen silinsin mi?")
                                if st.button("Evet, Sil", key=f"del_confirm_{row_id}", type="primary"):
                                    with st.spinner("..."):
                                        veri_sil(ws_basvuru, ws_gecmis, row_id)
                                    st.rerun()

# ==========================================
# TAB 3: ANALİZ
# ==========================================
with tab_analiz:
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
            
        if 'Tarih_Obj' in df.columns and pd.notnull(df['Tarih_Obj']).any():
            st.divider()
            df_sorted = df.sort_values(by='Tarih_Obj')
            fig_line = px.scatter(df_sorted, x='Tarih_Obj', y='Sirket', color='Durum', size_max=15, color_discrete_map=RENK_HARITASI)
            st.plotly_chart(fig_line, use_container_width=True)
