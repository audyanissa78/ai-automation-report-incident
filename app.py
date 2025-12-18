import streamlit as st
import os
import pytz
from langchain_groq import ChatGroq
from groq import Groq
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime

# --- 1. SETUP PAGE ---
st.set_page_config(page_title="AI Safety Agent", page_icon="⛑️")

if "log_history" not in st.session_state:
    st.session_state.log_history = []

if "widget_id" not in st.session_state:
    st.session_state.widget_id = 0 
  
def reset_app():
    st.session_state.widget_id += 1
    st.rerun()

# --- 2. SIDEBAR API KEY ---
with st.sidebar:
    st.title("⚙️ Panel Kontrol")
    if "GROQ_API_KEY" in st.secrets:
        st.success("✅ API Key terdeteksi dari sistem!")
        api_key = st.secrets["GROQ_API_KEY"]
    else:
        # Jika dijalankan lokal/tanpa secrets, minta input manual
        api_key = st.text_input("Masukkan Groq API Key", type="password")
        if not api_key:
            st.warning("⚠️ Masukkan API Key untuk memulai.")
    st.divider()
    # TOMBOL RESET ADA DI SINI
    if st.button("🔄 Reset / Rekam Ulang", type="primary", use_container_width=True):
        reset_app()

def transcribe_audio(audio_file, api_key):
    """Mengubah suara menjadi teks menggunakan Groq Whisper"""
    try:
        client = Groq(api_key=api_key) 
        transcription = client.audio.transcriptions.create(
            file=(audio_file.name, audio_file, "audio/wav"), # Wajib format tuple
            model="whisper-large-v3",
            response_format="text",
            language="id" 
        )
        return transcription
    except Exception as e:
        st.error(f"Gagal transkripsi: {e}")
        return None
# --- Fungsi Log Manual 
def save_to_log(report: str, risk_level: str):
  wib = pytz.timezone('Asia/Jakarta')
  timestamp = datetime.now(wib).strftime("%Y-%m-%d %H:%M:%S")
  log_entry = f"[{timestamp}] RISK : {risk_level} - {report}\n"
  st.session_state.log_history.append(log_entry)
  return True
  
# --- DEFINISI TOOL ---
# --- TOOL 1 : Mengirim Whatsapp (SImulasi untuk bahaya Menengah)---
@tool
def send_wa_alert(report: str, analysis: str):
  """
  Gunakan alat ini HANYA untuk insiden berisiko MEDIUM (MEDIUM RISK)
  Alat ini akan mengirimkan whatsapp kepada Manajer untuk hal yang perlu perhatian tapi tidak darurat.
  """
  wa_draft = f"""
  === WA SENT TO MANAGER ===
  TO: manager
    SUBJECT: Report of Medium Risk!

    Laporan Teknisi:
    \"{report}\"

    Analisis AI:
    {analysis}

    Mohon tindakan secepatnya.
    ================================
    """
  print(wa_draft) # Di dunia nyata, ganti ini dengan library SMTP/Gmail API
  return "WA darurat telah dikirim ke Manajer."

# --- TOOL 2 : Mengirim Email (SImulasi untuk bahaya Tinggi)---
@tool
def send_email_alert(report: str, analysis: str):
  """
  Gunakan alat ini HANYA untuk insiden berisiko TINGGI (HIGH RISK)
  Alat ini akan mengirimkan draf email darurat kepada Manajer
  """
  email_draft = f"""
  === EMAIL SENT TO MANAGER ===
  TO: manager@pabrik.com
    SUBJECT: ⚠️ URGENT: High Risk Incident Detected!

    Laporan Teknisi:
    \"{report}\"

    Analisis AI:
    {analysis}

    Mohon tindakan segera.
    ================================
    """
  print(email_draft) # Di dunia nyata, ganti ini dengan library SMTP/Gmail API
  return "Email darurat telah dikirim ke Manajer."

# Daftar alat yang akan diberikan ke AI
tools = [send_wa_alert, send_email_alert]

# --- 4. LOGIC AGENT ---
st.title("⛑️ AI Safety Reporter")
st.markdown("---")

if api_key:
    try:
        llm = ChatGroq(groq_api_key=api_key, model="llama-3.3-70b-versatile", temperature=0)
        llm_with_tools = llm.bind_tools(tools)
    except Exception as e:
        st.error(f"Error API Key: {e}")
        st.stop()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🗣️ Input Suara")
        # Perhatikan: key menggunakan widget_id agar bisa di-reset
        audio_value = st.audio_input("Rekam Laporan", key=f"audio_{st.session_state.widget_id}")

    with col2:
        st.subheader("⌨️ Input Teks")
        text_value = st.text_area("Ketik Laporan", height=70, key=f"text_{st.session_state.widget_id}")

    # Tentukan input mana yang dipakai
    final_report_text = ""
    if audio_value:
        with st.spinner("Menerjemahkan suara..."):
            final_report_text = transcribe_audio(audio_value, api_key)
            st.info(f"🎤 Terdeteksi: {final_report_text}")
    elif text_value:
        final_report_text = text_value

    if final_report_text:
            st.divider()
            st.subheader("🤖 Analisis AI Agent")
            st.markdown("---")

            with st.spinner("🕵️ AI sedang menganalisis tingkat bahaya..."):
                # System Prompt
                sysmsg = """
                    Anda adalah AI Safety Supervisor di sebuah pabrik. Tugas Anda:
                    1. Baca laporan singkat dari teknisi.
                    2. Analisis seberapa bahaya situasi tersebut.
                    3. JIKA bahaya RENDAH (hanya perawatan rutin, info biasa, error kecil):
                      -> Gunakan tool 'log_incident'.
                    4. JIKA bahaya MEDIUM (Perlu perhatian tapi tidak darurat misal stok oli habis, meisn butuh servis minggu depan):
                      -> Gunakan tool 'send_wa_alert'. Sertakan analisis singkat kenapa ini menengah.
                    5. JIKA bahaya TINGGI (api, ledakan, cedera, mesin overheat parah):
                      -> Gunakan tool 'send_email_alert'. Sertakan analisis singkat kenapa ini berbahaya.
                    6. Jika laporannya tidak jelas atau bukan tetntang mesin, langsung jawab "Mohon berikan laporan teknis yang spesifik" tanpa memanggil tool apapun.
                    7. Jika AMAN -> Jangan panggil tool apapun, cukup balas dengan analisis singkat.


                    Pilih tindakan yang paling tepat.
                    """
                messages = [
                    SystemMessage(content=sysmsg),
                    HumanMessage(content=final_report_text)
                ]

                ai_response = llm_with_tools.invoke(messages)

                # Cek Keputusan AI
                risk_status = "AMAN" # Default
                ai_action_text = "Tidak ada tindakan eskalasi."

                if ai_response.tool_calls:
                    for tool_call in ai_response.tool_calls:
                        func_name = tool_call['name']
                        args = tool_call['args']

                        st.write(f"🧠 *AI memutuskan menggunakan tool:* `{func_name}`")

                        if func_name == "send_email_alert":
                            st.error(f"KATEGORI: BAHAYA TINGGI (HIGH RISK)")
                            # Eksekusi Tool
                            result = send_email_alert.invoke(args)
                            risk_status = "BAHAYA TINGGI"
                            st.code(result) # Tampilkan simulasi email

                        elif func_name == "send_wa_alert":
                            st.success(f"KATEGORI: BAHAYA MENENGAH (MEDIUM RISK)")
                            # Eksekusi Tool
                            result = send_wa_alert.invoke(args)
                            risk_status = "BAHAYA MEDIUM"
                            st.info(result)
                        
                else:
                    # Jika AI bingung / hanya mengobrol
                    st.warning("AI memberikan respon langsung (Tidak memanggil alat):")
                    st.write(ai_response.content)
                
                # --- TAHAP 3: AUTO-LOGGING (Double Action) ---
                # Apapun keputusan AI, kita PASTI jalankan ini
                save_to_log(final_report_text, risk_status)
                st.toast("📝 Laporan berhasil disimpan ke Database Log!", icon="✅")

    # --- 7. TAMPILAN LOG DATABASE ---
    st.markdown("---")
    st.subheader("📂 Database Log Insiden (Live Update)")

    if len(st.session_state.log_history) > 0:
        log_text = "\n".join(st.session_state.log_history)
        st.text_area("History Log:", value=log_text, height=200, disabled=True)
        
        st.download_button(
            label="📥 Download Log (.txt)",
            data=log_text,
            file_name="incident_log.txt",
            mime="text/plain"
        )
    else:
        st.info("Belum ada data masuk.")
      
else:
    st.warning("Masukkan API Key di sidebar untuk mengaktifkan Agent.")
