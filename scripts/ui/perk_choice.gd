class_name PerkChoice
extends CanvasLayer
## Shown when entering a dimensional gate: pick one of three blessings.

signal chosen(id: String)

var _done := false


func setup(ids: Array[String], level: int) -> void:
	layer = 20
	process_mode = Node.PROCESS_MODE_ALWAYS
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	var root := UiUtil.root_control()
	add_child(root)
	root.add_child(UiUtil.dim_rect(0.78))
	var box := VBoxContainer.new()
	box.position = Vector2(240 - 120, 60)
	box.custom_minimum_size = Vector2(240, 0)
	box.add_theme_constant_override("separation", 6)
	root.add_child(box)
	box.add_child(UiUtil.label("Ulottuvuusportti", Color("c8a8ff"), 24))
	box.add_child(UiUtil.label("Taso %d selvitetty. Valitse siunaus:" % level, Color("e8e0d0")))
	for id in ids:
		var d: Dictionary = Perks.LIST[id]
		var b := UiUtil.button("%s – %s" % [d["name"], d["desc"]], func(): _pick(id), 240)
		box.add_child(b)
	if box.get_child_count() > 2:
		(box.get_child(2) as Button).grab_focus()


func _pick(id: String) -> void:
	if _done:
		return
	_done = true
	Input.mouse_mode = Input.MOUSE_MODE_HIDDEN
	chosen.emit(id)
