class_name UiUtil
extends RefCounted
## Small helpers for building menus in code.


## Full-screen root Control that carries the pixel-font theme. Controls under a
## CanvasLayer do not inherit the Window theme, so every menu root sets it.
static func root_control() -> Control:
	var c := Control.new()
	c.theme = Assets.theme
	c.set_anchors_preset(Control.PRESET_FULL_RECT)
	return c


static func label(text: String, color: Color = Color("e8e0d0"), size: int = 12, align: int = HORIZONTAL_ALIGNMENT_CENTER) -> Label:
	var l := Label.new()
	l.text = text
	l.horizontal_alignment = align
	l.add_theme_color_override("font_color", color)
	l.add_theme_font_size_override("font_size", size)
	return l


static func button(text: String, cb: Callable, min_w: float = 140.0) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(min_w, 18)
	b.focus_mode = Control.FOCUS_ALL
	b.pressed.connect(func():
		Audio.play("ui_click", -4.0)
		cb.call())
	b.mouse_entered.connect(func(): Audio.play("ui_hover", -12.0))
	return b


## Shrinks a button's vertical padding (for dense lists).
static func compact(b: Button) -> Button:
	for st in ["normal", "hover", "pressed", "focus", "disabled"]:
		var base := b.get_theme_stylebox(st)
		if base is StyleBoxFlat:
			var sb := (base as StyleBoxFlat).duplicate() as StyleBoxFlat
			sb.content_margin_top = 0
			sb.content_margin_bottom = 0
			b.add_theme_stylebox_override(st, sb)
	b.custom_minimum_size.y = 13
	return b


static func dim_rect(alpha: float = 0.7) -> ColorRect:
	var r := ColorRect.new()
	r.color = Color(0.02, 0.01, 0.04, alpha)
	r.set_anchors_preset(Control.PRESET_FULL_RECT)
	r.mouse_filter = Control.MOUSE_FILTER_STOP
	return r
