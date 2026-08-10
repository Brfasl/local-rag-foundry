from foundry_local_sdk import Configuration, FoundryLocalManager

# Konfigürasyonu uygulama adıyla oluşturuyoruz
config = Configuration(app_name="local-rag-app")

# Yerel servis yöneticisini başlatıyoruz
manager = FoundryLocalManager(config)

print("Foundry Local Manager başarıyla çalıştırıldı!")