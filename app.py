import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import uuid
import os
import plotly.express as px
from fpdf import FPDF

# --- AYARLAR ---
st.set_page_config(page_title="Kariyer Takip", layout="wide", page_icon="💼")

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
        ws_basvuru.append_row(["ID", "Sirket", "Pozisyon", "Durum", "Tarih", "Notlar", "Link"])
    
    try: ws_gecmis = sheet.worksheet("Gecmis")
    except:
        ws_gecmis = sheet.add_worksheet(title="Gecmis", rows="100", cols="20")
        ws_gecmis.append_row(["Gecmis_ID", "Basvuru_ID", "Islem", "Detay", "Tarih"])
    return ws_basvuru, ws_gecmis

# --- KARAKTER TEMİZLEME (CRITICAL FIX) ---
def clean_text(text):
    """Türkçe karakterleri ve emojileri PDF için temizler"""
    if text is None: return ""
    text = str(text)
    replacements = {
        'ş': 's', 'Ş': 'S', 'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G',
        'ü': 'u', 'Ü': 'U', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C',
        '…': '...', '“': '"', '”': '"', '’': "'", '‘': "'", '–': '-', '—': '-',
        '€': 'Euro', '₺': 'TL'
    }
    for tr, en in replacements.items():
        text = text.replace(tr, en)
    
    # Latin-1 dışında kalan her şeyi '?' yap (Çökme riskini sıfırlar)
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- MODERN BOX PDF MOTORU ---
class ModernBoxPDF(FPDF):
    def header(self):
        # Üst Şerit (Koyu Lacivert)
        self.set_fill_color(44, 62, 80)
        self.rect(0, 0, 210, 25, 'F')
        
        # Başlık
        self.set_font('Arial', 'B', 18)
        self.set_text_color(255, 255, 255)
        self.cell(0, 15, 'BASVURU SUREC RAPORU', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Sayfa {self.page_no()}', 0, 0, 'C')

def create_pdf(df, df_gecmis):
    pdf = ModernBoxPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)
    
    for index, row in df.iterrows():
        # Sayfa taşma kontrolü
        if pdf.get_y() > 240:
            pdf.add_page()

        sirket = clean_text(row['Sirket'])
        pozisyon = clean_text(row['Pozisyon'])
        durum = clean_text(row['Durum'])
        tarih = clean_text(row['Tarih'])
        notlar = clean_text(row['Notlar'])
        link = str(row.get('Link', ''))
        row_id = str(row['ID'])

        # --- KUTU BAŞLIĞI ---
        # Açık Mavi Arka Plan
        pdf.set_fill_color(235, 245, 251) 
        pdf.set_draw_color(180, 180, 180) # Gri Çerçeve
        pdf.set_line_width(0.1)
        
        pdf.set_font("Arial", "B", 12)
        pdf.set_text_color(41, 128, 185) # Mavi Yazı
        
        # Başlık Hücresi (Tam Çerçeve)
        header_txt = f"  {sirket.upper()}  /  {pozisyon}"
        pdf.cell(0, 10, header_txt, 1, 1, 'L', fill=True)
        
        # --- KUTU İÇERİĞİ ---
        # Yan Çizgiler (LR Borders)
        pdf.set_fill_color(255, 255, 255) # Beyaz zemin
        pdf.set_text_color(0, 0, 0) # Siyah yazı
        
        # Durum Satırı
        pdf.set_font("Arial", "B", 9)
        status_text = f"  DURUM: {durum}    |    TARIH: {tarih}"
        pdf.cell(0, 8, status_text, "LR", 1, 'L', fill=True)
        
        # Notlar (MultiCell)
        if notlar:
            pdf.set_font("Arial", "", 9)
            pdf.set_text_color(80, 80, 80)
            # Not başlığı
            pdf.cell(0, 5, "  Notlar:", "LR", 1, 'L', fill=True)
            pdf.set_font("Arial", "I", 9)
            # İçerik
            pdf.multi_cell(0, 5, f"  {notlar}", "LR", 'L', fill=True)
            
        # Link
        if link and len(link) > 5:
            pdf.set_font("Arial", "U", 9)
            pdf.set_text_color(0, 0, 255)
            pdf.cell(0, 6, "  Ilan Linki", "LR", 1, 'L', fill=True, link=link)
            pdf.set_text_color(0, 0, 0) # Rengi sıfırla

        # --- GEÇMİŞ BÖLÜMÜ ---
        if not df_gecmis.empty:
            bu_gecmis = df_gecmis[df_gecmis['Basvuru_ID'] == row_id].sort_values(by='Tarih', ascending=False)
            if not bu_gecmis.empty:
                # Ayırıcı Çizgi (Hücre içi)
                pdf.set_font("Arial", "B", 8)
                pdf.set_text_color(150, 150, 150)
                pdf.cell(0, 6, "  -----------------------------------------------------------------------------------", "LR", 1, 'C', fill=True)
                
                pdf.cell(0, 5, "  ISLEM GECMISI:", "LR", 1, 'L', fill=True)
                
                pdf.set_font("Arial", "", 8)
                pdf.set_text_color(100, 100, 100)
                for idx, h_row in bu_gecmis.iterrows():
                    h_log = f"  >> {clean_text(h_row['Tarih'])}: {clean_text(h_row['Detay'])}"
                    pdf.cell(0, 4, h_log, "LR", 1, 'L', fill=True)

        # --- KUTUYU KAPAT ---
        # Alt Çizgi (Top border of an empty cell)
        pdf.cell(0, 0, "", "T", 1, 'L')
        
        # Boşluk
        pdf.ln(6)
        
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- CRUD İŞLEMLERİ ---
def veri_ekle(ws_b, ws_g, sirket, pozisyon, durum, notlar, link):
    tarih = datetime.now().strftime("%d-%m-%Y %H:%M")
    basvuru_id = str(uuid.uuid4())[:8]
    gecmis_id = str(uuid.uuid4())[:8]
    if not link: link = ""
    ws_b.append_row([basvuru_id, sirket, pozisyon, durum, tarih, notlar, link])
    ws_g.append_row([gecmis_id, basvuru_id, "YENİ KAYIT", f"Durum: {durum}", tarih])

def veri_guncelle(ws_b, ws_g, id, sirket, pozisyon, durum, notlar, link):
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
        ws_b.update_cell(row, 7, link)
        
        gecmis_id = str(uuid.uuid4())[:8]
        if eski_durum != durum:
            ws_g.append_row([gecmis_id, id, "GÜNCELLEME", f"{eski_durum} -> {durum}", tarih])
        elif notlar:
            ws_g.append_row([gecmis_id, id, "NOT GÜNCELLEME", f"Not: {notlar}", tarih])
    except Exception as e: st.error(f"Hata: {e}")

def veri_sil(ws_b, ws_g, id):
    try:
        cell = ws_b.find(id)
        ws_b.delete_rows(cell.row)
    except: pass

def gecmis_tekil_sil(ws_g, gecmis_id):
    try:
        cell = ws_g.find(gecmis_id)
        ws_g.delete_rows(cell.row)
    except: pass

# --- UYGULAMA BAŞLANGICI ---
sheet = baglanti_kur()
ws_basvuru, ws_gecmis = sayfalari_hazirla(sheet)

st.title("💼 İş Başvuru Takip")

# --- VERİLERİ ÇEK ---
data_b = ws_basvuru.get_all_records()
df = pd.DataFrame(data_b)
data_g = ws_gecmis.get_all_records()
df_gecmis = pd.DataFrame(data_g)

if not df.empty:
    if 'ID' in df.columns: df['ID'] = df['ID'].astype(str)
    if 'Link' not in df.columns: df['Link'] = ""
if not df_gecmis.empty:
    if 'Basvuru_ID' in df_gecmis.columns: df_gecmis['Basvuru_ID'] = df_gecmis['Basvuru_ID'].astype(str)
    if 'Gecmis_ID' in df_gecmis.columns: df_gecmis['Gecmis_ID'] = df_gecmis['Gecmis_ID'].astype(str)

# --- SEKMELER ---
tab_goruntule, tab_duzenle, tab_analiz = st.tabs(["👀 Görüntüle & PDF", "✏️ Düzenle", "📊 Analiz"])

# ==========================================
# TAB 1: GÖRÜNTÜLEME & PDF
# ==========================================
with tab_goruntule:
    if df.empty:
        st.info("Henüz veri yok.")
    else:
        c1, c2, c3 = st.columns([1, 2, 2])
        with c1:
            pdf_data = create_pdf(df, df_gecmis)
            st.download_button(
                label="📄 Rapor İndir",
                data=pdf_data,
                file_name="Kariyer_Raporu.pdf",
                mime="application/pdf",
                type="primary"
            )
        with c2:
            filtre_durum = st.multiselect("Filtre", df['Durum'].unique(), key="view_filter")
        with c3:
            filtre_ara = st.text_input("Ara", key="view_search")

        df_view = df.copy()
        if filtre_durum: df_view = df_view[df_view['Durum'].isin(filtre_durum)]
        if filtre_ara: df_view = df_view[df_view['Sirket'].str.contains(filtre_ara, case=False)]

        st.divider()

        for index, row in df_view.iterrows():
            row_id = str(row['ID'])
            durum = row['Durum']
            link = row.get('Link', '')
            
            icon = "⚪"
            if durum == "Reddedildi": icon="🔴"
            elif durum == "Teklif Alındı": icon="🟢"
            elif durum == "Mülakat Bekleniyor": icon="🟠"
            elif durum == "Görüşüldü": icon="🟡"

            baslik = f"{icon} **{row['Sirket']}** - {row['Pozisyon']}  |  *Durum: {durum}*"
            
            with st.expander(baslik):
                col_detay, col_tarihce = st.columns([1, 2])
                with col_detay:
                    st.markdown("#### 📌 Özet")
                    st.write(f"**Tarih:** {row['Tarih']}")
                    st.info(f"**Not:** {row['Notlar']}")
                    if link and str(link).startswith("http"):
                        st.link_button("🔗 İlana Git", link)
                with col_tarihce:
                    st.markdown("#### 🕒 Geçmiş")
                    if not df_gecmis.empty:
                        bu_gecmis = df_gecmis[df_gecmis['Basvuru_ID'] == row_id].sort_values(by='Tarih', ascending=False)
                        if not bu_gecmis.empty:
                            st.dataframe(bu_gecmis[['Tarih', 'Islem', 'Detay']], hide_index=True, use_container_width=True)
                        else: st.caption("Yok")
                    else: st.caption("Yok")

# ==========================================
# TAB 2: DÜZENLEME
# ==========================================
with tab_duzenle:
    col_form, col_list = st.columns([1, 2])

    with col_form:
        st.subheader("Yeni Ekle")
        with st.form("ekle_form", clear_on_submit=True):
            s_sirket = st.text_input("Şirket")
            s_pozisyon = st.text_input("Pozisyon")
            s_link = st.text_input("İlan Linki")
            s_durum = st.selectbox("Durum", ["Başvuruldu", "Görüşüldü", "Mülakat Bekleniyor", "Teklif Alındı", "Reddedildi"])
            s_not = st.text_area("Not")
            if st.form_submit_button("Kaydet"):
                if s_sirket and s_pozisyon:
                    with st.spinner("..."):
                        veri_ekle(ws_basvuru, ws_gecmis, s_sirket, s_pozisyon, s_durum, s_not, s_link)
                    st.rerun()
                else: st.error("Eksik bilgi.")

    with col_list:
        st.subheader("Yönetim")
        if df.empty: st.info("Kayıt yok.")
        else:
            arama_edit = st.text_input("Şirket Ara", key="edit_search")
            df_edit = df.copy()
            if arama_edit: df_edit = df_edit[df_edit['Sirket'].str.contains(arama_edit, case=False)]

            for index, row in df_edit.iterrows():
                row_id = str(row['ID'])
                durum = row['Durum']
                link = row.get('Link', '')
                icon = "⚪"
                if durum == "Reddedildi": icon="🔴"
                elif durum == "Teklif Alındı": icon="🟢"
                elif durum == "Mülakat Bekleniyor": icon="🟠"
                elif durum == "Görüşüldü": icon="🟡"

                with st.expander(f"{icon} {row['Sirket']} - {row['Pozisyon']}"):
                    c_gecmis, c_guncelle = st.columns([3, 2])
                    with c_gecmis:
                        st.markdown("##### 🕒 Geçmiş")
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
                                                if st.button("Onayla", key=f"gs_{g_id}"):
                                                    gecmis_tekil_sil(ws_gecmis, g_id); st.rerun()
                                        st.divider()
                            else: st.info("Yok.")
                        else: st.info("Yok.")

                    with c_guncelle:
                        st.markdown("##### ⚙️ Güncelle")
                        idx = 0
                        secenekler = ["Başvuruldu", "Görüşüldü", "Mülakat Bekleniyor", "Teklif Alındı", "Reddedildi"]
                        if durum in secenekler: idx = secenekler.index(durum)
                        
                        y_durum = st.selectbox("Durum", secenekler, key=f"s_{row_id}", index=idx)
                        y_link = st.text_input("Link", value=link, key=f"l_{row_id}")
                        y_not = st.text_input("Not", value=row['Notlar'], key=f"n_{row_id}")
                        
                        cb1, cb2 = st.columns(2)
                        with cb1:
                            if st.button("💾", key=f"save_{row_id}"):
                                veri_guncelle(ws_basvuru, ws_gecmis, row_id, row['Sirket'], row['Pozisyon'], y_durum, y_not, y_link); st.rerun()
                        with cb2:
                            with st.popover("🗑️", use_container_width=True):
                                if st.button("Sil", key=f"del_confirm_{row_id}", type="primary"):
                                    veri_sil(ws_basvuru, ws_gecmis, row_id); st.rerun()

# ==========================================
# TAB 3: ANALİZ
# ==========================================
with tab_analiz:
    if df.empty: st.info("Analiz için veri gerekli.")
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

