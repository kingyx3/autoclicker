# Release and signing

## Verified in CI

- Android Kotlin sources compile; the debug APK is checked for MainActivity and TapService bytecode.
- Android API 35 emulator installs and launches the app, enables its Accessibility service, and captures a screenshot.
- iOS builds for Simulator without signing.
- Desktop model, script serialization, cancellation, and button-release tests run on Windows, macOS, and Linux. All three desktop archives build; the Linux executable opens under Xvfb.

These checks do not replace hands-on testing of Android gestures and stop controls on physical devices, signed install testing, macOS input permissions, or Windows and macOS GUI testing.

## Android release APK

Create a **durable release keystore on a machine you control** and back it up securely. Keep the same key for all future updates; losing it prevents updating installed APKs with the same package name.

```sh
keytool -genkeypair -v -keystore autoclicker-release.jks -alias autoclicker -keyalg RSA -keysize 3072 -validity 10000
```

In the GitHub repository's **Settings → Secrets and variables → Actions**, add:

| Secret | Value |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | Base64 encoding of the complete keystore file (one line) |
| `ANDROID_KEYSTORE_PASSWORD` | Keystore password |
| `ANDROID_KEY_ALIAS` | Alias, e.g. `autoclicker` |
| `ANDROID_KEY_PASSWORD` | Key password |

On macOS/Linux, generate the one-line value with `base64 < autoclicker-release.jks | tr -d '\n'`. Do not commit the keystore, paste it into a PR, or upload it as a public artifact.

After the PR is merged, run **Actions → Signed Android release → Run workflow** on the default branch. The workflow decodes the private keystore on the runner, builds the release APK, verifies its signature, and uploads `autoclicker-signed-release` with a SHA-256 checksum. It fails if any secret is missing. Install the signed APK on a physical Android device and check Accessibility enablement, point selection, hold and wait times, repetitions, cancellation, screen rotation, and save/load/delete before distributing it.

## Desktop and iOS

Windows builds are currently unsigned. Trusted Windows distribution needs an Authenticode signing certificate under the publisher's control. macOS builds are unsigned test bundles; broad distribution needs an Apple Developer ID signing identity and notarization. Neither certificate is stored in this repository.

The iOS project builds in Simulator, but installing on testers' iPhones needs Apple provisioning. Signing does not grant the iOS app permission to inject taps into other apps, so it is a script editor/preview rather than an iOS autoclicker.
