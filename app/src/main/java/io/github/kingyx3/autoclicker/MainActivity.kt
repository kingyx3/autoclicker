package io.github.kingyx3.autoclicker

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.graphics.Typeface
import android.view.View
import android.widget.*
import android.text.InputType

class MainActivity : Activity() {
    private lateinit var body: LinearLayout
    private lateinit var store: ScriptStore
    private lateinit var name: EditText
    private lateinit var repeats: EditText
    private lateinit var x: EditText
    private lateinit var y: EditText
    private lateinit var radius: EditText
    private lateinit var hold: EditText
    private lateinit var wait: EditText
    private lateinit var stepsView: LinearLayout
    private val steps = mutableListOf<Step>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store = ScriptStore(this)
        val scroll = ScrollView(this)
        body = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 32, 32, 48)
        }
        scroll.addView(body)
        setContentView(scroll)
        label("AutoClicker", true)
        label("Android: enable the tap service, then start a saved script. A five second countdown lets you switch apps. Use the floating STOP button to end playback.")
        button("Enable tap service") { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        button("Load saved script") {
            val saved = store.all()
            if (saved.isEmpty()) { message("No saved scripts yet"); return@button }
            val titles = saved.map { it.name }.toTypedArray()
            android.app.AlertDialog.Builder(this).setTitle("Saved scripts").setItems(titles) { _, index ->
                val script = saved[index]
                name.setText(script.name)
                repeats.setText(script.repetitions.toString())
                steps.clear(); steps.addAll(script.steps); renderSteps()
            }.show()
        }
        name = field("Script name", "My script", false)
        repeats = field("Repetitions (1–10000)", "1").apply { setText("1") }
        label("Tap steps (screen pixels, in order)", true)
        stepsView = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        body.addView(stepsView)
        x = field("X pixel", "300")
        y = field("Y pixel", "600")
        radius = field("Marker radius in pixels (1–200)", "24").apply { setText("24") }
        hold = field("Hold duration in ms (1–60000)", "60").apply { setText("60") }
        wait = field("Wait after tap in ms (0–600000)", "500").apply { setText("500") }
        button("Add tap step") {
            val step = runCatching { Step(x.number(), y.number(), radius.number(), hold.number().toLong(), wait.number().toLong()) }.getOrNull()
            if (step == null || steps.size >= 100) message("Check step values (maximum 100 steps)")
            else { steps.add(step); renderSteps() }
        }
        button("Save script") {
            val script = buildScript() ?: return@button
            store.save(script); message("Saved locally: " + script.name)
        }
        button("Run script") {
            val script = buildScript() ?: return@button
            val service = TapService.current
            if (service == null) message("Enable AutoClicker taps in Accessibility settings first")
            else if (service.start(script)) message("Starting in five seconds. Switch to your target app.")
            else message("Already running, or a coordinate is outside the screen")
        }
        button("Stop playback") { TapService.current?.stop() }
        button("Delete named script") {
            if (name.text.isNotBlank()) {
                android.app.AlertDialog.Builder(this).setMessage("Delete saved script ${name.text}?")
                    .setNegativeButton("Cancel", null).setPositiveButton("Delete") { _, _ ->
                        store.delete(name.text.toString()); message("Deleted")
                    }.show()
            }
        }
        label("Touch radius is a visual marker; Android injects each touch at its center. Coordinates are absolute pixels and may move after rotation. Scripts stay on this device.")
        renderSteps()
    }
    private fun buildScript(): Script? {
        val result = runCatching { Script(name.text.toString().trim(), repeats.number(), steps.toList()) }.getOrNull()
        if (result == null) message("Enter a name, repetitions, and at least one valid step")
        return result
    }
    private fun renderSteps() {
        stepsView.removeAllViews()
        steps.forEachIndexed { index, step ->
            button("${index + 1}. (${step.x}, ${step.y}) • radius ${step.radius}px • hold ${step.holdMs}ms • wait ${step.waitMs}ms   ✕") {
                steps.removeAt(index); renderSteps()
            }
        }
    }
    private fun field(title: String, hint: String, numeric: Boolean = true): EditText {
        label(title)
        val edit = EditText(this).apply {
            this.hint = hint
            inputType = if (numeric) InputType.TYPE_CLASS_NUMBER else InputType.TYPE_CLASS_TEXT
            setSingleLine(true)
        }
        body.addView(edit)
        return edit
    }
    private fun EditText.number() = text.toString().toInt()
    private fun label(value: String, heading: Boolean = false) {
        body.addView(TextView(this).apply {
            text = value
            textSize = if (heading) 22f else 16f
            if (heading) setTypeface(null, Typeface.BOLD)
            setPadding(0, 12, 0, 8)
        })
    }
    private fun button(title: String, action: () -> Unit) {
        body.addView(Button(this).apply { text = title; setOnClickListener { action() } })
    }
    private fun message(value: String) = Toast.makeText(this, value, Toast.LENGTH_LONG).show()
}
