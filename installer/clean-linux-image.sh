set -eu
grep -q 'Open Foam Friend clean environment' /etc/openfoamfriend/build-info
test -z "$(find /home/off/OpenFOAM/off14/run -mindepth 1 -print -quit)"
# This script is run only inside the dedicated package-build distribution.
rm -f /etc/ssh/ssh_host_* /home/ubuntu/.ssh/authorized_keys /root/.bash_history /home/off/.bash_history
truncate -s 0 /etc/machine-id
find /var/log -type f -exec truncate -s 0 {} \;
printf 'localhost\n' > /etc/hostname
printf '127.0.0.1 localhost\n::1 localhost\n' > /etc/hosts
rm -f /etc/resolv.conf
printf '[boot]\nsystemd=false\n[user]\ndefault=off\n' > /etc/wsl.conf
sync
