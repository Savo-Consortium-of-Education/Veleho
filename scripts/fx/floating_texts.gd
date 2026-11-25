class_name FloatingTexts
extends Node2D
## Small rising damage numbers / pickup texts drawn with the pixel font.

var items: Array = []  # [pos, text, color, t]


func add(pos: Vector2, text: String, color: Color) -> void:
	if items.size() > 60:
		items.pop_front()
	items.append([pos + Vector2(randf_range(-3, 3), 0), text, color, 0.0])


func clear() -> void:
	items.clear()
	queue_redraw()


func _process(delta: float) -> void:
	var i := 0
	while i < items.size():
		var it: Array = items[i]
		it[3] += delta
		it[0] += Vector2(0, -18.0 * delta)
		if it[3] > 0.9:
			items.remove_at(i)
		else:
			i += 1
	queue_redraw()


func _draw() -> void:
	var f := Assets.font
	for it in items:
		var p: Vector2 = (it[0] as Vector2).round()
		var c: Color = it[2]
		c.a = clampf(1.6 - it[3] * 1.8, 0.0, 1.0)
		var w := f.get_string_size(it[1], HORIZONTAL_ALIGNMENT_LEFT, -1, 12).x
		var pos := Vector2(p.x - floorf(w * 0.5), p.y)
		f.draw_string(get_canvas_item(), pos + Vector2(1, 1), it[1], HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0, 0, 0, c.a * 0.8))
		f.draw_string(get_canvas_item(), pos, it[1], HORIZONTAL_ALIGNMENT_LEFT, -1, 12, c)
