package io.github.kingyx3.autoclicker

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Color
import android.graphics.Path
import android.graphics.PixelFormat
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.WindowManager
import android.view.View
import android.widget.Button
import android.widget.TextView
import android.view.accessibility.AccessibilityEvent

class TapService : AccessibilityService() {
    companion object { var current: TapService? = null; private set }
    private val handler = Handler(Looper.getMainLooper())
    private var generation = 0
    private var running = false
    private var panel: View? = null
    private var marker: View? = null
    private val windows by lazy { getSystemService(WINDOW_SERVICE) as WindowManager }

    override fun onServiceConnected() { super.onServiceConnected(); current = this }
    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}
    override fun onInterrupt() { stop() }
    override fun onDestroy() { stop(); current = null; super.onDestroy() }

    fun start(script: Script): Boolean {
        if (running) return false
        val metrics = resources.displayMetrics
        if (script.steps.any { it.x >= metrics.widthPixels || it.y >= metrics.heightPixels }) return false
        generation++
        val run = generation
        running = true
        showStop()
        // The countdown gives the user time to navigate to the target app.
        handler.postDelayed({ if (valid(run)) next(script, 0, 0, run) }, 5000)
        return true
    }
    fun stop() {
        generation++
        running = false
        handler.removeCallbacksAndMessages(null)
        panel?.let { windows.removeView(it) }; panel = null
        marker?.let { windows.removeView(it) }; marker = null
    }
    private fun valid(run: Int) = running && run == generation
    private fun next(script: Script, loop: Int, index: Int, run: Int) {
        if (!valid(run)) return
        if (loop == script.repetitions) { stop(); return }
        val step = script.steps[index]
        showMarker(step)
        val path = Path().apply { moveTo(step.x.toFloat(), step.y.toFloat()) }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, step.holdMs)).build()
        val accepted = dispatchGesture(gesture, object : GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) {
                if (!valid(run)) return
                val last = index == script.steps.lastIndex
                handler.postDelayed({
                    next(script, if (last) loop + 1 else loop, if (last) 0 else index + 1, run)
                }, step.waitMs)
            }
            override fun onCancelled(gestureDescription: GestureDescription?) { if (valid(run)) stop() }
        }, handler)
        if (!accepted) stop()
    }
    private fun showStop() {
        val button = Button(this).apply {
            text = "STOP TAPS"
            setOnClickListener { stop() }
            contentDescription = "Stop tap script"
        }
        val p = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE, PixelFormat.TRANSLUCENT
        ).apply { gravity = Gravity.TOP or Gravity.END }
        windows.addView(button, p)
        panel = button
    }
    private fun showMarker(step: Step) {
        marker?.let { windows.removeView(it) }
        val diameter = step.radius * 2
        val view = TextView(this).apply {
            background = android.graphics.drawable.GradientDrawable().apply {
                shape = android.graphics.drawable.GradientDrawable.OVAL
                setColor(Color.argb(60, 20, 130, 255))
                setStroke(3, Color.BLUE)
            }
        }
        val p = WindowManager.LayoutParams(diameter, diameter,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or WindowManager.LayoutParams.FLAG_NOT_ACCESSIBILITY_FOCUSABLE,
            PixelFormat.TRANSLUCENT).apply {
            gravity = Gravity.TOP or Gravity.LEFT
            x = step.x - step.radius
            y = step.y - step.radius
        }
        windows.addView(view, p)
        marker = view
    }
}
