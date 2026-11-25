class_name DeathScreen
extends CanvasLayer
## Permadeath summary. The saved run is already deleted at this point.

signal retry
signal to_menu


func setup(info: Dictionary) -> void:
	layer = 20
	process_mode = Node.PROCESS_MODE_ALWAYS
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	get_tree().paused = false
	var root := UiUtil.root_control()
	add_child(root)
	var bg := ColorRect.new()
	bg.color = Color("08040a")
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(bg)
	var box := VBoxContainer.new()
	box.position = Vector2(40, 46)
	box.custom_minimum_size = Vector2(400, 0)
	box.add_theme_constant_override("separation", 4)
	root.add_child(box)
	box.add_child(UiUtil.label("KUOLIT", Color("e0303c"), 36))
	var cause := String(info.get("cause", ""))
	if cause == "":
		cause = "tuntematon"
	box.add_child(UiUtil.label("Kuolinsyy: %s" % cause, Color("ffb0a0")))
	var tsec := int(info.get("time", 0.0))
	box.add_child(UiUtil.label("Taso %d · %s" % [int(info.get("level", 1)), String(info.get("dimension", ""))], Color("e8e0d0")))
	box.add_child(UiUtil.label("Aika %d:%02d · Tappoja %d · Kultaa %d" % [tsec / 60, tsec % 60, int(info.get("kills", 0)), int(info.get("gold", 0))], Color("c8c0d8")))
	box.add_child(UiUtil.label("Maailman siemen #%d on kadonnut ikuisiksi ajoiksi." % int(info.get("seed", 0)), Color("8f86a8")))
	var spacer := Control.new()
	spacer.custom_minimum_size = Vector2(0, 10)
	box.add_child(spacer)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 10)
	box.add_child(row)
	var r := UiUtil.button("Uusi juoksu", func(): retry.emit(), 120)
	row.add_child(r)
	row.add_child(UiUtil.button("Päävalikko", func(): to_menu.emit(), 120))
	r.grab_focus()
	Audio.play_music("menu", 3.0)
