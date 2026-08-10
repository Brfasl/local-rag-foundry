import streamlit as st
from foundry_local_sdk import Configuration, FoundryLocalManager
from openai import OpenAI
from retrieval import get_relevant_chunks

st.set_page_config(page_title="Local RAG Foundry", page_icon="🤖", layout="wide")

st.title("🤖 Local RAG Foundry Asistanı")
st.caption("Yerel Cihazda Çalışan SQLite + Foundry Local Destekli RAG Uygulaması")

# 1. Foundry Local Servisi, Model Bulma ve Yükleme
@st.cache_resource
def init_foundry():
    try:
        config = Configuration(app_name="local-rag-app")
        manager = FoundryLocalManager(config)
    except Exception:
        manager = FoundryLocalManager.instance

    # EP Kaydı
    try:
        manager.download_and_register_eps(["WebGpuExecutionProvider"])
    except Exception:
        pass

    # Model Nesnesini Liste İçinden Bulma
    selected_model_id = "phi-1.5-mini"
    try:
        all_models = manager.catalog.list_models()
        # Qwen 0.5b veya ilk kullanılabilir modeli seçelim
        target_models = [m for m in all_models if "qwen2.5-0.5b" in str(m.id)]
        model_obj = target_models[0] if target_models else all_models[0]
        selected_model_id = model_obj.id

        # İndirme ve Belleğe Yükleme
        if hasattr(model_obj, "is_cached") and not model_obj.is_cached:
            model_obj.download()
        else:
            try:
                model_obj.download()
            except Exception:
                pass

        if hasattr(model_obj, "is_loaded") and not model_obj.is_loaded:
            model_obj.load()
        else:
            try:
                model_obj.load()
            except Exception:
                pass
    except Exception as err:
        st.sidebar.warning(f"Model hazırlık uyarısı: {err}")

    # Web Servisini Başlatma
    try:
        manager.start_web_service()
    except Exception:
        pass

    # URL Temizleme
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

# 2. Kullanıcı Arayüzü ve Soru Yanıt Hattı
query = st.text_input("Sorunuzu girin:", placeholder="Örn: Foundry Local ne işe yarar?")

if st.button("Sor", type="primary") and query:
    chunks = get_relevant_chunks(query, top_k=2)
    context_text = "\n".join(chunks) if chunks else "İlgili kaynak bulunamadı."

    with st.expander("📚 Veritabanından Bulunan Kaynak Metinler (Context)", expanded=True):
        if chunks:
            for i, chunk in enumerate(chunks, 1):
                st.markdown(f"**Parça {i}:** {chunk}")
        else:
            st.warning("Eşleşen metin bulunamadı.")

    system_prompt = (
        "Sen yerel çalışan yardımcı bir asistanısın. Sadece sana verilen BAGLAM bilgisini kullanarak soruya cevap ver. "
        "Eğer verilen bağlamda bilgi yoksa uydurma ve 'Bu konuda elimdeki dokümanlarda yeterli bilgi yok.' de."
    )
    user_prompt = f"BAGLAM:\n{context_text}\n\nSORU: {query}"

    st.subheader("💡 Asistan Yanıtı")
    
    if client:
        with st.spinner("Model yanıt üretiyor..."):
            try:
                response = client.chat.completions.create(
                    model=active_model_id,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.2,
                    stream=False
                )
                
                answer_text = response.choices[0].message.content
                st.write(answer_text)
            except Exception as err:
                st.error(f"Model Yanıt Hatası: {err}")
    else:
        st.error("Yerel model servisine bağlanılamadı.")