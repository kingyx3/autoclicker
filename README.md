# AutoClicker

A local script editor for Android and iOS. Android can replay user-authored taps over other apps after the user explicitly enables the Accessibility service. iOS can save scripts and preview their timing and target markers **inside this app only**. Public iOS app APIs do not provide an equivalent system-wide touch injector; installing outside the App Store does not change that capability.

## Build and install

### Android (APK, no Play Store)

Open the repository in Android Studio (JDK 17, Android SDK 35) and build the `app` module, or run `gradle :app:assembleDebug` with Gradle 8.9. The debug APK is at `app/build/outputs/apk/debug/app-debug.apk`. Install it on your own device with `adb install -r app-debug.apk` or open the APK on the device and approve the OS install prompt. Release distribution requires signing with your own key; do not ship a debug signed APK to others.

Launch the app and select **Enable tap service**. In Android Accessibility settings, enable **AutoClicker taps**. Define screen pixel positions and timings, add steps, name the script, save it, then tap **Run script**. Switch to the desired app during the five second countdown. A floating **STOP TAPS** button remains available during playback. Disabling the Accessibility service also stops playback. No network, account, or root access is required.

### iOS (without App Store listing)

On a Mac with Xcode and [XcodeGen](https://github.com/yonaskolb/XcodeGen), run `cd ios && xcodegen generate`, open `AutoClicker.xcodeproj`, choose your signing team, and run it on your own registered iPhone. Xcode's Personal Team can provision personal testing devices, with periodic reprovisioning. Ad hoc distribution to registered devices requires suitable Apple Developer Program signing. Regional alternative distribution has additional Apple requirements. This repository does not provide a signed IPA or public installer.

### Desktop (Windows, macOS, Linux X11)

Download the platform-specific archive from the **Desktop builds** workflow on the PR's Actions page (artifacts expire after 30 days), or install Python 3.12 and run:

```sh
python -m pip install -r desktop/requirements.txt
python desktop/main.py
```

On Windows, unzip `autoclicker-windows` and launch `AutoClicker.exe`. On macOS, unzip `autoclicker-macos` and open `AutoClicker.app`; the unsigned test build may require manual approval in Privacy & Security and Accessibility/Input Monitoring permissions. On Linux, unpack `autoclicker-linux-x11`, run `./AutoClicker`, and use an X11 session. Wayland generally prevents this app's global mouse and keyboard input.

Hover over a target and press **F8** to capture its desktop pixel coordinates; add each step, then save a named script. **F9** stops even when the target app has focus. The app waits three seconds before starting. Set hold to **0 ms** and wait to **0 ms** for the fastest requested loop; actual click rate depends on the OS, hardware, and target app. The marker radius is a saved visual reference and does not change the click's physical footprint. The app uses standard synthetic input, which target apps may recognize. No detection bypass is implemented.

## Script behavior

Each script has a name, 1–10,000 repetitions, and 1–100 ordered steps. Each step contains absolute screen pixel `x`/`y`, marker radius (1–200 pixels), hold duration (1–60,000 ms), and wait **after** the tap (0–600,000 ms). Repetitions run the entire sequence. Android schedules the next tap only after the gesture completion callback and the specified wait. OS scheduling can add latency, so timings are requested values, not hard real-time guarantees. Android validates points against the current screen size before starting; rotate or resize the display and recheck your coordinates. Touch radius changes the visible marker only; injected taps have a single center coordinate.

Scripts are saved locally in private app storage. Deleting the app removes them. The iOS preview draws markers within a 250-point panel, clips positions outside that panel, and never synthesizes touch events. Both editors support adding and removing steps, saving, loading and deleting scripts; there is currently no cross-device sync or export.

## Implementation brief (improved prompt)

> Build a privacy-preserving autoclicker with Android and iOS apps. Let users create named, locally saved scripts containing ordered tap positions, visual marker radii, per-step hold durations and post-tap delays in milliseconds, and a finite repetition count. Provide editing, validation, load/delete, an explicit start countdown, progress or preview, and an immediately accessible stop control. On Android, use a user-enabled AccessibilityService with `dispatchGesture` and an accessibility overlay stop button; never start automatically or request network access. Validate bounds and timing, serialize gesture callbacks, and cancel pending work on stop or service teardown. On iOS, implement only script editing and in-app timing preview because public APIs cannot inject global touches; explain that limitation clearly in the UI. Document sideload build and signing steps for each platform, do not claim that an unsigned IPA is installable, and add build verification. Avoid stealth automation, credential interception, and hidden background behavior.

## Verification

`gradle :app:assembleDebug` builds the Android app. For iOS, generate the Xcode project and build with your signing team in Xcode. Device-level gesture and provisioning checks require physical devices. CI builds Android and iOS, and packages desktop artifacts on Windows, macOS, and Linux. Desktop model and cancellation tests run on all three runners.
