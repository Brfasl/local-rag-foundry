import streamlit as st
from foundry_local_sdk import Configuration, FoundryLocalManager
from retrieval import get_relevant_chunks

# Sayfa Yapılandırması
st.set_page_config(page_title="Local RAG Foundry", page_icon="🤖", layout="wide")

st.title("🤖 Local RAG Foundry Asistanı")
st.caption("Tamamen yerel cihazda çalışan SQLite + Foundry Local destekli RAG uygulaması")

# Foundry Local Servisini Bir Kere Yükleme
@st.cache_resource
def load_manager():
    config = Configuration(app_name="local-rag-app")
    return FoundryLocalManager(config)

manager = load_manager()

# Kullanıcı Soru Girişi
query = st.text_input("Sorunuzu girin:", placeholder="Örn: Foundry Local ne işe yarar?")

if st.button("Sor", type="primary") and query:
    # 1. SQLite'tan bağlam çekme
    chunks = get_relevant_chunks(query, top_k=2)
    context_text = "\n".join(chunks) if chunks else "İlgili kaynak bulunamadı."

    # 2. Ekranın solunda veya üstünde çekilen kaynakları gösterme
    with st.expander("📚 Veritabanından Bulunan Kaynak Metinler (Context)", expanded=True):
        if chunks:
            for i, chunk in enumerate(chunks, 1):
                st.markdown(f"**Parça {i}:** {chunk}")
        else:
            st.warning("Eşleşen metin bulunamadı.")

    # 3. Sistem Prompt Yapısı
    system_prompt = (
        "Sen yerel çalışan bir asistanısın. Sadece sana verilen BAGLAM bilgisini kullanarak soruya cevap ver. "
        "Eğer verilen bağlamda bilgi yoksa uydurma ve 'Bu konuda elimdeki dokümanlarda yeterli bilgi yok.' de.\n\n"
        f"BAGLAM:\n{context_text}\n\n"
        f"SORU: {query}"
    )

    # 4. Yanıt Alanı
    st.subheader("💡 Asistan Yanıtı")
    st.info(system_prompt)