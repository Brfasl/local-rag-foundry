from foundry_local_sdk import Configuration, FoundryLocalManager
from retrieval import get_relevant_chunks

# 1. Foundry Local Servisini Başlatma
config = Configuration(app_name="local-rag-app")
manager = FoundryLocalManager(config)

def ask_rag_assistant(question):
    # 2. SQLite'tan alakalı doküman parçalarını çekme
    context_chunks = get_relevant_chunks(question, top_k=2)
    # Mükerrer chunk'ları ayıkla
    seen = set()
    context_chunks = [ch for ch in context_chunks if ch not in seen and not seen.add(ch)]
    context_text = "\n".join(context_chunks) if context_chunks else "İlgili kaynak bulunamadı."

    # 3. Prompt Engineering (Modele Sadece Verilen Bağlamı Kullanmasını Söylüyoruz)
    system_prompt = (
        "Sen yerel çalışan bir asistanısın. Sadece sana verilen BAGLAM bilgisini kullanarak soruya cevap ver. "
        "Eğer verilen bağlamda bilgi yoksa uydurma ve 'Bu konuda elimdeki dokümanlarda yeterli bilgi yok.' de.\n\n"
        f"BAGLAM:\n{context_text}"
    )

    print(f"\n--- [BULUNAN BAGLAM] ---\n{context_text}\n--------------------------\n")
    print(f"Soru: {question}")
    
    # Not: Streamlit arayüzünde tam model yanıt akışına geçeceğiz
    print(f"Yanıt (Sistem Komutu Hazırlandı): {system_prompt}")

if __name__ == "__main__":
    test_soru = "Foundry Local ne işe yarar?"
    ask_rag_assistant(test_soru)