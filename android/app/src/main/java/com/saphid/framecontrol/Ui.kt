package com.saphid.framecontrol

import android.annotation.SuppressLint
import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.text.InputType
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView

/** Small builders for the native screens, in the iPhone app's palette. */
internal class Ui(val context: Context) {
    fun dp(v: Number): Int = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v.toFloat(), context.resources.displayMetrics).toInt()
    fun color(id: Int) = context.getColor(id)

    fun rounded(fill: Int, radiusDp: Int, stroke: Int? = null) = GradientDrawable().apply {
        setColor(fill)
        cornerRadius = dp(radiusDp).toFloat()
        stroke?.let { setStroke(dp(1), it) }
    }

    fun column(spacingDp: Int = 0, vararg children: View) = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        children.forEach { add(it, spacingDp) }
    }

    fun row(vararg children: View) = LinearLayout(context).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        children.forEach { addView(it) }
    }

    fun LinearLayout.add(child: View, spacingDp: Int = 0) {
        val lp = (child.layoutParams as? LinearLayout.LayoutParams)
            ?: LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        if (childCount > 0 && orientation == LinearLayout.VERTICAL) lp.topMargin = dp(spacingDp)
        addView(child, lp)
    }

    fun text(s: CharSequence, sizeSp: Float = 16f, colorId: Int = R.color.frame_text, bold: Boolean = false) = TextView(context).apply {
        text = s
        setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp)
        setTextColor(color(colorId))
        if (bold) setTypeface(typeface, Typeface.BOLD)
        setLineSpacing(0f, 1.15f)
    }

    fun muted(s: CharSequence, sizeSp: Float = 14f) = text(s, sizeSp, R.color.frame_muted)

    fun title(s: CharSequence, sizeSp: Float = 22f) = text(s, sizeSp, bold = true).apply { setAccessibilityHeading(true) }

    fun primaryButton(label: CharSequence, onClick: () -> Unit) = Button(context).apply {
        text = label
        isAllCaps = false
        setTextColor(color(R.color.frame_text))
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
        setTypeface(typeface, Typeface.BOLD)
        background = RippleDrawable(ColorStateList.valueOf(0x33FFFFFF), rounded(color(R.color.frame_blue), 12), null)
        stateListAnimator = null
        minHeight = dp(52)
        setOnClickListener { onClick() }
    }

    fun plainButton(label: CharSequence, colorId: Int = R.color.frame_blue, onClick: () -> Unit) = Button(context).apply {
        text = label
        isAllCaps = false
        setTextColor(color(colorId))
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
        background = RippleDrawable(ColorStateList.valueOf(0x22FFFFFF), null, rounded(0xFFFFFFFF.toInt(), 10))
        stateListAnimator = null
        minHeight = dp(48)
        setOnClickListener { onClick() }
    }

    fun field(hint: String, type: Int = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI) = EditText(context).apply {
        this.hint = hint
        inputType = type or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
        setSingleLine()
        setTextColor(color(R.color.frame_text))
        setHintTextColor(color(R.color.frame_muted))
        background = rounded(color(R.color.frame_field), 10)
        setPadding(dp(14), dp(12), dp(14), dp(12))
        minHeight = dp(48)
    }

    fun card(vararg children: View) = column(12, *children).apply {
        background = rounded(color(R.color.frame_panel), 14)
        setPadding(dp(16), dp(16), dp(16), dp(16))
    }

    fun label(s: String) = muted(s, 13f)

    fun tip(s: String) = text("•  $s", 14f)
}

/** Lays its one child out no wider than maxWidth, centred: setup reads well on a tablet or in landscape. */
@SuppressLint("ViewConstructor")  // built in code only, never inflated
internal class MaxWidth(context: Context, private val maxWidthPx: Int) : FrameLayout(context) {
    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val width = MeasureSpec.getSize(widthMeasureSpec)
        val capped = if (width > maxWidthPx) MeasureSpec.makeMeasureSpec(maxWidthPx, MeasureSpec.EXACTLY) else widthMeasureSpec
        super.onMeasure(capped, heightMeasureSpec)
        if (width > maxWidthPx) setMeasuredDimension(width, measuredHeight)
    }

    override fun onLayout(changed: Boolean, left: Int, top: Int, right: Int, bottom: Int) {
        val child = getChildAt(0) ?: return
        val x = (width - child.measuredWidth) / 2
        val gravity = (child.layoutParams as? LayoutParams)?.gravity ?: 0
        val centred = (gravity and Gravity.VERTICAL_GRAVITY_MASK) == Gravity.CENTER_VERTICAL
        val y = if (centred) maxOf(paddingTop, (height - child.measuredHeight) / 2) else paddingTop
        child.layout(x, y, x + child.measuredWidth, y + child.measuredHeight)
    }
}
