import re
import sqlite3
import streamlit as st
from foundry_local_sdk import Configuration, FoundryLocalManager
from openai import OpenAI
from retrieval import get_relevant_chunks, get_all_chunks

from ingest import save_uploaded_file

st.set_page_config(page_title="Local RAG Foundry", page_icon="🤖", layout="wide")

# ─────────────────────────────────────────────
# Yardımcı Fonksiyonlar
# ─────────────────────────────────────────────

def reset_database(db_path="rag_data.db"):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents")
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def clean_llm_output(text: str) -> str:
    text = re.sub(r'!{2,}', '!', text)
    text = re.sub(r'\.{3,}', '.', text)
    return text.strip()


def clean_repetitive_text(text: str) -> str:
    """Modelden gelen metindeki tekrarlayan cümleleri siler."""
    sentences = text.split('.')
    seen = set()
    cleaned = []
    for s in sentences:
        s_strip = s.strip()
        if s_strip and s_strip not in seen:
            seen.add(s_strip)
            cleaned.append(s_strip)
    return '. '.join(cleaned) + '.' if cleaned else text


# ─────────────────────────────────────────────
# 1. Foundry Local Servisi ve Model Yükleme
# ─────────────────────────────────────────────

@st.cache_resource
def init_foundry():
    try:
        config = Configuration(app_name="local-rag-app")
        manager = FoundryLocalManager(config)
    except Exception:
        manager = FoundryLocalManager.instance

    try:
        manager.download_and_register_eps(["WebGpuExecutionProvider"])
    except Exception:
        selected_model_id = "qwen2.5-7b-instruct-generic-gpu:4"

    try:
        all_models = manager.catalog.list_models()
        preferred_candidates = [
            "qwen2.5-1.5b-instruct",
            "qwen2.5-coder-1.5b-instruct",
            "qwen2.5-0.5b-instruct",
            "qwen2.5-7b-instruct"
        ]

        chosen_model = None
        for pref in preferred_candidates:
            matches = [m for m in all_models if pref in str(m.id)]
            if matches:
                chosen_model = matches[0]
                break

        model_obj = chosen_model if chosen_model else all_models[0]
        selected_model_id = model_obj.id

        if hasattr(model_obj, "is_cached") and not model_obj.is_cached:
            with st.spinner(f"Akil Model Indiriliyor ({selected_model_id})... Lutfen bekleyin."):
                model_obj.download()

        if hasattr(model_obj, "is_loaded") and not model_obj.is_loaded:
            with st.spinner(f"Model Yukleniyor ({selected_model_id})..."):
                model_obj.load()
    except Exception as err:
        st.sidebar.warning(f"Model hazirlik uyarisi: {err}")

    try:
        manager.start_web_service()
    except Exception:
        pass

    urls = manager.urls
    raw_url = ""

    if isinstance(urls, list) and len(urls) > 0:
        raw_url = str(urls[0])
    elif isinstance(urls, dict) and urls:
        raw_url = str(urls.get("openai") or list(urls.values())[0])
    else:
        raw_url = str(urls) if urls else ""

    raw_url = raw_url.strip("[]'\" ").rstrip("/")
    if not raw_url or raw_url == "None":
        raise ValueError("Servis URL adresi bulunamadi.")

    base_url = raw_url if raw_url.endswith("/v1") else f"{raw_url}/v1"
    client = OpenAI(base_url=base_url, api_key="foundry")
    return client, base_url, selected_model_id


try:
    client, active_url, active_model_id = init_foundry()
except Exception as e:
    st.sidebar.error(f"Servis Hatasi: {e}")
    client = None
    active_model_id = "qwen2.5-7b-instruct-generic-gpu:4"


# ─────────────────────────────────────────────
# 2. Sohbet Gecmisi Baslatma
# ─────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

if "ingested_files" not in st.session_state:
    st.session_state.ingested_files = set()


# ─────────────────────────────────────────────
# 3. Sol Menu (Sidebar)
# ─────────────────────────────────────────────

# 3a. Dokuman Yonetimi
st.sidebar.markdown("## 📂 Doküman Yönetimi")

uploaded_files = st.sidebar.file_uploader(
    "PDF, DOCX veya TXT dosyası seçin",
    type=["pdf", "txt", "docx", "doc"],
    accept_multiple_files=True,
    label_visibility="collapsed"
)

# Otomatik ingest: her yeni dosyayi aninda isle
if uploaded_files:
    newly_ingested = []
    for uf in uploaded_files:
        file_key = f"{uf.name}_{uf.size}"
        if file_key not in st.session_state.ingested_files:
            # Yeni dosya yüklenmeden önce eski veritabanı kayıtlarını temizle
            reset_database()
            st.session_state.ingested_files = set()

            file_bytes = uf.read()
            chunks_count = save_uploaded_file(file_bytes, uf.name)
            if chunks_count > 0:
                st.session_state.ingested_files.add(file_key)
                newly_ingested.append((uf.name, chunks_count))

    if newly_ingested:
        # Sadece toast göster — sohbet alanına mesaj ekleme
        st.toast("Dokümanlar veritabanına işlendi!", icon="✅")
        st.rerun()


# 3b. Hizli Islemler
st.sidebar.markdown("---")
st.sidebar.markdown("## ⚙️ Hızlı İşlemler")

# Dokumanlari Ozetle
if st.sidebar.button("📝 Dokümanları Özetle", use_container_width=True):
    all_chunks = get_all_chunks()
    if not all_chunks:
        st.sidebar.error("Veritabanında özetlenecek doküman bulunamadı.")
    elif not client:
        st.sidebar.error("Model servisi aktif değil.")
    else:
        selected_chunks = []
        curr_len = 0
        for ch in all_chunks:
            if curr_len + len(ch) > 8000:
                break
            selected_chunks.append(ch)
            curr_len += len(ch)
        context_text = "\n\n".join(selected_chunks)

        messages = [
            {
                "role": "system",
                "content": (
                    "Sen yüklenen dokümanı analiz eden son derece akıllı ve dürüst bir Yapay Zeka Akıl Ortağısın (Agent).\n\n"
                    "GÖREVİN VE KESİN KURALLARIN:\n"
                    "1. SADECE DOKÜMANA DAYAN: Yanıtlarını SADECE sana verilen 'DOKÜMAN BİLGİSİ / BAĞLAM' metnine dayandır. Dokümanda yer almayan bilgileri asla uydurma veya ekleme.\n"
                    "2. ADAPTE OL VE SENTEZLE: Kullanıcının isteğine göre (özetleme, planlama, dönüştürme, analiz) dokümandaki gerçek verilere bağlı kalarak istenen yapıyı oluştur.\n"
                    "3. DOĞRUDAN VE AKICI YANIT VER: Yanıtına doğrudan başla. Sistem talimatlarını veya kural cümlelerini yanıtın içinde asla tekrarlama.\n"
                    "4. DİL UYUMU: Doküman İngilizce veya farklı dilde olsa dahi kullanıcının Türkçe isteğine uygun olarak doğru, net ve mantıklı bir özet oluştur."
                )
            },
            {
                "role": "user",
                "content": f"DOKÜMAN BİLGİSİ / BAĞLAM:\n{context_text}\n\nKULLANICI İSTEĞİ / SORUSU:\nMetnin ana konusunu ve önemli noktalarını Türkçe olarak detaylı bir şekilde özetle."
            }
        ]

        with st.spinner("📑 Özet çıkartılıyor..."):
            try:
                response = client.chat.completions.create(
                    model=active_model_id,
                    messages=messages,
                    temperature=0.1,
                    top_p=0.9,
                    max_tokens=800,
                    frequency_penalty=0.5,
                    stop=["<|im_end|>", "<|endoftext|>", "<|im_start|>"]
                )
                summary_text = response.choices[0].message.content.strip()
                summary_text = clean_repetitive_text(summary_text)

                if not summary_text:
                    summary_text = "Model özet üretemedi."

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "### 📑 Doküman Özeti\n\n" + summary_text,
                    "context": context_text
                })
                st.rerun()
            except Exception as err:
                st.sidebar.error(f"Özet hatası: {err}")

# Sohbeti Temizle
if st.sidebar.button("🗑️ Sohbeti Temizle", use_container_width=True):
    st.session_state.messages = []
    st.toast("Sohbet geçmişi temizlendi!", icon="🧹")
    st.rerun()

# Veritabanini Sifirla (ikincil aksiyon)
st.sidebar.markdown("")
if st.sidebar.button("💥 Veritabanını Sıfırla", type="secondary", use_container_width=True):
    if reset_database():
        st.session_state.ingested_files = set()
        # Sadece toast göster — sohbet alanına mesaj ekleme
        st.toast("Veritabanı ve tüm dokümanlar temizlendi!", icon="🗑️")
        st.rerun()
    else:
        st.sidebar.error("Veritabanı sıfırlanırken bir hata oluştu.")


# 3c. Sohbet Gecmisi (Sidebar)
st.sidebar.markdown("---")
st.sidebar.markdown("## 💬 Sohbet Geçmişi")

if st.session_state.messages:
    with st.sidebar.expander(f"📜 {len(st.session_state.messages)} mesaj", expanded=False):
        for msg in st.session_state.messages[-10:]:
            role_icon = "🧑" if msg["role"] == "user" else "🤖"
            preview = msg["content"][:60].replace("\n", " ")
            st.caption(f"{role_icon} {preview}...")
else:
    st.sidebar.caption("Henuz sohbet gecmisi yok.")


# ─────────────────────────────────────────────
# 4. Ana Sohbet Alanı
# ─────────────────────────────────────────────

st.title("🤖 Local RAG Foundry Asistanı")
st.caption("Yerel Cihazda Çalışan SQLite + Foundry Local Destekli RAG Uygulaması")

# ── Geçmiş mesajları render et ──────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # Kaydedilmiş context varsa expander olarak göster
        if msg.get("context"):
            with st.expander("📚 Kullanılan Kaynak Metinler (Context)", expanded=False):
                st.write(msg["context"])

# ── Yeni soru alma ve işleme ────────────────────
if prompt := st.chat_input("Sorunuzu yazın..."):

    # 1. Sorguya özel en alakalı 5 chunk'ı çek (top_k=5)
    relevant_chunks = get_relevant_chunks(prompt, top_k=5)
    # Mükerrer (aynı) chunk'ları ayıkla — sıra korunarak
    seen = set()
    unique_chunks = []
    for ch in relevant_chunks:
        if ch not in seen:
            seen.add(ch)
            unique_chunks.append(ch)
    relevant_chunks = unique_chunks
    if relevant_chunks:
        context_text = "\n\n".join(relevant_chunks)
    else:
        context_text = "Yüklenmiş doküman bulunmamaktadır."

    # 2. System prompt — sertleştirilmiş, halüsinasyona karşı korumalı
    sys_prompt = (
        "Sen sadece sana sağlanan [BAĞLAM] içindeki metinleri kullanan bir asistansın. "
        "[BAĞLAM] dışına çıkma. "
        "Bilgi bağlamda yoksa dürüstçe 'Dokümanda bu bilgi yer almıyor' de. "
        "Asla kendi kafandan dosya silme/yükleme adımları uydurma. "
        "Yanıtlarını SADECE aşağıdaki [BAĞLAM] metnine dayandır. "
        "Her zaman Türkçe yanıt ver."
    )

    # Son 2 mesajı (takip bağlamı için) al
    history_msgs = []
    for m in st.session_state.messages[-2:]:
        history_msgs.append({"role": m["role"], "content": m["content"]})

    # Kullanıcının sorusunu [BAĞLAM] ile birlikte user mesajına göm
    user_content = (
        f"[BAĞLAM]\n{context_text}\n[/BAĞLAM]\n\n"
        f"SORU: {prompt}"
    )

    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(history_msgs)
    messages.append({"role": "user", "content": user_content})

    # 3. Kullanıcı mesajını arayüze kaydet ve göster
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 4. LLM'e gönder ve yanıt üret
    bot_response = ""
    with st.chat_message("assistant"):
        with st.spinner("Yanıt üretiliyor..."):
            if not client:
                bot_response = "❌ Yerel model servisine bağlanılamadı."
                st.error(bot_response)
            else:
                try:
                    response = client.chat.completions.create(
                        model=active_model_id,
                        messages=messages,
                        temperature=0.1,
                        top_p=0.9,
                        max_tokens=250,
                        frequency_penalty=0.5,
                        stop=["<|im_end|>", "<|endoftext|>", "<|im_start|>"]
                    )
                    bot_response = response.choices[0].message.content.strip()
                    bot_response = clean_repetitive_text(bot_response)

                    if not bot_response:
                        bot_response = "Model boş yanıt döndürdü. Lütfen tekrar deneyin."

                except Exception as err:
                    bot_response = f"❌ Model Yanıt Hatası: {err}"
                    st.error(bot_response)

        # 5. Bot yanıtını ekrana bas
        st.markdown(bot_response)

        # 6. Referans alınan metin parçalarını şeffaf şekilde göster
        if relevant_chunks:
            with st.expander("📄 Referans Alınan Metin Parçaları"):
                for i, chunk in enumerate(relevant_chunks, 1):
                    st.markdown(f"**Parça {i}:**")
                    st.caption(chunk)
                    if i < len(relevant_chunks):
                        st.divider()

    # 7. Asistan yanıtını geçmişe kaydet
    st.session_state.messages.append({
        "role": "assistant",
        "content": bot_response,
        "context": context_text
    })