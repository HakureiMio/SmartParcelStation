package io.github.hakureimio.smartparcel.demo

import android.content.Context
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.text.InputType
import android.view.View
import android.widget.*

object IosUi {
    const val BACKGROUND = "#F5F5F7"
    const val BLUE = "#007AFF"
    const val GREEN = "#34C759"
    const val ORANGE = "#FF9500"
    const val RED = "#FF3B30"
    const val LABEL = "#1C1C1E"
    const val SECONDARY = "#6E6E73"
    fun dp(c: Context, value: Int) = (value * c.resources.displayMetrics.density).toInt()
    fun rounded(color: String, radius: Int, strokeColor: String? = null) = GradientDrawable().apply {
        setColor(Color.parseColor(color)); cornerRadius = radius.toFloat()
        strokeColor?.let { setStroke(1, Color.parseColor(it)) }
    }
    fun card(c: Context, content: LinearLayout.() -> Unit) = LinearLayout(c).apply {
        orientation = LinearLayout.VERTICAL; setPadding(dp(c, 20), dp(c, 18), dp(c, 20), dp(c, 18)); background = rounded("#FFFFFF", dp(c, 18)); elevation = dp(c, 1).toFloat(); content()
    }
    fun label(c: Context, value: String, size: Float = 15f, color: String = LABEL, bold: Boolean = false) = TextView(c).apply {
        text = value; textSize = size; setTextColor(Color.parseColor(color)); if (bold) setTypeface(null, Typeface.BOLD); setLineSpacing(0f, 1.12f)
    }
    fun input(c: Context, hintText: String, value: String = "", secret: Boolean = false) = EditText(c).apply {
        hint = hintText; setText(value); textSize = 16f; setTextColor(Color.parseColor(LABEL)); setHintTextColor(Color.parseColor("#8E8E93")); setPadding(dp(c, 16), 0, dp(c, 16), 0); background = rounded("#F2F2F7", dp(c, 12)); minHeight = dp(c, 50)
        if (secret) inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
    }
    fun button(c: Context, title: String, color: String = BLUE, action: (View) -> Unit) = Button(c).apply {
        text = title; textSize = 16f; isAllCaps = false; setTextColor(Color.WHITE); setTypeface(null, Typeface.BOLD); background = rounded(color, dp(c, 14)); minHeight = dp(c, 52); setOnClickListener(action)
    }
    fun gap(c: Context, height: Int) = Space(c).apply { minimumHeight = dp(c, height) }
}
