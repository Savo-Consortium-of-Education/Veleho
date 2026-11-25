class_name InventoryMenu
extends CanvasLayer
## "Reppu" (Tab): drag spells between wands/staffs and the spell bag, and drag
## weapons to reorder the four weapon slots. The game is paused while open.

signal closed

var game: Game
var player: Player
var root: Control
var hover: InvSlot = null
var tip_title: Label
var tip_body: Label
var _slots: Array[InvSlot] = []


class InvSlot:
	extends Control
	var inv: InventoryMenu
	var kind := "spell"  # "spell" or "weapon"
	var arr: Array
	var idx := 0

	func _init() -> void:
		custom_minimum_size = Vector2(20, 20)
		size = Vector2(20, 20)
		mouse_filter = Control.MOUSE_FILTER_STOP
		mouse_entered.connect(func(): inv._set_hover(self))
		mouse_exited.connect(func(): inv._set_hover(null))

	func value():
		return arr[idx]

	func is_empty() -> bool:
		var v = arr[idx]
		return v == null or (v is String and v == "")

	func icon() -> Texture2D:
		if is_empty():
			return null
		if kind == "spell":
			return Spells.icon_of(String(arr[idx]))
		return (arr[idx] as Weapon).icon()

	func _draw() -> void:
		var frame := 2 if is_empty() else 0
		if inv.hover == self:
			frame = 1
		draw_texture_rect_region(Assets.tex("slot"), Rect2(0, 0, 20, 20), Rect2(frame * 20, 0, 20, 20))
		if is_empty():
			return
		if kind == "spell":
			draw_texture(icon(), Vector2(2, 2))
		else:
			var w := arr[idx] as Weapon
			var t := w.icon()
			var ang := 0.0 if w.type == Weapon.FLASK else -PI * 0.25
			draw_set_transform(Vector2(10, 10), ang, Vector2.ONE)
			draw_texture(t, -(Vector2(t.get_width(), t.get_height()) * 0.5).floor())
			draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)

	func _get_drag_data(_at: Vector2) -> Variant:
		if is_empty():
			return null
		var holder := Control.new()
		var tr := TextureRect.new()
		tr.texture = icon()
		tr.position = -Vector2(8, 8)
		if kind == "weapon" and (arr[idx] as Weapon).type != Weapon.FLASK:
			tr.rotation = -PI * 0.25
		holder.add_child(tr)
		set_drag_preview(holder)
		Audio.play("ui_hover", -6.0)
		return {"inv_slot": self}

	func _can_drop_data(_at: Vector2, data: Variant) -> bool:
		return data is Dictionary and data.has("inv_slot") and (data["inv_slot"] as InvSlot).kind == kind

	func _drop_data(_at: Vector2, data: Variant) -> void:
		inv.swap(data["inv_slot"], self)


func setup(g: Game) -> void:
	game = g
	player = g.player
	layer = 25
	process_mode = Node.PROCESS_MODE_ALWAYS
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_build()
	Audio.play("inventory_open", -4.0)


func _build() -> void:
	if root:
		root.queue_free()
	_slots.clear()
	hover = null
	root = UiUtil.root_control()
	add_child(root)
	root.add_child(UiUtil.dim_rect(0.6))
	var panel := PanelContainer.new()
	panel.position = Vector2(10, 6)
	panel.size = Vector2(460, 258)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(panel)
	var title := UiUtil.label("Reppu", Color("ffe08a"), 24)
	title.position = Vector2(0, 12)
	title.size = Vector2(480, 24)
	root.add_child(title)
	var hint := UiUtil.label("Raahaa loitsuja ja aseita. Muokkain vaikuttaa seuraavaan loitsuun.", Color("a89cc0"))
	hint.position = Vector2(0, 38)
	hint.size = Vector2(480, 12)
	root.add_child(hint)
	for i in Player.SLOTS:
		var y := 54.0 + i * 32.0
		var ws := _slot("weapon", player.weapons, i, Vector2(22, y))
		var w: Weapon = player.weapons[i]
		var keylab := UiUtil.label(str(i + 1), Color(1, 1, 1, 0.5), 12, HORIZONTAL_ALIGNMENT_LEFT)
		keylab.position = Vector2(14, y + 4)
		root.add_child(keylab)
		if w == null:
			var e := UiUtil.label("(tyhjä paikka)", Color("6b6275"), 12, HORIZONTAL_ALIGNMENT_LEFT)
			e.position = Vector2(48, y + 4)
			root.add_child(e)
			continue
		var nm := UiUtil.label(w.name, w.main_color().lerp(Color.WHITE, 0.5), 12, HORIZONTAL_ALIGNMENT_LEFT)
		nm.position = Vector2(48, y)
		root.add_child(nm)
		var sub := ""
		match w.type:
			Weapon.WAND:
				sub = "Sauva · %d paikkaa · kerralla %d" % [w.capacity, w.multicast]
			Weapon.STAFF:
				sub = "Keppi · %d paikkaa · lataus %.1f s" % [w.capacity, w.charge_time]
			Weapon.SWORD:
				sub = "Miekka · vahinko %d" % int(w.damage)
			Weapon.FLASK:
				sub = "Pullo · %s %d/%d" % [w.liquid_name(), int(w.amount), int(Weapon.FLASK_MAX)]
		var sl := UiUtil.label(sub, Color("8f86a8"), 12, HORIZONTAL_ALIGNMENT_LEFT)
		sl.position = Vector2(48, y + 11)
		root.add_child(sl)
		if w.uses_spells():
			for k in w.spells.size():
				_slot("spell", w.spells, k, Vector2(226 + k * 21, y))
		ws.tooltip_text = ""
	var bag_l := UiUtil.label("Loitsupussi", Color("c8a8ff"), 12, HORIZONTAL_ALIGNMENT_LEFT)
	bag_l.position = Vector2(22, 184)
	root.add_child(bag_l)
	for k in Player.BAG_SIZE:
		_slot("spell", player.spell_bag, k, Vector2(22 + (k % 8) * 21, 197 + (k / 8) * 22))
	tip_title = UiUtil.label("", Color("ffe08a"), 12, HORIZONTAL_ALIGNMENT_LEFT)
	tip_title.position = Vector2(202, 186)
	tip_title.size = Vector2(256, 12)
	root.add_child(tip_title)
	tip_body = UiUtil.label("Vie hiiri loitsun tai aseen päälle.", Color("d8d0e8"), 12, HORIZONTAL_ALIGNMENT_LEFT)
	tip_body.position = Vector2(202, 199)
	tip_body.size = Vector2(256, 52)
	tip_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(tip_body)
	var close := UiUtil.button("Sulje (Tab)", _close, 90)
	close.position = Vector2(370, 14)
	root.add_child(close)


func _slot(kind: String, arr: Array, idx: int, pos: Vector2) -> InvSlot:
	var s := InvSlot.new()
	s.inv = self
	s.kind = kind
	s.arr = arr
	s.idx = idx
	s.position = pos
	root.add_child(s)
	_slots.append(s)
	return s


func _set_hover(s: InvSlot) -> void:
	hover = s
	for x in _slots:
		x.queue_redraw()
	if s == null or s.is_empty():
		return
	if s.kind == "spell":
		var lines := Spells.describe(String(s.value()))
		tip_title.text = lines[0]
		tip_body.text = "\n".join(lines.slice(1))
	else:
		var w := s.value() as Weapon
		tip_title.text = "%s (%s)" % [w.name, w.type_name()]
		tip_body.text = "\n".join(w.describe())


func swap(a: InvSlot, b: InvSlot) -> void:
	if a == b:
		return
	var va = a.arr[a.idx]
	var vb = b.arr[b.idx]
	if a.kind == "spell":
		a.arr[a.idx] = "" if vb == null else vb
		b.arr[b.idx] = "" if va == null else va
	else:
		a.arr[a.idx] = vb
		b.arr[b.idx] = va
	Audio.play("slot_place", -2.0)
	for w in player.weapons:
		if w != null:
			(w as Weapon).cursor = 0
	if a.kind == "weapon":
		player._refresh_weapon_sprite()
		_build.call_deferred()
	else:
		for x in _slots:
			x.queue_redraw()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("inventory") or event.is_action_pressed("pause"):
		get_viewport().set_input_as_handled()
		_close()


func _close() -> void:
	Audio.play("inventory_close", -4.0)
	player._refresh_weapon_sprite()
	closed.emit()
	queue_free()
