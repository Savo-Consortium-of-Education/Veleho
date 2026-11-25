class_name SettingsMenu
extends CanvasLayer
## Options menu: audio, display, gameplay and key bindings. Opened from the
## title screen and the pause menu. Changes apply immediately and are saved
## when the menu closes.

signal closed

var s: GameSettings
var tabs: Array[Button] = []
var pages: Array[Control] = []
var _waiting_action := ""
var _waiting_button: Button
var _waiting_since := 0
var _key_buttons := {}
var _scale_label: Label


func _ready() -> void:
	layer = 30
	process_mode = Node.PROCESS_MODE_ALWAYS
	s = GameState.settings
	var root := UiUtil.root_control()
	add_child(root)
	root.add_child(UiUtil.dim_rect(0.75))
	var panel := PanelContainer.new()
	panel.position = Vector2(50, 14)
	panel.size = Vector2(380, 242)
	panel.custom_minimum_size = Vector2(380, 242)
	root.add_child(panel)
	var outer := VBoxContainer.new()
	outer.add_theme_constant_override("separation", 6)
	panel.add_child(outer)
	outer.add_child(UiUtil.label("Asetukset", Color("ffe08a"), 24))
	var tab_row := HBoxContainer.new()
	tab_row.alignment = BoxContainer.ALIGNMENT_CENTER
	tab_row.add_theme_constant_override("separation", 4)
	outer.add_child(tab_row)
	var names := ["Ääni", "Näyttö", "Peli", "Näppäimet"]
	for i in names.size():
		var b := UiUtil.button(names[i], func(): _show_page(i), 80)
		tab_row.add_child(b)
		tabs.append(b)
	var page_holder := Control.new()
	page_holder.custom_minimum_size = Vector2(360, 150)
	outer.add_child(page_holder)
	pages.append(_audio_page())
	pages.append(_display_page())
	pages.append(_game_page())
	pages.append(_keys_page())
	for p in pages:
		page_holder.add_child(p)
	var back := UiUtil.button("Palaa", _close, 120)
	var back_row := HBoxContainer.new()
	back_row.alignment = BoxContainer.ALIGNMENT_CENTER
	back_row.add_child(back)
	outer.add_child(back_row)
	_show_page(0)
	back.grab_focus()
	Audio.play("inventory_open", -6.0)


func _show_page(i: int) -> void:
	for k in pages.size():
		pages[k].visible = k == i
		tabs[k].add_theme_color_override("font_color", Color("ffe08a") if k == i else Color("a89cc0"))
	_cancel_wait()


func _page() -> VBoxContainer:
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 5)
	v.position = Vector2(8, 4)
	v.custom_minimum_size = Vector2(344, 0)
	return v


func _row(page: VBoxContainer, text: String, ctrl: Control) -> void:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 8)
	var l := UiUtil.label(text, Color("e8e0d0"), 12, HORIZONTAL_ALIGNMENT_LEFT)
	l.custom_minimum_size = Vector2(150, 12)
	h.add_child(l)
	h.add_child(ctrl)
	page.add_child(h)


func _slider(value: float, cb: Callable) -> HBoxContainer:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 6)
	var sl := HSlider.new()
	sl.min_value = 0
	sl.max_value = 100
	sl.step = 5
	sl.value = round(value * 100.0)
	sl.custom_minimum_size = Vector2(130, 12)
	sl.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var pct := UiUtil.label("%d %%" % int(sl.value), Color("c8c0d8"), 12, HORIZONTAL_ALIGNMENT_LEFT)
	pct.custom_minimum_size = Vector2(36, 12)
	sl.value_changed.connect(func(v: float):
		pct.text = "%d %%" % int(v)
		cb.call(v / 100.0))
	h.add_child(sl)
	h.add_child(pct)
	return h


func _check(value: bool, cb: Callable) -> CheckBox:
	var c := CheckBox.new()
	c.button_pressed = value
	c.text = "Päällä" if value else "Pois"
	c.toggled.connect(func(on: bool):
		c.text = "Päällä" if on else "Pois"
		Audio.play("ui_click", -8.0)
		cb.call(on))
	return c


func _audio_page() -> Control:
	var p := _page()
	_row(p, "Kokonaisvoimakkuus", _slider(s.master, func(v):
		s.master = v
		s.apply_audio()))
	_row(p, "Musiikki", _slider(s.music, func(v):
		s.music = v
		s.apply_audio()))
	_row(p, "Äänitehosteet", _slider(s.sfx, func(v):
		s.sfx = v
		s.apply_audio()
		Audio.play("ui_hover", -2.0)))
	return p


func _display_page() -> Control:
	var p := _page()
	_row(p, "Koko näyttö", _check(s.fullscreen, func(on):
		s.fullscreen = on
		s.apply_display()))
	if OS.has_feature("web"):
		p.add_child(UiUtil.label("Selaimessa pelin koko seuraa selainikkunaa.", Color("8f86a8"), 12, HORIZONTAL_ALIGNMENT_LEFT))
		return p
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 4)
	var minus := UiUtil.button("<", func(): _change_scale(-1), 18)
	_scale_label = UiUtil.label("%dx" % s.window_scale, Color("ffe08a"))
	_scale_label.custom_minimum_size = Vector2(40, 12)
	var plus := UiUtil.button(">", func(): _change_scale(1), 18)
	h.add_child(minus)
	h.add_child(_scale_label)
	h.add_child(plus)
	_row(p, "Ikkunan koko", h)
	_row(p, "Pystytahdistus (VSync)", _check(s.vsync, func(on):
		s.vsync = on
		s.apply_display()))
	p.add_child(UiUtil.label("Ikkunan koko on aina pelin 480x270-kuvan kokonaislukumonikerta.", Color("8f86a8"), 12, HORIZONTAL_ALIGNMENT_LEFT))
	return p


func _change_scale(d: int) -> void:
	s.window_scale = clampi(s.window_scale + d, 1, s.max_scale())
	_scale_label.text = "%dx" % s.window_scale
	if not s.fullscreen:
		s.apply_display()


func _game_page() -> Control:
	var p := _page()
	_row(p, "Ruudun tärinä", _slider(s.shake, func(v): s.shake = v))
	_row(p, "Vahinkonumerot", _check(s.damage_numbers, func(on): s.damage_numbers = on))
	_row(p, "FPS-näyttö", _check(s.show_fps, func(on): s.show_fps = on))
	return p


func _keys_page() -> Control:
	var p := _page()
	p.add_theme_constant_override("separation", 1)
	for pair in GameSettings.REBINDABLE:
		var action: String = pair[0]
		var b := UiUtil.button(GameSettings.action_label(action), func(): _start_wait(action), 150)
		_key_buttons[action] = b
		_row(p, pair[1], b)
	var reset := UiUtil.button("Palauta oletukset", func():
		s.reset_bindings()
		_refresh_keys(), 150)
	_row(p, "", reset)
	for b in _key_buttons.values():
		_compact_later(b)
	_compact_later(reset)
	return p


func _compact_later(b: Button) -> void:
	# Theme styles resolve only once the button is inside the themed tree.
	b.ready.connect(func(): UiUtil.compact(b), CONNECT_ONE_SHOT)


func _refresh_keys() -> void:
	for action in _key_buttons:
		(_key_buttons[action] as Button).text = GameSettings.action_label(action)


func _start_wait(action: String) -> void:
	_cancel_wait()
	_waiting_action = action
	_waiting_button = _key_buttons[action]
	_waiting_button.text = "Paina näppäintä…"
	_waiting_since = Time.get_ticks_msec()


func _cancel_wait() -> void:
	if _waiting_action != "":
		_waiting_action = ""
		_refresh_keys()


func _input(event: InputEvent) -> void:
	if _waiting_action == "":
		if event.is_action_pressed("pause"):
			get_viewport().set_input_as_handled()
			_close()
		return
	var accept := false
	if event is InputEventKey and event.pressed and not event.echo:
		if (event as InputEventKey).physical_keycode == KEY_ESCAPE:
			get_viewport().set_input_as_handled()
			_cancel_wait()
			return
		accept = true
	elif event is InputEventMouseButton and event.pressed:
		# ignore the click that started the wait
		accept = Time.get_ticks_msec() - _waiting_since > 200
	if accept:
		get_viewport().set_input_as_handled()
		s.set_binding(_waiting_action, event)
		_waiting_action = ""
		_refresh_keys()
		Audio.play("slot_place", -4.0)


func _close() -> void:
	s.save_settings()
	Audio.play("inventory_close", -6.0)
	closed.emit()
	queue_free()
