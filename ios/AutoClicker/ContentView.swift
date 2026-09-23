import SwiftUI

struct TapStep: Codable, Identifiable {
    var id = UUID()
    var x: Int
    var y: Int
    var radius: Int
    var holdMs: Int
    var waitMs: Int
}
struct TapScript: Codable, Identifiable {
    var id = UUID()
    var name: String
    var repetitions: Int
    var steps: [TapStep]
}
@MainActor
final class ScriptLibrary: ObservableObject {
    @Published var scripts: [TapScript] = [] {
        didSet { persist() }
    }
    init() {
        if let data = UserDefaults.standard.data(forKey: "scripts"),
           let decoded = try? JSONDecoder().decode([TapScript].self, from: data) {
            scripts = decoded
        }
    }
    func save(_ script: TapScript) {
        scripts.removeAll { $0.name == script.name }
        scripts.append(script)
    }
    private func persist() {
        if let data = try? JSONEncoder().encode(scripts) {
            UserDefaults.standard.set(data, forKey: "scripts")
        }
    }
}
struct ContentView: View {
    @StateObject private var library = ScriptLibrary()
    @State private var name = ""
    @State private var repetitions = "1"
    @State private var x = ""
    @State private var y = ""
    @State private var radius = "24"
    @State private var hold = "60"
    @State private var wait = "500"
    @State private var steps: [TapStep] = []
    @State private var error: String?
    @State private var active: TapStep?
    @State private var playback: Task<Void, Never>?
    @State private var progress = "Idle"

    var body: some View {
        NavigationStack {
            Form {
                Section("Platform capability") {
                    Text("iOS can edit and preview scripts here. Apps cannot inject touches into other apps with public iOS APIs. Preview markers do not trigger taps.")
                        .font(.footnote)
                }
                Section("Saved scripts") {
                    ForEach(library.scripts) { script in
                        Button(script.name) { load(script) }
                    }
                    .onDelete { library.scripts.remove(atOffsets: $0) }
                }
                Section("Script") {
                    TextField("Name", text: $name)
                    TextField("Repetitions (1–10000)", text: $repetitions).keyboardType(.numberPad)
                }
                Section("Steps in order") {
                    ForEach(steps) { step in
                        Text("(\(step.x), \(step.y)) · radius \(step.radius)px · hold \(step.holdMs)ms · wait \(step.waitMs)ms")
                    }
                    .onDelete { steps.remove(atOffsets: $0) }
                    number("X pixel", $x)
                    number("Y pixel", $y)
                    number("Marker radius in pixels", $radius)
                    number("Hold duration in ms", $hold)
                    number("Wait after tap in ms", $wait)
                    Button("Add step") { addStep() }
                }
                Section {
                    Button("Save on this device") {
                        if let script = validated() { library.save(script); progress = "Saved" }
                    }
                    Button("Preview sequence") {
                        if let script = validated() { startPreview(script) }
                    }
                    Button("Stop preview") { stopPreview() }
                }
                Section("In-app preview") {
                    GeometryReader { geometry in
                        ZStack {
                            Color(.secondarySystemBackground)
                            if let step = active {
                                Circle()
                                    .fill(.blue.opacity(0.3))
                                    .overlay(Circle().stroke(.blue, lineWidth: 2))
                                    .frame(width: CGFloat(step.radius * 2), height: CGFloat(step.radius * 2))
                                    .position(x: min(CGFloat(step.x), geometry.size.width),
                                              y: min(CGFloat(step.y), geometry.size.height))
                            }
                        }
                    }.frame(height: 250).accessibilityLabel("Preview target markers")
                    Text(progress).font(.footnote)
                    Text("Coordinates are screen pixels on Android; the iOS preview uses the same values inside this panel and clips larger positions.")
                        .font(.footnote)
                }
            }
            .navigationTitle("AutoClicker")
            .alert("Check script", isPresented: Binding(
                get: { error != nil }, set: { if !$0 { error = nil } }
            )) { Button("OK") { error = nil } } message: { Text(error ?? "") }
        }
    }
    private func number(_ title: String, _ binding: Binding<String>) -> some View {
        TextField(title, text: binding).keyboardType(.numberPad)
    }
    private func addStep() {
        guard let xx = Int(x), let yy = Int(y), let r = Int(radius),
              let h = Int(hold), let w = Int(wait),
              xx >= 0, yy >= 0, (1...200).contains(r),
              (1...60000).contains(h), (0...600000).contains(w), steps.count < 100
        else { error = "Enter valid coordinates and timing. Maximum 100 steps."; return }
        steps.append(TapStep(x: xx, y: yy, radius: r, holdMs: h, waitMs: w))
    }
    private func validated() -> TapScript? {
        guard !name.trimmingCharacters(in: .whitespaces).isEmpty,
              let count = Int(repetitions), (1...10000).contains(count), !steps.isEmpty
        else { error = "Enter a name, 1–10000 repetitions and at least one step."; return nil }
        return TapScript(name: name.trimmingCharacters(in: .whitespaces), repetitions: count, steps: steps)
    }
    private func load(_ script: TapScript) {
        stopPreview()
        name = script.name
        repetitions = String(script.repetitions)
        steps = script.steps
    }
    private func stopPreview() {
        playback?.cancel()
        playback = nil
        active = nil
        progress = "Stopped"
    }
    private func startPreview(_ script: TapScript) {
        stopPreview()
        progress = "Previewing"
        playback = Task {
            for loop in 0..<script.repetitions {
                for step in script.steps {
                    if Task.isCancelled { return }
                    active = step
                    do {
                        try await Task.sleep(nanoseconds: UInt64(step.holdMs) * 1_000_000)
                        active = nil
                        try await Task.sleep(nanoseconds: UInt64(step.waitMs) * 1_000_000)
                    } catch { return }
                }
                progress = "Completed \(loop + 1) of \(script.repetitions)"
            }
            playback = nil
        }
    }
}
