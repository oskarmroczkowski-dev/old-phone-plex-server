#!/usr/bin/env bash
# Builds the "Server Status" app without Gradle (Git Bash on Windows, JDK 17, Android SDK).
# Output: server-status.apk in this folder.
# Install on the phone: adb -s <phone> install -r server-status.apk
# Bump VERSION_CODE whenever you change the code, otherwise Android will not update the app.
# The signing key is created on the first build in keystore/ (gitignored). KEEP IT: updates need the same key.
set -euo pipefail
cd "$(dirname "$0")"

VERSION_CODE=7
VERSION_NAME=1.3.3
SDK="${ANDROID_SDK:-$(cygpath -u "$LOCALAPPDATA")/Android/Sdk}"
BT="$SDK/build-tools/36.0.0"
PLAT="$SDK/platforms/android-36/android.jar"
W() { cygpath -w "$1"; }

rm -rf build
mkdir -p build/gen build/classes build/dex

echo "1/6 resources"
"$BT/aapt2" compile --dir res -o build/res.zip
"$BT/aapt2" link -o build/base.apk -I "$(W "$PLAT")" --manifest AndroidManifest.xml \
  --java build/gen build/res.zip --min-sdk-version 30 --target-sdk-version 33 \
  --version-code "$VERSION_CODE" --version-name "$VERSION_NAME"

echo "2/6 compile Java"
# no lambdas in the code: android.jar has no LambdaMetafactory, javac fails on them
javac -encoding UTF-8 -source 8 -target 8 -Xlint:-options -bootclasspath "$(W "$PLAT")" \
  -d build/classes $(find src build/gen -name '*.java')

echo "3/6 dex"
java -cp "$(W "$BT/lib/d8.jar")" com.android.tools.r8.D8 --release --min-api 30 \
  --lib "$(W "$PLAT")" --output build/dex $(find build/classes -name '*.class')

echo "4/6 package"
python - <<'EOF'
import zipfile
with zipfile.ZipFile('build/base.apk', 'a', zipfile.ZIP_DEFLATED) as z:
    z.write('build/dex/classes.dex', 'classes.dex')
EOF
"$BT/zipalign" -f -p 4 build/base.apk build/aligned.apk

echo "5/6 signing key"
if [ ! -f keystore/status.jks ]; then
  mkdir -p keystore
  python -c "import secrets; print(secrets.token_urlsafe(24))" > keystore/password.txt
  keytool -genkeypair -keystore keystore/status.jks -storepass:file keystore/password.txt -keypass:file keystore/password.txt \
    -alias status -keyalg RSA -keysize 2048 -validity 36500 -dname "CN=Server Status, O=Home" >/dev/null
fi

echo "6/6 sign"
# one password for keystore and key: pass only --ks-pass (apksigner would read a 2nd line for --key-pass from the same file)
java -jar "$(W "$BT/lib/apksigner.jar")" sign --ks keystore/status.jks --ks-pass file:keystore/password.txt \
  --out server-status.apk build/aligned.apk
java -jar "$(W "$BT/lib/apksigner.jar")" verify server-status.apk
echo "Done: $(pwd)/server-status.apk ($(stat -c %s server-status.apk) B)"
