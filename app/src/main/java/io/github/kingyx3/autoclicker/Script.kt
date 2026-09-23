package io.github.kingyx3.autoclicker

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

data class Step(val x: Int, val y: Int, val radius: Int, val holdMs: Long, val waitMs: Long) {
    init {
        require(x >= 0 && y >= 0 && radius in 1..200)
        require(holdMs in 1..60000 && waitMs in 0..600000)
    }
    fun json() = JSONObject().put("x", x).put("y", y).put("radius", radius).put("holdMs", holdMs).put("waitMs", waitMs)
    companion object {
        fun parse(o: JSONObject) = Step(o.getInt("x"), o.getInt("y"), o.optInt("radius", 24), o.getLong("holdMs"), o.getLong("waitMs"))
    }
}
data class Script(val name: String, val repetitions: Int, val steps: List<Step>) {
    init { require(name.isNotBlank() && repetitions in 1..10000 && steps.isNotEmpty() && steps.size <= 100) }
    fun json() = JSONObject().put("name", name).put("repetitions", repetitions)
        .put("steps", JSONArray().also { a -> steps.forEach { a.put(it.json()) } })
    companion object {
        fun parse(o: JSONObject): Script {
            val a = o.getJSONArray("steps")
            return Script(o.getString("name"), o.getInt("repetitions"), (0 until a.length()).map { Step.parse(a.getJSONObject(it)) })
        }
    }
}
class ScriptStore(context: Context) {
    private val prefs = context.getSharedPreferences("scripts", Context.MODE_PRIVATE)
    fun all(): List<Script> = runCatching {
        val a = JSONArray(prefs.getString("data", "[]"))
        (0 until a.length()).map { Script.parse(a.getJSONObject(it)) }
    }.getOrDefault(emptyList())
    fun save(script: Script) {
        val list = all().filterNot { it.name == script.name } + script
        prefs.edit().putString("data", JSONArray().also { a -> list.forEach { a.put(it.json()) } }.toString()).apply()
    }
    fun delete(name: String) {
        prefs.edit().putString("data", JSONArray().also { a -> all().filterNot { it.name == name }.forEach { a.put(it.json()) } }.toString()).apply()
    }
}
