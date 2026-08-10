import sqlite3
import streamlit as st
from foundry_local_sdk import Configuration, FoundryLocalManager
from openai import OpenAI
from retrieval import get_relevant_chunks, get_all_chunks
from ingest import save_uploaded_file

st.set_page_config(page_title="Local RAG Foundry", page_icon="🤖", layout="wide")

st.title("🤖 Local RAG Foundry Asistanı")
st.caption("Yerel Cihazda Çalışan SQLite + Foundry Local Destekli RAG Uygulaması")

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

# 1. Foundry Local Servisi ve Model Yükleme
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
        pass

    selected_model_id = "phi-1.5-mini"
    try:
        all_models = manager.catalog.list_models()
        target_models = [m for m in all_models if "qwen2.5-1.5b" in str(m.id)]
        model_obj = target_models[0] if target_models else all_models[0]
        selected_model_id = model_obj.id

        if hasattr(model_obj, "is_cached") and not model_obj.is_cached:
            model_obj.download()

        if hasattr(model_obj, "is_loaded") and not model_obj.is_loaded:
            model_obj.load()
    except Exception as err:
        st.sidebar.warning(f"Model hazırlık uyarısı: {err}")

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
        raise ValueError("Servis URL adresi bulunamadı.")

    base_url = raw_url if raw_url.endswith("/v1") else f"{raw_url}/v1"

    client = OpenAI(base_url=base_url, api_key="foundry")
    return client, base_url, selected_model_id

try:
    client, active_url, active_model_id = init_foundry()
    st.sidebar.success(f"✅ Foundry Servisi Aktif\n\n`{active_url}`")
    st.sidebar.info(f"🧠 Aktif Model:\n`{active_model_id}`")
except Exception as e:
    st.sidebar.error(f"❌ Servis Hatası: {e}")
    client = None
    active_model_id = "phi-1.5-mini"

# Sol Menü
st.sidebar.markdown("---")
st.sidebar.header("📂 Veritabanı ve Özet")

if st.sidebar.button("🗑️ Veritabanını Temizle", type="secondary"):
    if reset_database():
        st.sidebar.success("Veritabanı temizlendi!")
        st.rerun()
    else:
        st.sidebar.error("Veritabanı temizlenirken bir hata oluştu.")

uploaded_file = st.sidebar.file_uploader("PDF veya TXT dosyası seçin", type=["pdf", "txt"])

if uploaded_file is not None:
    if st.sidebar.button("Veritabanına İşle", type="secondary"):
        with st.sidebar.spinner("Metinler işleniyor..."):
            bytes_data = uploaded_file.getvalue()
            num_chunks = save_uploaded_file(bytes_data, uploaded_file.name)
            if num_chunks > 0:
                st.sidebar.success(f"🎉 `{uploaded_file.name}` veritabanına eklendi! ({num_chunks} parça)")
                st.rerun()
            else:
                st.sidebar.error("Dosyadan okunabilir metin çıkarılamadı.")

# Veritabanında ne var ne yok kontrol etmek için
all_chunks = get_all_chunks()
if all_chunks:
    with st.expander("🔍 Veritabanındaki Ham Metin Parçaları (Okunan Metin)", expanded=False):
        for idx, ch in enumerate(all_chunks, 1):
            st.text(f"Parça {idx}:\n{ch[:300]}...\n")

# TÜM DOKÜMANI ÖZETLE BUTONU
if st.sidebar.button("📑 Tüm Dokümanı Özetle", type="primary"):
    if not all_chunks:
        st.sidebar.error("Veritabanında özetlenecek doküman bulunamadı.")
    else:
        context_sample = "\n".join(all_chunks)[:1500]
        
        user_summary_prompt = (
            f"Aşağıdaki CV metnini oku ve SADECE TÜRKÇE olarak maddeler halinde özetle:\n\n"
            f"{context_sample}\n\n"
            f"TÜRKÇE ÖZET:"
        )
        
        with st.spinner("Özet çıkartılıyor..."):
            try:
                response = client.chat.completions.create(
                    model=active_model_id,
                    messages=[
                        {
                            "role": "system", 
                            "content": "Sen sadece Türkçe konuşan bir asistansın. Başka hiçbir dil (Japonca, Çince, İngilizce) kullanma. Tüm yanıtlarını kesinlikle Türkçe ver."
                        },
                        {
                            "role": "user", 
                            "content": user_summary_prompt
                        }
                    ],
                    temperature=0.1,
                    max_tokens=300,
                    stream=False
                )
                summary_text = response.choices[0].message.content
                
                if "messages" not in st.session_state:
                    st.session_state.messages = []
                st.session_state.messages.append({"role": "assistant", "content": f"### 📑 Doküman Özeti\n\n{summary_text}"})
                st.rerun()
            except Exception as err:
                st.error(f"Özet çıkarma hatası: {err}")



# 2. Sohbet Geçmişi Yönetimi
if "messages" not in st.session_state:
    st.session_state.messages = []

if st.sidebar.button("🗑️ Sohbet Geçmişini Temizle"):
    st.session_state.messages = []
    st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 3. Chat Input ve Akış
if prompt := st.chat_input("Sorunuzu yazın..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    chunks = get_relevant_chunks(prompt, top_k=2)
    context_text = "\n".join(chunks) if chunks else "İlgili kaynak bulunamadı."

    with st.expander("📚 Kullanılan Kaynak Metinler (Context)", expanded=False):
        if chunks:
            for i, chunk in enumerate(chunks, 1):
                st.markdown(f"**Parça {i}:** {chunk}")
        else:
            st.warning("Eşleşen metin bulunamadı.")

    user_prompt = f"Aşağıdaki metne dayanarak soruyu cevapla.\n\nMETİN:\n{context_text}\n\nSORU: {prompt}\n\nCEVAP:"

    with st.chat_message("assistant"):
        if client:
            with st.spinner("Model yanıt veriyor..."):
                try:
                    response = client.chat.completions.create(
                        model=active_model_id,
                        messages=[
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.2,
                        max_tokens=250,
                        stream=False
                    )
                    answer_text = response.choices[0].message.content
                    st.markdown(answer_text)
                    st.session_state.messages.append({"role": "assistant", "content": answer_text})
                except Exception as err:
                    st.error(f"Model Yanıt Hatası: {err}")
        else:
            st.error("Yerel model servisine bağlanılamadı.")