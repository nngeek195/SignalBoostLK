#!/usr/bin/env bash
set -euo pipefail

APP_NAME="signalboostlk"
VERSION="2.0.0"
ARCH="amd64"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$PROJECT_DIR/build/deb"
PACKAGE_DIR="$BUILD_DIR/package"
DIST_DIR="$PROJECT_DIR/dist"

echo "Building SignalBoostLK Linux application..."

cd "$PROJECT_DIR"

source .venv/bin/activate

pip install -r requirements.txt

rm -rf build dist
mkdir -p "$PACKAGE_DIR/DEBIAN"
mkdir -p "$PACKAGE_DIR/opt/signalboostlk"
mkdir -p "$PACKAGE_DIR/usr/bin"
mkdir -p "$PACKAGE_DIR/usr/share/applications"

# Build standalone executable
pyinstaller \
    --noconfirm \
    --clean \
    --onefile \
    --windowed \
    --name SignalBoostLK \
    --add-data "app/ui/assets:app/ui/assets" \
    --add-data "app/config:app/config" \
    main.py

# Install executable into package
cp "$DIST_DIR/SignalBoostLK" \
   "$PACKAGE_DIR/opt/signalboostlk/SignalBoostLK"

chmod 755 "$PACKAGE_DIR/opt/signalboostlk/SignalBoostLK"

# Launcher
cat > "$PACKAGE_DIR/usr/bin/signalboostlk" <<'EOF'
#!/bin/sh
exec /opt/signalboostlk/SignalBoostLK "$@"
EOF

chmod 755 "$PACKAGE_DIR/usr/bin/signalboostlk"

# Desktop application entry
cat > "$PACKAGE_DIR/usr/share/applications/signalboostlk.desktop" <<'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=SignalBoostLK
Comment=Lightweight ISP connection keeper for Sri Lankan ISPs
Exec=/usr/bin/signalboostlk
Icon=network-wireless
Terminal=false
Categories=Network;Utility;
StartupNotify=true
EOF

# Debian package metadata
cat > "$PACKAGE_DIR/DEBIAN/control" <<EOF
Package: signalboostlk
Version: $VERSION
Section: net
Priority: optional
Architecture: $ARCH
Maintainer: Niranga Nayanajith
Depends: libc6, libstdc++6, libgl1, libxkbcommon0, libxcb-cursor0
Description: SignalBoostLK ISP connection keeper
 Keeps a lightweight HTTPS connection to the selected Sri Lankan ISP's
 Ookla server and reconnects when it closes. Does not run speed tests.
EOF

dpkg-deb --build --root-owner-group \
    "$PACKAGE_DIR" \
    "$PROJECT_DIR/${APP_NAME}_${VERSION}_${ARCH}.deb"

echo ""
echo "Build completed!"
echo "Package: ${APP_NAME}_${VERSION}_${ARCH}.deb"
