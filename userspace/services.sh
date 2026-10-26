#!/bin/bash -e

# Enable DSP services
systemctl enable cdsp

# Enable our services
systemctl enable fs_setup.service
systemctl enable serial-hostname.service
systemctl enable comma.service
systemctl enable agnos-debug.service
systemctl enable gpio.service
systemctl enable ultimate_provisioning.service
systemctl enable lte.service
systemctl enable modem.service
systemctl enable sound.service
systemctl enable magic.service
systemctl enable init-qcom.service
systemctl enable wifi.service
systemctl enable varwatch.service
systemctl enable power_monitor.service
systemctl enable power_drop_monitor.service
systemctl enable brightnessd.service
systemctl enable ssh-param-watcher.path
systemctl enable ssh-param-watcher.service
systemctl enable adb-param-watcher.path
systemctl enable adb-param-watcher.service
systemctl enable avahi-daemon
systemctl enable avahi-ssh-publish.service
systemctl enable screen_calibration.service

# Disable SSH by default, ssh-param-watcher starts it
systemctl disable ssh ssh.socket

# Disable all useless systemctl services
systemctl disable apt-daily-upgrade.service
systemctl disable apt-daily.service
systemctl disable apt-daily-upgrade.timer
systemctl disable apt-daily.timer
systemctl disable serial-getty@ttyS0.service
systemctl disable remote-fs.target
systemctl disable remote-fs-pre.target
systemctl disable e2scrub_all.timer
systemctl disable fstrim.timer
systemctl disable motd-news.service
systemctl disable motd-news.timer
systemctl disable systemd-pstore.service
systemctl mask systemd-backlight@.service
systemctl mask alsa-restore.service
ln -s /dev/null /etc/udev/rules.d/90-alsa-restore.rules
systemctl disable dpkg-db-backup.timer
# The Ubuntu unit set differs between the AGNOS 19.8 and 20.2 base images
# (e.g. 20.2 no longer ships ua-reboot-cmds.service), so every disable for a
# stock unit must tolerate a missing unit. systemctl disable exits non-zero
# otherwise and the docker build fails.
disable_optional() {
  systemctl disable "$@" 2>/dev/null || true
}

disable_optional ua-reboot-cmds.service
disable_optional ubuntu-advantage.service
disable_optional update-notifier-download.timer
disable_optional update-notifier-download.service
disable_optional update-notifier-motd.timer
disable_optional update-notifier-motd.service
disable_optional man-db.timer

# Disable NFS stuff by default
disable_optional rpcbind
disable_optional dnsmasq.service
disable_optional nfs-client.target
disable_optional remote-fs-pre.target

# Service is from ifupdown but ifupdown is managed by NetworkManager
# networking service fails with "ifup: failed to bring up lo"
# no influence on any interface, all interfaces work fine
disable_optional networking.service

# TODO: this doesn't actually disable unless run twice...
# Service fails with Status: "No devices to monitor"
disable_optional smartd.service

disable_optional console-setup.service
disable_optional sfsconfig.service

# Opt-in native Bluetooth trial; inactive unless /data/bluetooth/ENABLED exists.
# Kept strict on purpose: if the unit is missing the image is broken and the
# build should fail loudly.
systemctl enable carrot-bluetooth-radio.service
disable_optional bluetooth.service
