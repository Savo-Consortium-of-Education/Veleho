class_name PauseMenu
extends CanvasLayer
## Esc menu. The run is checkpointed at the start of each level, so quitting
## returns you to the start of the current level next time.

signal resumed
signal quit_requested


func _ready() -> void:
	layer = 20
	process_mode = Node.PROCESS_MODE_ALWAYS
	var root := UiUtil.root_control()
	add_child(root)
	root.add_child(UiUtil.dim_rect(0.7))
	var box := VBoxContainer.new()
	box.position = Vector2(240 - 90, 70)
	box.custom_minimum_size = Vector2(180, 0)
	box.add_theme_constant_override("separation", 6)
	root.add_child(box)
	box.add_child(UiUtil.label("Tauko", Color("ffe08a"), 24))
	var resume := UiUtil.button("Jatka", _resume, 180)
	box.add_child(resume)
	box.add_child(UiUtil.button("Asetukset", _open_settings, 180))
	box.add_child(UiUtil.button("Tallenna ja lopeta", func(): quit_requested.emit(), 180))
	box.add_child(UiUtil.label("Maailma tallentuu juuri tähän kohtaan.", Color("a89cc0")))
	# The browser build cannot close itself; "Tallenna ja lopeta" covers it there.
	if not OS.has_feature("web"):
		box.add_child(UiUtil.button("Tallenna ja sulje peli", _save_and_exit, 180))
	resume.grab_focus()


func _settings_open() -> bool:
	for c in get_children():
		if c is SettingsMenu:
			return true
	return false


func _save_and_exit() -> void:
	var g := get_parent() as Game
	get_tree().paused = false
	if g:
		g.save_world()
	get_tree().quit()


func _open_settings() -> void:
	var sm := SettingsMenu.new()
	add_child(sm)


func _resume() -> void:
	resumed.emit()
	queue_free()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause") and not _settings_open():
		get_viewport().set_input_as_handled()
		_resume()
