class_name GameSettings
extends RefCounted
## Player-facing options: audio volumes (buses), display, gameplay and key
## bindings. Stored in user://settings.cfg and applied immediately.

const PATH := "user://settings.cfg"
const BASE := Vector2i(480, 270)

## Rebindable actions in menu order: [action, Finnish label]
const REBINDABLE := [
	["move_left", "Liiku vasemmalle"],
	["move_right", "Liiku oikealle"],
	["jump", "Hyppy / leijunta"],
	["fire", "Käytä asetta"],
	["alt_fire", "Heitä pullo"],
	["drink", "Juo pullosta"],
	["interact", "Poimi"],
	["inventory", "Reppu"],
]

var master := 0.8
var music := 0.6
var sfx := 0.8
var fullscreen := false
var window_scale := 3
var vsync := true
var shake := 1.0
var damage_numbers := true
var show_fps := false
## action -> Array of event dicts: {"k": physical_keycode} or {"m": mouse_button}
var bindings := {}


func ensure_buses() -> void:
	for bus_name in ["Music", "SFX"]:
		if AudioServer.get_bus_index(bus_name) < 0:
			AudioServer.add_bus()
			var idx := AudioServer.bus_count - 1
			AudioServer.set_bus_name(idx, bus_name)
			AudioServer.set_bus_send(idx, "Master")


func load_settings() -> void:
	var cf := ConfigFile.new()
	if cf.load(PATH) != OK:
		return
	master = float(cf.get_value("audio", "master", master))
	music = float(cf.get_value("audio", "music", music))
	sfx = float(cf.get_value("audio", "sfx", sfx))
	fullscreen = bool(cf.get_value("display", "fullscreen", fullscreen))
	window_scale = int(cf.get_value("display", "window_scale", window_scale))
	vsync = bool(cf.get_value("display", "vsync", vsync))
	shake = float(cf.get_value("game", "shake", shake))
	damage_numbers = bool(cf.get_value("game", "damage_numbers", damage_numbers))
	show_fps = bool(cf.get_value("game", "show_fps", show_fps))
	var b = cf.get_value("input", "bindings", {})
	if typeof(b) == TYPE_DICTIONARY:
		bindings = b
	if OS.has_feature("web"):
		# Browsers allow fullscreen only right after a click or key press.
		fullscreen = false


func save_settings() -> void:
	var cf := ConfigFile.new()
	cf.set_value("audio", "master", master)
	cf.set_value("audio", "music", music)
	cf.set_value("audio", "sfx", sfx)
	cf.set_value("display", "fullscreen", fullscreen)
	cf.set_value("display", "window_scale", window_scale)
	cf.set_value("display", "vsync", vsync)
	cf.set_value("game", "shake", shake)
	cf.set_value("game", "damage_numbers", damage_numbers)
	cf.set_value("game", "show_fps", show_fps)
	cf.set_value("input", "bindings", bindings)
	cf.save(PATH)


func apply_all() -> void:
	apply_audio()
	apply_display()
	apply_bindings()


func apply_audio() -> void:
	_set_bus("Master", master)
	_set_bus("Music", music)
	_set_bus("SFX", sfx)


func _set_bus(bus_name: String, v: float) -> void:
	var idx := AudioServer.get_bus_index(bus_name)
	if idx < 0:
		return
	AudioServer.set_bus_mute(idx, v <= 0.001)
	AudioServer.set_bus_volume_db(idx, linear_to_db(maxf(v, 0.001)))


func max_scale() -> int:
	var usable := DisplayServer.screen_get_usable_rect()
	var s := mini(usable.size.x / BASE.x, usable.size.y / BASE.y)
	return maxi(1, s)


func apply_display() -> void:
	if OS.has_feature("web"):
		# The page sizes the canvas and the browser syncs frames; only fullscreen applies.
		var full := DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_FULLSCREEN
		if fullscreen != full:
			DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN if fullscreen else DisplayServer.WINDOW_MODE_WINDOWED)
		return
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_ENABLED if vsync else DisplayServer.VSYNC_DISABLED)
	if fullscreen:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
		return
	if DisplayServer.window_get_mode() != DisplayServer.WINDOW_MODE_WINDOWED:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	window_scale = clampi(window_scale, 1, max_scale())
	var size := BASE * window_scale
	var usable := DisplayServer.screen_get_usable_rect()
	DisplayServer.window_set_size(size)
	DisplayServer.window_set_position(usable.position + (usable.size - size) / 2)


func apply_bindings() -> void:
	for action in bindings:
		if not InputMap.has_action(action):
			continue
		var evs: Array = bindings[action]
		if evs.is_empty():
			continue
		InputMap.action_erase_events(action)
		for d in evs:
			var ev := event_from_dict(d)
			if ev:
				InputMap.action_add_event(action, ev)


func set_binding(action: String, ev: InputEvent) -> void:
	var d := dict_from_event(ev)
	if d.is_empty():
		return
	bindings[action] = [d]
	apply_bindings()


func reset_bindings() -> void:
	bindings.clear()
	GameState.apply_default_input()


static func event_from_dict(d: Dictionary) -> InputEvent:
	if d.has("k"):
		var k := InputEventKey.new()
		k.physical_keycode = int(d["k"])
		return k
	if d.has("m"):
		var m := InputEventMouseButton.new()
		m.button_index = int(d["m"])
		return m
	return null


static func dict_from_event(ev: InputEvent) -> Dictionary:
	if ev is InputEventKey:
		var code := (ev as InputEventKey).physical_keycode
		if code == KEY_NONE:
			code = (ev as InputEventKey).keycode
		return {"k": int(code)}
	if ev is InputEventMouseButton:
		return {"m": int((ev as InputEventMouseButton).button_index)}
	return {}


static func event_label(ev: InputEvent) -> String:
	if ev is InputEventKey:
		var k := ev as InputEventKey
		var code := k.physical_keycode if k.physical_keycode != KEY_NONE else k.keycode
		var shown := code
		# The web display server cannot map physical keys to the keyboard layout.
		if k.physical_keycode != KEY_NONE and not OS.has_feature("web"):
			shown = DisplayServer.keyboard_get_keycode_from_physical(code)
		match shown:
			KEY_SPACE:
				return "Välilyönti"
			KEY_ESCAPE:
				return "Esc"
			KEY_TAB:
				return "Tab"
			KEY_SHIFT:
				return "Shift"
			KEY_CTRL:
				return "Ctrl"
			KEY_ALT:
				return "Alt"
			KEY_ENTER:
				return "Enter"
			KEY_UP:
				return "Ylös"
			KEY_DOWN:
				return "Alas"
			KEY_LEFT:
				return "Vasen"
			KEY_RIGHT:
				return "Oikea"
		return OS.get_keycode_string(shown)
	if ev is InputEventMouseButton:
		match (ev as InputEventMouseButton).button_index:
			MOUSE_BUTTON_LEFT:
				return "Hiiri vasen"
			MOUSE_BUTTON_RIGHT:
				return "Hiiri oikea"
			MOUSE_BUTTON_MIDDLE:
				return "Hiiri keski"
			MOUSE_BUTTON_WHEEL_UP:
				return "Rulla ylös"
			MOUSE_BUTTON_WHEEL_DOWN:
				return "Rulla alas"
			_:
				return "Hiiri %d" % (ev as InputEventMouseButton).button_index
	return "?"


static func action_label(action: String) -> String:
	var evs := InputMap.action_get_events(action)
	if evs.is_empty():
		return "–"
	var parts: Array[String] = []
	for e in evs.slice(0, 2):
		parts.append(event_label(e))
	return " / ".join(parts)
