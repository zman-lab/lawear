#!/bin/bash
set -euo pipefail

# ── 설정 ──────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WEB_DIR="$PROJECT_DIR/web"
FTP_BASE="http://127.0.0.1:8585/api/files"
FTP_UPLOAD_DIR="zman-lab/lawear"
GH_REPO="zman-lab/lawear"

# ── 버전 읽기 (version.ts에서) ────────────────────────────────
VERSION_FILE="$WEB_DIR/src/version.ts"
if [[ ! -f "$VERSION_FILE" ]]; then
  echo "ERROR: $VERSION_FILE not found"
  exit 1
fi

APP_VERSION=$(grep "APP_VERSION" "$VERSION_FILE" | sed "s/.*'\(.*\)'.*/\1/")
BUILD_DATE=$(grep "BUILD_DATE" "$VERSION_FILE" | sed "s/.*'\(.*\)'.*/\1/")

echo "=== LawEar Deploy ==="
echo "Version: $APP_VERSION"
echo "Build Date: $BUILD_DATE"
echo ""

# ── APK 빌드 ─────────────────────────────────────────────────
echo "[1/5] Building web..."
cd "$WEB_DIR"
npx vite build

echo "[2/5] Syncing to Android..."
npx cap sync android

echo "[3/5] Building APK..."
cd "$WEB_DIR/android"
./gradlew assembleDebug

APK_SRC="$WEB_DIR/android/app/build/outputs/apk/debug/app-debug.apk"
if [[ ! -f "$APK_SRC" ]]; then
  echo "ERROR: APK not found at $APK_SRC"
  exit 1
fi

# ── FTP 업로드 ────────────────────────────────────────────────
APK_NAME="lawear-${APP_VERSION}.apk"
APK_LATEST="lawear-latest.apk"

echo "[4/5] Uploading to FTP..."

# APK 업로드 (버전 이름)
curl -sf -X POST "${FTP_BASE}/upload" \
  -F "path=${FTP_UPLOAD_DIR}" \
  -F "files=@${APK_SRC};filename=${APK_NAME}" \
  || { echo "ERROR: Failed to upload ${APK_NAME}"; exit 1; }
echo "  Uploaded: ${APK_NAME}"

# APK 업로드 (latest)
curl -sf -X POST "${FTP_BASE}/upload" \
  -F "path=${FTP_UPLOAD_DIR}" \
  -F "files=@${APK_SRC};filename=${APK_LATEST}" \
  || { echo "ERROR: Failed to upload ${APK_LATEST}"; exit 1; }
echo "  Uploaded: ${APK_LATEST}"

# latest.json 생성 및 업로드
echo "[5/5] Uploading latest.json..."
LATEST_JSON=$(cat <<EOF
{"version":"${APP_VERSION}","buildDate":"${BUILD_DATE}","downloadUrl":"http://127.0.0.1:8585/ftp/zman-lab/lawear/","changelog":""}
EOF
)

TMPFILE=$(mktemp /tmp/latest.json.XXXXXX)
echo "$LATEST_JSON" > "$TMPFILE"

curl -sf -X POST "${FTP_BASE}/upload" \
  -F "path=${FTP_UPLOAD_DIR}" \
  -F "files=@${TMPFILE};filename=latest.json" \
  || { echo "ERROR: Failed to upload latest.json"; exit 1; }
rm -f "$TMPFILE"
echo "  Uploaded: latest.json"

# ── GitHub Release ──────────────────────────────────────────
echo "[6/6] GitHub Release..."
TAG="v${APP_VERSION}"

# 이미 있는 릴리즈면 APK만 덮어쓰기, 없으면 새로 생성
if GH_HOST=github.com gh release view "$TAG" --repo "$GH_REPO" > /dev/null 2>&1; then
  # 기존 APK 삭제 후 재업로드
  GH_HOST=github.com gh release delete-asset "$TAG" "$APK_NAME" --repo "$GH_REPO" -y 2>/dev/null || true
  GH_HOST=github.com gh release upload "$TAG" "${APK_SRC}#${APK_NAME}" --repo "$GH_REPO"
  echo "  Updated: ${TAG}"
else
  GH_HOST=github.com gh release create "$TAG" "${APK_SRC}#${APK_NAME}" \
    --repo "$GH_REPO" \
    --title "${TAG}" \
    --notes "lawear ${TAG} (${BUILD_DATE})"
  echo "  Created: ${TAG}"
fi

GH_RELEASE_URL="https://github.com/${GH_REPO}/releases/tag/${TAG}"

echo ""
echo "=== Deploy Complete ==="
echo "FTP APK: ${FTP_BASE}/download/${FTP_UPLOAD_DIR}/${APK_NAME}"
echo "FTP Latest: ${FTP_BASE}/download/${FTP_UPLOAD_DIR}/${APK_LATEST}"
echo "GitHub: ${GH_RELEASE_URL}"
