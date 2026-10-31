"""Localized operator progress events; machine-readable results are unchanged."""
import json
import sys
from pathlib import Path

_TR_PHASE = {"CHECK": "KONTROL", "UPDATE": "GÜNCELLEME", "REBOOT": "YENİDEN BAŞLATMA",
             "VERIFY": "DOĞRULAMA", "INIT": "İLK KURULUM", "CLEANUP": "TEMİZLİK"}
_TR_MESSAGES = {
    "Checking installed kernel versions, repositories and /boot space...": "Kurulu kernel sürümleri, depolar ve /boot alanı kontrol ediliyor...",
    "Eligible kernel upgrade found; installing repository RPM packages with DNF. Please do not close this session.": "Uygun kernel güncellemesi bulundu; DNF ile RPM paketleri kuruluyor. Lütfen oturumu kapatmayın.",
    "Checking operator-approved recovery readiness and application health...": "Onaylanan kurtarma hazırlığı ve uygulama sağlığı kontrol ediliyor...",
    "Preparing one-time GRUB boot with previous-kernel fallback...": "Önceki kernel geri dönüş seçeneği korunarak tek seferlik GRUB açılışı hazırlanıyor...",
    "Post-boot verification failed. Old kernel remains the persistent fallback; operator review required.": "Açılış sonrası doğrulama başarısız. Eski kernel kalıcı geri dönüş seçeneği olarak korundu; yönetici incelemesi gerekiyor.",
    "Automatic updates and reboot disabled; performing read-only check.": "Otomatik güncelleme ve yeniden başlatma kapalı; salt okunur kontrol yapılıyor.",
    "Starting first managed kernel maintenance pass...": "İlk yönetilen kernel bakım işlemi başlatılıyor...",
    "Initial setup action was already recorded; not repeating the first-install kernel transaction.": "İlk kurulum işlemi daha önce kaydedilmiş; kernel kurulumu tekrarlanmıyor.",
    "/boot below the minimum free-space threshold; checking safe obsolete-kernel cleanup.": "/boot alanı minimum eşiğin altında; güvenli eski kernel temizliği değerlendiriliyor.",
    "Trial kernel prepared; sending event notification and recording fleet report before restart...": "Deneme kerneli hazırlandı; yeniden başlatmadan önce olay bildirimi ve merkezi rapor gönderiliyor...",
    "systemctl accepted the reboot request. Waiting for server startup and post-boot checks.": "systemctl yeniden başlatma isteğini kabul etti. Sunucunun açılması ve sağlık kontrolleri bekleniyor.",
}
_TR_PREFIX = {
    "Restart blocked: ": "Yeniden başlatma engellendi: ",
    "Reboot request failed: ": "Yeniden başlatma isteği başarısız: ",
    "Server restarted. Running kernel: ": "Sunucu yeniden başladı. Çalışan kernel: ",
    "Kernel RPM installation finished. Running: ": "Kernel RPM kurulumu tamamlandı. Çalışan: ",
    "One-time GRUB boot staged for ": "Tek seferlik GRUB açılışı hazırlandı: ",
    "A newer kernel is already installed; verifying it for a controlled trial boot.": "Yeni kernel zaten kurulu; kontrollü deneme açılışı için doğrulanıyor.",
}
def _language():
    try:
        data = json.loads(Path("/etc/lksu/config.json").read_text())
        return data.get("report_language", "en")
    except (OSError, ValueError, TypeError, AttributeError):
        return "en"


def event(phase, message):
    try:
        if _language() == "tr":
            phase = _TR_PHASE.get(phase, phase)
            message = _TR_MESSAGES.get(message, message)
            for english, turkish in _TR_PREFIX.items():
                if message.startswith(english):
                    message = turkish + message[len(english):]
                    break
        print(f"LKSU [{phase}] {message}", file=sys.stderr, flush=True)
    except OSError:
        pass
