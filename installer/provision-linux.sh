set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates wget gnupg
wget -qO /etc/apt/trusted.gpg.d/openfoam.asc https://dl.openfoam.org/gpg.key
printf 'deb [arch=amd64] http://dl.openfoam.org/ubuntu noble main\n' > /etc/apt/sources.list.d/openfoam-friend.list
apt-get update
apt-get install -y --no-install-recommends openfoam14 openmpi-bin gmsh
id off >/dev/null 2>&1 || useradd -m -s /bin/bash off
mkdir -p /home/off/OpenFOAM/off14/run
chown -R off:off /home/off/OpenFOAM
printf '\nsource /opt/openfoam14/etc/bashrc\n' >> /home/off/.bashrc
printf '[boot]\nsystemd=false\n[user]\ndefault=off\n' > /etc/wsl.conf
mkdir -p /etc/openfoamfriend
printf 'Open Foam Friend clean environment\nUbuntu 24.04 / OpenFOAM Foundation 14\nNo personal files or research cases included.\n' > /etc/openfoamfriend/build-info
set +u
source /opt/openfoam14/etc/bashrc
foamRun -help > /etc/openfoamfriend/foamRun-help.txt
blockMesh -help > /etc/openfoamfriend/blockMesh-help.txt
mpirun --version > /etc/openfoamfriend/mpi-version.txt
gmsh -version > /etc/openfoamfriend/gmsh-version.txt 2>&1
dpkg-query -W > /etc/openfoamfriend/packages.tsv
apt-get clean
