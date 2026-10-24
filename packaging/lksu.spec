Name:           lksu
Version:        0.2.0
Release:        1%{?dist}
Summary:        Conservative AlmaLinux kernel security updater
License:        MIT
URL:            https://github.com/KeygenLTD/linux-kernel-security-updater
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  python3-devel python3-setuptools
Requires:       python3 grubby dnf systemd

%description
Kernel advisory checks, policy-gated installation, one-shot trial boot,
health verification, reports, and optional fleet collection for AlmaLinux.

%prep
%autosetup

%build
%py3_build

%install
%py3_install
install -D -m 0644 systemd/lksu.service %{buildroot}%{_unitdir}/lksu.service
install -D -m 0644 systemd/lksu.timer %{buildroot}%{_unitdir}/lksu.timer
install -D -m 0644 systemd/lksu-maintenance.service %{buildroot}%{_unitdir}/lksu-maintenance.service
install -D -m 0644 systemd/lksu-maintenance.timer %{buildroot}%{_unitdir}/lksu-maintenance.timer
install -D -m 0644 systemd/lksu-verify.service %{buildroot}%{_unitdir}/lksu-verify.service

%files
%license LICENSE
%doc README.md SECURITY.md
%{python3_sitelib}/lksu*
%{_bindir}/lksu
%{_bindir}/lksu-fleet
%{_unitdir}/lksu*.service
%{_unitdir}/lksu*.timer

%changelog
* Sun Oct 25 2026 LKSU contributors - 0.2.0-1
- Initial RPM packaging preview
