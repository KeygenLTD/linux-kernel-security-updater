# E-posta bildirimleri ve SMTP yapılandırması

LKSU operasyon raporlarını SMTP ile gönderir. Kurulumda alıcı e-posta adresi, sağlayıcı, kimlik bilgileri, güncelleme tercihleri ve sağlık kontrolleri sorulur.

> [!IMPORTANT]
> Bu belge **main dalındaki mevcut uygulamayı** anlatır. Geliştirme dalındaki özellikler farklı olabilir. SMTP şifrelerini veya tam yapılandırma dosyasını GitHub issue'larına eklemeyin.

## İlk kurulum

Kurulum betiğini inceledikten sonra `sudo lksu configure` çalıştırın.

| Sağlayıcı | Sunucu | Port | Giriş bilgisi |
| --- | --- | --- | --- |
| Postmark | `smtp.postmarkapp.com` | 587 | Server Token, kullanıcı adı ve şifre olarak |
| SMTP2GO | `mail.smtp2go.com` | 587 | SMTP kullanıcı adı ve şifresi |
| Özel SMTP | Sağlayıcınızın verdiği sunucu | Varsayılan 465; gerekirse sağlayıcının portu | SMTP kullanıcı adı ve şifre/uygulama şifresi |

**Report email** alıcı adresidir. Mevcut kurulumda `from_email` başlangıçta aynı adres olarak kaydedilir. Sağlayıcınız doğrulanmış gönderici veya alan adı isteyebilir.

## Yapılandırma dosyası

`/etc/lksu/config.json` içinde SMTP ayarları **üst düzey anahtarlardır**; iç içe `smtp` nesnesi kullanılmaz.

| Anahtar | Açıklama |
| --- | --- |
| `email` | Alıcı adresi |
| `from_email` | Gönderen adresi |
| `smtp_host` | SMTP sunucusu |
| `smtp_port` | SMTP portu |
| `smtp_user` | SMTP kullanıcı adı |
| `smtp_password` | Şifre veya token |
| `notifications` | Olay e-postası tercihi |

Şifreleri issue, ekran görüntüsü veya loglarda paylaşmayın. Dosya yalnızca root tarafından okunmalı: `chmod 600 /etc/lksu/config.json`.

## Şifreli bağlantı

Kod, **465** portunda doğrudan TLS (`SMTP_SSL`), diğer portlarda önce bağlantı ardından zorunlu **STARTTLS** kullanır. Şifresiz SMTP'ye otomatik geri dönüş yapılmaz.

## Ne zaman e-posta gönderilir?

Kurulumdaki **“Email only when updates succeed or fail?”** tercihi güncelleme olayları için bildirimleri yönetir. Her 15 dakikalık salt okunur kontrolün e-posta gönderdiğini varsaymayın. Gerçek teslimatı sağlayıcı kayıtlarından doğrulayın.

## Sık karşılaşılan sorunlar

<details>
<summary>SMTP kullanıcı adı veya şifre hatalı</summary>

Token/uygulama şifresini, hesap durumunu ve doğrulanmış gönderici adresini kontrol edin. Gizli bilgileri paylaşmayın.

</details>

<details>
<summary>Bağlantı zaman aşımı veya TLS hatası</summary>

DNS, sunucu çıkış güvenlik duvarı, port ve sağlayıcının TLS/STARTTLS gereksinimlerini kontrol edin. Sertifika doğrulamasını kapatmayın.

</details>

<details>
<summary>Gönderildi deniyor ama e-posta gelmiyor</summary>

SMTP sağlayıcısının teslimat kayıtlarını, spam klasörünü, gönderen alan adı doğrulamasını ve SPF/DKIM/DMARC kayıtlarını kontrol edin. SMTP kabulü, gelen kutusuna teslim garantisi değildir.

</details>

<details>
<summary>Mevcut sunucuda SMTP ayarlarını nasıl değiştiririm?</summary>

Main dalındaki CLI'da ayrı bir SMTP yeniden yapılandırma komutu yoktur. Güvenli yedek alıp yalnızca root'un erişebildiği JSON dosyasını dikkatle düzenleyin. `configure` komutu kernel otomasyon ayarlarını da yeniden sorar.

</details>

## Güvenli kontrol

Şifreleri ekrana yazdırmadan JSON sözdizimini ve dosya izinlerini kontrol edin:

```bash
sudo python3 -m json.tool /etc/lksu/config.json >/dev/null
sudo stat -c '%a %U:%G' /etc/lksu/config.json
```

Bu komutlar gerçek SMTP teslimatını test etmez. Uçtan uca doğrulama için yetkili bir operasyon olayı ve sağlayıcı teslimat kayıtları gerekir; yalnızca e-postayı test etmek için canlı sunucuda kernel güncellemesi başlatmayın.
