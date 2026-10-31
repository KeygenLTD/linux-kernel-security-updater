<div align="center">

# 🛡️ LKSU
### Linux Kernel Güvenlik Güncelleyicisi

**Otomatik kontrol. Güvenli kernel güncellemesi. Doğrulanabilir geri dönüş.**

[🇹🇷 Türkçe](README.tr.md) · [🇬🇧 English](README.md) · [İşletim sistemi desteği](docs/platform-support.md)

![LKSU işleyişi](docs/assets/lksu-hero.png)

![Sürüm](https://img.shields.io/badge/geliştirme-0.3.23.dev0-blue)
![AlmaLinux](https://img.shields.io/badge/AlmaLinux-8%20%7C%209%20%7C%2010-168B4C)
![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB)

</div>

## LKSU ne yapar?

| 🔍 Kontrol | 🛠️ Güncelleme | 🧪 Doğrulama | ↩️ Geri dönüş |
| :---: | :---: | :---: | :---: |
| **7/24, 15 dakikada bir** kontrol | İzin verildiğinde resmî depolardaki uygun kernel paketlerini kurar | Deneme açılışından sonra kernel ve servisleri denetler | Önceki kerneli korur, geri dönüşe yardımcı olur |

**Diğer özellikler:** Türkçe/İngilizce olay e-postaları, sunucuya özel görünen ad, Security Watch, kontrollü eski kernel temizliği ve isteğe bağlı LKSU sürüm kontrolü.

> **Geliştirme durumu:** Depodaki sürüm `0.3.23.dev0`. Testlerin geçmesi bütün üretim ortamlarında güvenli çalışacağı anlamına gelmez. Otomatik yeniden başlatmadan önce harici snapshot ve sağlayıcı konsol erişimini doğrulayın.

## Hangi sistemlerde çalışır?

| İşletim sistemi | Kernel güncellemesi / kontrollü yeniden başlatma |
| --- | --- |
| **AlmaLinux 8, 9, 10** | Uygulandı; canlı kullanımdan önce kendi ortamınızda doğrulayın |
| Rocky Linux, RHEL, CloudLinux | Algılama ve salt okunur envanter; otomatik kernel değişikliği engelli |
| Ubuntu, Debian | Algılama ve salt okunur envanter; otomatik kernel değişikliği engelli |
| Diğer algılanabilen Linux sistemleri | Desteklenen yerlerde yalnızca algılama |

Ayrıntılar: [Platform ve güvenlik matrisi](docs/platform-support.md). **Algılanması, güncellemenin desteklendiği anlamına gelmez.**

## Kurulum

Önce **test sunucusunda** deneyin. [Kurulum betiğini](install.sh) inceleyip depoyu indirdikten sonra:

```bash
sudo ./install.sh
sudo lksu configure
lksu active
```

Kurulum seçenekleri **gerçek kernel kurulumu ve yeniden başlatma** yetkisi verebilir. Kritik sunucuda önce snapshot, kurtarma konsolu ve servis sağlık kontrollerini hazırlayın.

[Bootstrap betiği](bootstrap.sh) hâlen **v0.3.22** sürümüne sabitlenmiştir; geliştirme sürümünü kurmaz.

## Sık kullanılan komutlar

```bash
lksu active                   # Genel durum
lksu check --json             # Salt okunur kernel kontrolü
lksu compatibility --json     # İşletim sistemi yetenekleri
lksu kernel-inventory --json  # Salt okunur paket envanteri
lksu configure-automation     # Otomatik kurulum/yeniden başlatma
lksu configure-server-name    # Raporlarda görünen sunucu adı
```

## Güvenlik ilkeleri

- Kernel paketleri dağıtımın etkin resmî depolarından alınır.
- CyberPanel veya sistem Python ortamı değiştirilmemelidir; LKSU ayrı Python ortamı kullanmalıdır.
- Deneme açılışı ve sağlık kontrolleri riski azaltır, **her açılış hatasından kurtulmayı garanti etmez**.
- `/boot` hesabı **150 MiB taban rezerv + tahmini kernel/initramfs ihtiyacını** kullanır; her özel disk düzeni için kesin garanti değildir.
- LKSU'nun kendi güncellemeleri doğrulanmış sürüm dosyaları ve yönetilen sürüm dizinlerini kullanır. **Geliştirme/eski kurulumlarda otomatik self-update geçiş yapılana kadar engellenir.**
- **Zero-Day Shield plan aşamasındadır; henüz CVE için otomatik geçici koruma uygulamaz.**

## Belgeler

[Platform desteği](docs/platform-support.md) · [Önceki ayrıntılı README (arşiv)](docs/README-legacy.md) · [Kaynak kod](src/lksu/) · [Hata ve öneriler](https://github.com/KeygenLTD/linux-kernel-security-updater/issues)

**Not:** Bir CVE'nin kapatıldığını söylemek için üreticinin ilgili düzeltmesinin kurulması, düzeltilmiş kernelin çalışması ve doğrulama gerekir. Geçici önlem, yamanın yerini tutmaz.
