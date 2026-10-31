# LKSU — İşletim sistemi desteği ve güvenlik şartları

**Önemli:** Bir Linux dağıtımının algılanması, o sistemde otomatik kernel güncellemesinin desteklendiği anlamına **gelmez**. Şu anda otomatik kernel kurulumu ve kontrollü deneme açılışı yalnızca **AlmaLinux 8/9/10** için uygulanmıştır.

## Destek tablosu

| Dağıtım ailesi | Örnek sistemler | Paket yöneticisi | Otomatik kernel güncellemesi |
| --- | --- | --- | --- |
| RHEL | AlmaLinux, Rocky, RHEL, CentOS Stream, Oracle, Fedora, Amazon Linux | DNF/RPM | Yalnızca AlmaLinux 8/9/10 |
| CloudLinux | CloudLinux 8/9/10 | DNF/RPM ve üretici paketleri | Kapalı |
| Debian | Debian, Ubuntu, Mint, Pop!_OS, Proxmox | APT/DPKG | Kapalı |
| SUSE | openSUSE, SLES | Zypper/RPM | Kapalı |
| Arch | Arch, Manjaro, EndeavourOS | Pacman | Kapalı |
| Alpine | Alpine | APK | Kapalı |
| Gentoo | Gentoo | Portage | Kapalı |
| Nix | NixOS | Nix | Kapalı |
| Void | Void Linux | XBPS | Kapalı |

Bu liste bütün dağıtımları kapsamaz. Bir dağıtımın aynı aileden olması aynı kernel/önyükleme davranışını garanti etmez.

## Bir dağıtımda otomatik güncelleme açılmadan önce

1. Dağıtımın adı ve sürümü kesin belirlenmeli.
2. Yerel kernel paketleri ve güvenlik duyuruları doğrulanmalı.
3. Paket imzaları, depolar ve kurulu/çalışan kernel ayrı ayrı kontrol edilmeli.
4. Çalışan kernel, modülleri ve geri dönüş kerneli korunmalı.
5. BIOS/UEFI, GRUB, Secure Boot ve sağlayıcıya özel açılış koşulları test edilmeli.
6. Harici snapshot ve sağlayıcının kurtarma konsolu doğrulanmalı.
7. Servis, ağ ve depolama sağlık kontrolleri çalışmalı.
8. Yeniden başlatma sonrası kernel ve servisler doğrulanmalı.
9. Gerçek, izole sanal makinelerde başarılı/başarısız güncelleme ve geri dönüş testleri geçmeli.
10. Sadece algılama desteği eklenmesi otomatik kernel değişikliğini **asla** etkinleştirmemeli.

## CloudLinux için özel uyarı

CloudLinux'un kernel ve LVE modül bağımlılıkları sürüme göre farklılaşabilir. LKSU genel bir AlmaLinux kernelini CloudLinux kernelinin yerine otomatik geçirmemeli veya LVE modüllerini gelişigüzel silmemelidir. Kernel sürümünün eşleşmesi, LVE ve uygulama uyumluluğunun kanıtı değildir.

[CloudLinux'un resmî kernel belgesi](https://docs.cloudlinux.com/cloudlinuxos/cloudlinux_os_kernel/)

## Sürüm yayımlama ve CVE doğrulaması

Tüm dağıtımlar için kurulum, deneme açılışı, yeniden başlatma sonrası kontrol ve geri dönüş testleri yapılmadan **v1.0.0 tam destek** iddiasında bulunulmayacak. Bir CVE'nin giderildiği ancak üreticinin güvenlik duyurusu, kurulu paket ve **çalışan düzeltilmiş kernel** birlikte doğrulandığında raporlanacak.

[🇹🇷 Türkçe README](../README.tr.md) · [🇬🇧 English platform support](platform-support.md)
