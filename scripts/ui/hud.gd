class_name Hud
extends CanvasLayer
## In-game HUD, drawn directly with the pixel font for crisp 1:1 pixels.

var game: Game
var canvas: HudCanvas
var debug := false
var messages: Array = []  # [text, color, t]
var title_text := ""
var title_sub := ""
var title_t := 99.0
var loading := false


class HudCanvas:
	extends Control
	var hud: Hud

	func _draw() -> void:
		hud._draw_hud(self)


func _ready() -> void:
	layer = 10
	process_mode = Node.PROCESS_MODE_ALWAYS
	canvas = HudCanvas.new()
	canvas.hud = self
	canvas.mouse_filter = Control.MOUSE_FILTER_IGNORE
	canvas.position = Vector2.ZERO
	canvas.size = Vector2(480, 270)
	add_child(canvas)


func show_loading(on: bool) -> void:
	loading = on
	canvas.queue_redraw()


func show_title(t: String, sub: String) -> void:
	title_text = t
	title_sub = sub
	title_t = 0.0


func message(text: String, color: Color = Color.WHITE) -> void:
	messages.append([text, color, 0.0])
	if messages.size() > 4:
		messages.pop_front()


func _process(delta: float) -> void:
	title_t += delta
	var i := 0
	while i < messages.size():
		messages[i][2] += delta
		if messages[i][2] > 3.5:
			messages.remove_at(i)
		else:
			i += 1
	canvas.queue_redraw()


# ---------------------------------------------------------------------------
func _text(ci: CanvasItem, pos: Vector2, s: String, col: Color, size: int = 12, align: int = HORIZONTAL_ALIGNMENT_LEFT, width: float = -1.0) -> void:
	var f := Assets.font
	f.draw_string(ci.get_canvas_item(), pos + Vector2(1, 1), s, align, width, size, Color(0, 0, 0, col.a * 0.85))
	f.draw_string(ci.get_canvas_item(), pos, s, align, width, size, col)


func _text_c(ci: CanvasItem, cx: float, y: float, s: String, col: Color, size: int = 12) -> void:
	var w := Assets.font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	_text(ci, Vector2(floorf(cx - w * 0.5), y), s, col, size)


func _bar(ci: CanvasItem, x: float, y: float, w: float, frac: float, col: Color, back: Color) -> void:
	ci.draw_rect(Rect2(x - 1, y - 1, w + 2, 6), Color("140c1c"))
	ci.draw_rect(Rect2(x, y, w, 4), back)
	ci.draw_rect(Rect2(x, y, floorf(w * clampf(frac, 0.0, 1.0)), 4), col)
	ci.draw_rect(Rect2(x, y, floorf(w * clampf(frac, 0.0, 1.0)), 1), col.lightened(0.35))


func _draw_hud(ci: Control) -> void:
	if loading:
		ci.draw_rect(Rect2(0, 0, 480, 270), Color("07050b"))
		var dots := ".".repeat(int(Time.get_ticks_msec() / 300) % 4)
		_text_c(ci, 240, 128, "Maailma muotoutuu" + dots, Color("c8b8e8"))
		return
	if game == null or game.player == null:
		return
	var p := game.player
	var run: Dictionary = GameState.run
	# --- top-left: level + stats
	_text(ci, Vector2(6, 12), "Taso %d · %s" % [game.level, String(game.dim.get("name", ""))], Color("e8e0d0"))
	var st: Dictionary = run.get("stats", {})
	ci.draw_texture(Assets.icon(4), Vector2(6, 17))
	_text(ci, Vector2(17, 25), str(int(st.get("gold", 0))), Color("f2c14e"))
	ci.draw_texture(Assets.icon(3), Vector2(52, 17))
	_text(ci, Vector2(63, 25), str(int(st.get("kills", 0))), Color("e8e0d0"))
	ci.draw_texture(Assets.icon(6), Vector2(92, 17))
	var tsec := int(st.get("time", 0.0))
	_text(ci, Vector2(103, 25), "%d:%02d" % [tsec / 60, tsec % 60], Color("b8b0c8"))
	# --- bottom-left: bars
	var bx := 18.0
	var by := 236.0
	ci.draw_texture(Assets.icon(0), Vector2(6, by - 2))
	_bar(ci, bx, by, 70, p.hp / p.max_hp, Color("d8343f"), Color("3a1018"))
	_text(ci, Vector2(bx + 74, by + 5), "%d/%d" % [ceili(p.hp), int(p.max_hp)], Color("ffb0b0"))
	ci.draw_texture(Assets.icon(1), Vector2(6, by + 9))
	var mcol := Color("4a8fe8") if p.mana_flash <= 0.0 else Color("ff5050")
	_bar(ci, bx, by + 11, 70, p.mana / p.mana_max, mcol, Color("101a3a"))
	_text(ci, Vector2(bx + 74, by + 16), str(int(p.mana)), Color("a8c8ff"))
	ci.draw_texture(Assets.icon(2), Vector2(6, by + 20))
	_bar(ci, bx, by + 22, 70, p.lev / p.lev_max, Color("f0e0a0"), Color("2e2a1e"))
	# --- bottom-center: weapon slots
	var slot_tex := Assets.tex("slot")
	var sx0 := 240.0 - (4 * 20 + 3 * 3) * 0.5
	var sy := 246.0
	for i in 4:
		var x := floorf(sx0 + i * 23)
		var w: Weapon = p.weapons[i]
		var frame := 1 if i == p.slot else (0 if w != null else 2)
		ci.draw_texture_rect_region(slot_tex, Rect2(x, sy, 20, 20), Rect2(frame * 20, 0, 20, 20))
		if w != null:
			var t := w.icon()
			var c := Vector2(x + 10, sy + 10)
			var ang := 0.0 if w.type == Weapon.FLASK else -PI * 0.25
			ci.draw_set_transform(c, ang, Vector2.ONE)
			ci.draw_texture(t, -(Vector2(t.get_width(), t.get_height()) * 0.5).floor())
			ci.draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
			if w.cooldown > 0.05 and i == p.slot and w.uses_spells():
				ci.draw_rect(Rect2(x + 2, sy + 17, 16 * clampf(w.cooldown / maxf(0.01, w.cast_delay + w.recharge), 0.0, 1.0), 1), Color(1, 1, 1, 0.6))
			if w.type == Weapon.FLASK:
				ci.draw_rect(Rect2(x + 2, sy + 17, 16, 1), Color(0, 0, 0, 0.6))
				ci.draw_rect(Rect2(x + 2, sy + 17, 16 * clampf(w.amount / Weapon.FLASK_MAX, 0.0, 1.0), 1), w.main_color())
		_text(ci, Vector2(x + 2, sy + 8), str(i + 1), Color(1, 1, 1, 0.55))
	var cw: Weapon = p.current_weapon()
	if cw:
		if cw.uses_spells():
			# spell slots as icons, the next one to be cast highlighted
			var n := cw.spells.size()
			var iw := 17.0
			var ix0 := floorf(240.0 - n * iw * 0.5)
			var iy := sy - 19.0
			var nxt := cw.cursor % maxi(1, n)
			for k in n:
				var r := Rect2(ix0 + k * iw, iy, 16, 16)
				var sid: String = cw.spells[k]
				if sid == "":
					ci.draw_rect(r, Color(0.08, 0.06, 0.12, 0.85))
					ci.draw_rect(r, Color("3a3245"), false, 1.0)
				else:
					ci.draw_texture(Spells.icon_of(sid), r.position)
				if k == nxt:
					ci.draw_rect(r.grow(1), Color("f2c14e"), false, 1.0)
			_text_c(ci, 240, iy - 3, cw.name, cw.main_color().lerp(Color.WHITE, 0.55))
		elif cw.type == Weapon.FLASK:
			_text_c(ci, 240, sy - 12, "%s · %s %d/%d" % [cw.name, cw.liquid_name(), int(cw.amount), int(Weapon.FLASK_MAX)], cw.main_color().lerp(Color.WHITE, 0.5))
			_text_c(ci, 240, sy - 3, "vasen kaada · oikea heitä · F juo", Color("a89cc0"))
		else:
			_text_c(ci, 240, sy - 3, cw.name, cw.main_color().lerp(Color.WHITE, 0.55))
	# --- boss bar
	var b := game.boss
	if b and is_instance_valid(b) and b.awake and not b.dead:
		var bw2 := 220.0
		var bx2 := 240.0 - bw2 * 0.5
		_text_c(ci, 240, 38, "Portinvartija" + (" – raivo" if b.phase == 2 else ""), Color("ff9cb4") if b.phase == 2 else Color("d7b0ff"))
		ci.draw_rect(Rect2(bx2 - 1, 41, bw2 + 2, 6), Color("140c1c"))
		ci.draw_rect(Rect2(bx2, 42, bw2, 4), Color("2a1030"))
		ci.draw_rect(Rect2(bx2, 42, floorf(bw2 * clampf(b.hp / b.max_hp, 0.0, 1.0)), 4), Color("c8283c") if b.phase == 2 else Color("9a5cf0"))
		ci.draw_rect(Rect2(bx2, 42, floorf(bw2 * clampf(b.hp / b.max_hp, 0.0, 1.0)), 1), Color("ffb0c8") if b.phase == 2 else Color("d7b0ff"))
	# --- pickup prompt
	var pk := game.nearby_pickup
	if pk and pk.weapon:
		var lines := pk.weapon.describe()
		var bw := 230.0
		var bh := 26.0 + lines.size() * 10.0
		var bxp := 240.0 - bw * 0.5
		var byp := 150.0
		ci.draw_rect(Rect2(bxp, byp, bw, bh), Color(0.05, 0.03, 0.08, 0.88))
		ci.draw_rect(Rect2(bxp, byp, bw, bh), Color("5a4a6e"), false, 1.0)
		_text_c(ci, 240, byp + 11, "[E] Poimi: " + pk.weapon.name, Color("ffe08a"))
		_text_c(ci, 240, byp + 21, pk.weapon.type_name(), pk.weapon.main_color())
		for k in lines.size():
			_text_c(ci, 240, byp + 32 + k * 10, lines[k], Color("d8d0e8"))
	# --- messages
	for k in messages.size():
		var m: Array = messages[k]
		var a := clampf(3.5 - float(m[2]), 0.0, 1.0)
		var col: Color = m[1]
		col.a = a
		_text_c(ci, 240, 52 + k * 11, m[0], col)
	# --- level title card
	if title_t < 3.6:
		var a2 := clampf(minf(title_t * 2.0, (3.6 - title_t) * 1.5), 0.0, 1.0)
		_text_c(ci, 240, 98, title_text, Color(1, 0.95, 0.85, a2), 24)
		_text_c(ci, 240, 114, title_sub, Color(0.8, 0.7, 1.0, a2))
	# --- hurt vignette
	if p.hurt_timer > 0.0:
		ci.draw_rect(Rect2(0, 0, 480, 270), Color(0.8, 0.0, 0.05, p.hurt_timer * 0.6))
	if p.hp < p.max_hp * 0.25 and not p.dead:
		var pulse := 0.08 + 0.06 * sin(Time.get_ticks_msec() * 0.008)
		ci.draw_rect(Rect2(0, 0, 480, 3), Color(0.9, 0.1, 0.1, pulse * 3.0))
		ci.draw_rect(Rect2(0, 267, 480, 3), Color(0.9, 0.1, 0.1, pulse * 3.0))
	# --- crosshair + staff charge
	if not get_tree().paused and not game.paused_for_ui:
		var mp := ci.get_local_mouse_position().round()
		var ch := Assets.tex("crosshair")
		ci.draw_texture(ch, mp - Vector2(floorf(ch.get_width() * 0.5), floorf(ch.get_height() * 0.5)))
		if p.charging and cw and cw.type == Weapon.STAFF:
			var frac := p.charge / maxf(0.05, cw.charge_time)
			ci.draw_rect(Rect2(mp.x - 9, mp.y + 8, 18, 3), Color("140c1c"))
			ci.draw_rect(Rect2(mp.x - 8, mp.y + 9, 16 * frac, 1), cw.main_color().lerp(Color.WHITE, frac * 0.5))
	# --- debug
	if GameState.settings.show_fps and not debug:
		_text(ci, Vector2(436, 12), "FPS %d" % Engine.get_frames_per_second(), Color("a8c8a0"))
	if debug:
		_text(ci, Vector2(380, 12), "FPS %d" % Engine.get_frames_per_second(), Color.WHITE)
		_text(ci, Vector2(380, 22), "Lohkot %d" % game.world.active_count, Color.WHITE)
		_text(ci, Vector2(380, 32), "Hiukk. %d" % game.particles.count, Color.WHITE)
		_text(ci, Vector2(380, 42), "Viholl. %d" % game.enemies.size(), Color.WHITE)
		var mw := game.get_global_mouse_position()
		_text(ci, Vector2(380, 52), Mat.NAMES[game.world.get_mat(int(mw.x), int(mw.y))], Color.WHITE)
