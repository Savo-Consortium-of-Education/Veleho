class_name Player
extends Actor
## The sorcerer. Movement, levitation, weapons (wands, staffs, swords), inventory.

const SPEED := 78.0
const JUMP := 168.0
const LEV_SPEED := 92.0
const LEV_ACCEL := 820.0
const SLOTS := 4
const BAG_SIZE := 16

var body: AnimatedSprite2D
var arm_pivot: Node2D
var arm: Sprite2D
var weapon_sprite: Sprite2D
var weapons: Array = [null, null, null, null]
var spell_bag: Array = []
var slot := 0
var mana := 100.0
var mana_max := 100.0
var mana_regen := 30.0
var lev := 2.6
var lev_max := 2.6
var speed_mult := 1.0
var dmg_mult := 1.0
var blast_resist := 0.0
var lifesteal := 0.0
var reach_mult := 1.0
var perks: Array = []
var facing := 1
var aim := Vector2.RIGHT
var coyote := 0.0
var jump_buffer := 0.0
var jump_held := 0.0
var levitating := false
var invuln := 0.0
var hurt_timer := 0.0
var charging := false
var charge := 0.0
var swing_t := 0.0
var swing_total := 0.0
var swing_dir := 1
var swing_base := 0.0
var death_timer := 0.0
var mana_flash := 0.0
var dim_gravity := 1.0
var _was_ground := true
var _charge_sound := false
var debug_aim := Vector2.ZERO  # tests: aim direction override
var pouring := false
var _pour_t := 0.0
var _fill_t := 0.0
var _fill_snd := 0.0


func _ready() -> void:
	hw = 3
	hh = 6
	faction = 0
	z_index = 2
	body = AnimatedSprite2D.new()
	body.sprite_frames = Assets.frames("player", 16, 16, [
		["idle", 0, 4, 6, true], ["walk", 1, 6, 12, true], ["jump", 2, 2, 8, true],
		["fall", 3, 2, 8, true], ["levitate", 4, 4, 10, true], ["hurt", 5, 2, 10, false],
		["death", 6, 6, 8, false],
	])
	body.position = Vector2(0, -2)
	body.play("idle")
	add_child(body)
	arm_pivot = Node2D.new()
	arm_pivot.position = Vector2(0, -2)
	add_child(arm_pivot)
	weapon_sprite = Sprite2D.new()
	weapon_sprite.centered = false
	weapon_sprite.position = Vector2(6, 0)
	arm_pivot.add_child(weapon_sprite)
	arm = Sprite2D.new()
	arm.texture = Assets.tex("player_arm")
	arm.centered = false
	arm.offset = Vector2(-1, -2)
	arm_pivot.add_child(arm)
	_refresh_weapon_sprite()


func load_state(d: Dictionary) -> void:
	max_hp = float(d.get("max_hp", 100.0))
	hp = clampf(float(d.get("hp", max_hp)), 1.0, max_hp)
	mana_max = float(d.get("mana_max", 100.0))
	mana = mana_max
	mana_regen = float(d.get("mana_regen", 30.0))
	lev_max = float(d.get("lev_max", 2.6))
	lev = lev_max
	speed_mult = float(d.get("speed", 1.0))
	dmg_mult = float(d.get("dmg_mult", 1.0))
	fire_immune = bool(d.get("fire_immune", false))
	blast_resist = float(d.get("blast_resist", 0.0))
	lifesteal = float(d.get("lifesteal", 0.0))
	reach_mult = float(d.get("reach_mult", 1.0))
	perks = Array(d.get("perks", []))
	acid_immune = perks.has("acid_skin")
	slot = int(d.get("slot", 0))
	# runtime reset (the Player node is reused between levels)
	dead = false
	burning = 0.0
	wet = 0.0
	chilled = 0.0
	vel = Vector2.ZERO
	invuln = 1.5
	hurt_timer = 0.0
	swing_t = 0.0
	charging = false
	death_timer = 0.0
	if arm_pivot:
		arm_pivot.visible = true
	if body:
		body.play("idle")
	set_physics_process(true)
	weapons = [null, null, null, null]
	var ws: Array = d.get("weapons", [])
	for i in mini(ws.size(), SLOTS):
		var wd = ws[i]
		if wd is Dictionary and not (wd as Dictionary).is_empty():
			weapons[i] = Weapon.from_dict(wd)
	spell_bag = Array(d.get("bag", []))
	spell_bag.resize(BAG_SIZE)
	for i in BAG_SIZE:
		if spell_bag[i] == null:
			spell_bag[i] = ""
	poisoned = 0.0
	oily = 0.0
	if weapons[slot] == null:
		_select_next(1)
	_refresh_weapon_sprite()


## Adds a loose spell to the bag. Returns false when the bag is full.
func add_spell(id: String) -> bool:
	var i := spell_bag.find("")
	if i < 0:
		return false
	spell_bag[i] = id
	return true


func save_state() -> Dictionary:
	var ws: Array = []
	for w in weapons:
		ws.append(w.to_dict() if w != null else {})
	return {
		"hp": hp, "max_hp": max_hp, "mana_max": mana_max, "mana_regen": mana_regen,
		"lev_max": lev_max, "speed": speed_mult, "dmg_mult": dmg_mult,
		"fire_immune": fire_immune, "blast_resist": blast_resist, "lifesteal": lifesteal,
		"reach_mult": reach_mult, "perks": perks.duplicate(), "slot": slot, "weapons": ws,
		"bag": spell_bag.duplicate(),
	}


func current_weapon() -> Weapon:
	return weapons[slot]


func _refresh_weapon_sprite() -> void:
	if weapon_sprite == null:
		return
	var w := current_weapon()
	if w == null:
		weapon_sprite.texture = null
		return
	var t := w.icon()
	weapon_sprite.texture = t
	if w.type == Weapon.FLASK:
		# held neck-first along the arm
		weapon_sprite.rotation = PI * 0.5
		weapon_sprite.offset = Vector2(-5, -11)
	else:
		weapon_sprite.rotation = 0.0
		weapon_sprite.offset = Vector2(-WeaponArt.grip_x(w.type), -int(t.get_height() / 2))
	charging = false
	charge = 0.0


func select_slot(i: int) -> void:
	if i < 0 or i >= SLOTS or i == slot:
		return
	slot = i
	_refresh_weapon_sprite()
	Audio.play("ui_hover", -6.0)


func _select_next(dir: int) -> void:
	for k in range(1, SLOTS + 1):
		var i := posmod(slot + dir * k, SLOTS)
		if weapons[i] != null:
			select_slot(i)
			return


# ---------------------------------------------------------------------------
func _physics_process(delta: float) -> void:
	if game == null or game.paused_for_ui:
		return
	if dead:
		death_timer += delta
		vel.x = move_toward(vel.x, 0.0, 300.0 * delta)
		physics_move(delta, dim_gravity)
		if death_timer > 2.2:
			game.on_player_dead_finished()
			set_physics_process(false)
		return
	_aim()
	_movement(delta)
	physics_move(delta, dim_gravity)
	if on_ground and not _was_ground and vel.y >= 0.0:
		Audio.play("land", -10.0)
	_was_ground = on_ground
	env_effects(delta)
	_weapons(delta)
	mana = minf(mana_max, mana + mana_regen * delta * (1.5 if in_liquid == Mat.AETHER else 1.0))
	if on_ground:
		lev = minf(lev_max, lev + 1.8 * delta)
	if in_liquid == Mat.AETHER:
		lev = minf(lev_max, lev + 3.0 * delta)
	invuln = maxf(0.0, invuln - delta)
	hurt_timer = maxf(0.0, hurt_timer - delta)
	mana_flash = maxf(0.0, mana_flash - delta)
	game.add_light(position + Vector2(0, -2), 115.0, Color(1.0, 0.86, 0.68) * 0.9)
	_animate()


func _aim() -> void:
	var m := get_global_mouse_position()
	if debug_aim != Vector2.ZERO:
		m = position + debug_aim.normalized() * 60.0
	var shoulder := arm_pivot.global_position
	aim = (m - shoulder)
	if aim.length() < 1.0:
		aim = Vector2(facing, 0)
	aim = aim.normalized()
	facing = 1 if m.x >= position.x else -1


func _movement(delta: float) -> void:
	var ix := Input.get_axis("move_left", "move_right")
	var target := ix * SPEED * speed_mult * (0.6 if chilled > 0.0 else 1.0)
	var accel := 1000.0 if on_ground else 620.0
	vel.x = move_toward(vel.x, target, accel * delta)
	if on_ground:
		coyote = 0.1
	else:
		coyote -= delta
	if Input.is_action_just_pressed("jump"):
		jump_buffer = 0.12
	else:
		jump_buffer -= delta
	levitating = false
	if Input.is_action_pressed("jump"):
		jump_held += delta
	else:
		jump_held = 0.0
	if in_liquid != 0:
		if Input.is_action_pressed("jump"):
			vel.y = maxf(vel.y - 700.0 * delta, -85.0)
		return
	if jump_buffer > 0.0 and coyote > 0.0:
		vel.y = -JUMP
		jump_buffer = 0.0
		coyote = 0.0
		on_ground = false
		Audio.play("jump", -8.0)
		return
	if not Input.is_action_pressed("jump") and vel.y < -70.0 and jump_held == 0.0:
		vel.y = lerpf(vel.y, -70.0, 0.35)
	if Input.is_action_pressed("jump") and not on_ground and coyote <= 0.0 and lev > 0.0 and (vel.y > -50.0 or jump_held > 0.22):
		levitating = true
		vel.y = move_toward(vel.y, -LEV_SPEED, LEV_ACCEL * delta)
		lev = maxf(0.0, lev - delta)
		if game.particles and randf() < 0.5:
			game.particles.spawn(position + Vector2(randf_range(-3, 3), 6), Vector2(randf_range(-15, 15), randf_range(20, 45)), Color(1.0, 0.8, 0.4) if randf() < 0.5 else Color(0.5, 0.9, 1.0), 0.35, 0.0)
	if levitating:
		Audio.loop_start("levitate", -14.0)
	else:
		Audio.loop_stop("levitate")


func _weapons(delta: float) -> void:
	for w in weapons:
		if w != null:
			(w as Weapon).cooldown = maxf(0.0, (w as Weapon).cooldown - delta)
	if Input.is_action_just_pressed("slot_1"):
		select_slot(0)
	elif Input.is_action_just_pressed("slot_2"):
		select_slot(1)
	elif Input.is_action_just_pressed("slot_3"):
		select_slot(2)
	elif Input.is_action_just_pressed("slot_4"):
		select_slot(3)
	elif Input.is_action_just_pressed("next_weapon"):
		_select_next(1)
	elif Input.is_action_just_pressed("prev_weapon"):
		_select_next(-1)
	var w := current_weapon()
	# Arm rotation (sword swings override)
	var ang := aim.angle()
	if swing_t > 0.0:
		swing_t -= delta
		var t := 1.0 - clampf(swing_t / swing_total, 0.0, 1.0)
		var half := deg_to_rad((w.arc if w else 120.0) * 0.5)
		ang = swing_base + lerpf(-half, half, ease(t, 0.6)) * swing_dir
	arm_pivot.rotation = ang
	arm_pivot.scale.y = -1.0 if absf(wrapf(ang, -PI, PI)) > PI * 0.5 else 1.0
	if w == null or w.type != Weapon.FLASK:
		if pouring:
			pouring = false
			Audio.loop_stop("potion_pour")
		if Input.is_action_just_pressed("drink"):
			_drink(_first_flask())
	if w == null:
		return
	match w.type:
		Weapon.WAND:
			if Input.is_action_pressed("fire") and w.cooldown <= 0.0:
				if not _cast_from(w, 1.0, 1.0, 1.0):
					w.cooldown = 0.25
				else:
					vel -= aim * 6.0
		Weapon.STAFF:
			if Input.is_action_pressed("fire") and w.cooldown <= 0.0 and not w.filled().is_empty():
				if not charging:
					charging = true
					charge = 0.0
					_charge_sound = false
				charge = minf(charge + delta, w.charge_time)
				if not _charge_sound:
					_charge_sound = true
					Audio.play("staff_charge", -6.0, 2.0 - w.charge_time * 0.8, 0.0)
				if game.particles and randf() < 0.6:
					var tip := tip_position()
					var a := randf() * TAU
					game.particles.spawn(tip + Vector2(cos(a), sin(a)) * 7.0, -Vector2(cos(a), sin(a)) * 25.0, w.main_color(), 0.25, 0.0)
				game.add_light(tip_position(), 16.0 + 30.0 * (charge / w.charge_time), w.main_color() * 0.8)
			elif charging:
				_release_staff(w)
		Weapon.SWORD:
			if Input.is_action_pressed("fire") and w.cooldown <= 0.0 and swing_t <= 0.0:
				_swing(w)
		Weapon.FLASK:
			_flask_update(w, delta)


func tip_position() -> Vector2:
	var w := current_weapon()
	var d := WeaponArt.tip_dist(w.type) if w else 8.0
	return arm_pivot.global_position + aim * (6.0 + d)


## Draws the next cast from a wand/staff. Modifiers apply to the next
## projectile; "draw" modifiers cast several projectiles at once.
## Returns {casts: [[spell_id, mods]], mana: float, wrapped: bool}.
func _draw_cast(w: Weapon) -> Dictionary:
	var n := w.spells.size()
	var res := {"casts": [], "mana": 0.0, "wrapped": false}
	if n == 0 or w.filled().is_empty():
		return res
	var draws := maxi(1, w.multicast)
	var mods := {}
	var guard := 0
	while draws > 0 and guard < n * 3:
		guard += 1
		if w.cursor >= n:
			w.cursor = 0
			res["wrapped"] = true
			if not (res["casts"] as Array).is_empty():
				break
		var sid: String = w.spells[w.cursor]
		w.cursor += 1
		if sid == "":
			continue
		var sp := Spells.get_spell(sid)
		res["mana"] = float(res["mana"]) + float(sp.get("mana", 0.0)) * w.mana_mult
		if Spells.is_modifier(sid):
			var m: Dictionary = sp["mod"]
			if m.has("draw"):
				draws += int(m["draw"])
			else:
				for k in m:
					if k == "dmg" or k == "speed" or k == "power":
						mods[k] = float(mods.get(k, 1.0)) * float(m[k])
					elif k == "homing" or k == "explode":
						mods[k] = maxf(float(mods.get(k, 0.0)), float(m[k]))
					else:
						mods[k] = int(mods.get(k, 0)) + int(m[k])
		else:
			(res["casts"] as Array).append([sid, mods])
			mods = {}
			draws -= 1
	if w.cursor >= n:
		w.cursor = 0
		res["wrapped"] = true
	return res


## Casts the next spell group from a wand or staff. Returns false if nothing
## was cast (empty weapon or not enough mana).
func _cast_from(w: Weapon, power: float, speed_extra: float, cost_mult: float) -> bool:
	var start := w.cursor
	var res := _draw_cast(w)
	var casts: Array = res["casts"]
	if casts.is_empty():
		w.cursor = 0
		return false
	var cost := float(res["mana"]) * cost_mult
	if mana < cost:
		w.cursor = start
		mana_flash = 0.3
		Audio.play("ui_click", -10.0, 0.7)
		return false
	mana -= cost
	var tip := tip_position()
	if not world.line_clear(arm_pivot.global_position, tip):
		tip = arm_pivot.global_position
	for k in casts.size():
		var sid: String = casts[k][0]
		var mods: Dictionary = casts[k][1]
		var sp := Spells.get_spell(sid)
		var fan := (k - (casts.size() - 1) * 0.5) * 7.0
		var spread := 0.0
		if not mods.has("accurate"):
			var ss := float(sp.get("spread", 0.0))
			spread = randf_range(-w.spread, w.spread) + randf_range(-ss, ss)
		var off := deg_to_rad(spread + fan)
		game.cast_spell(sid, tip, aim.rotated(off), 0, power * float(mods.get("power", 1.0)),
			w.dmg_mult * dmg_mult * float(mods.get("dmg", 1.0)),
			w.speed_mult * speed_extra * float(mods.get("speed", 1.0)), mods)
	game.spawn_fx("muzzle", tip, aim.angle(), Spells.color_of(String(casts[0][0])))
	if w.type == Weapon.STAFF:
		w.cooldown = w.recharge if res["wrapped"] else 0.15
	elif res["wrapped"]:
		w.cooldown = w.cast_delay + w.recharge
	else:
		w.cooldown = w.cast_delay
	return true


func _release_staff(w: Weapon) -> void:
	charging = false
	var t := clampf(charge / maxf(0.05, w.charge_time), 0.0, 1.0)
	charge = 0.0
	var pw := lerpf(0.55, 2.0, t)
	if not _cast_from(w, pw, lerpf(0.85, 1.3, t), 0.5 + t):
		w.cooldown = 0.2
		return
	Audio.play("staff_release", -4.0 + t * 4.0)
	vel -= aim * (15.0 + 50.0 * t)
	if t > 0.8:
		game.shake(2.5)


func _swing(w: Weapon) -> void:
	w.cooldown = w.swing_time
	swing_total = w.swing_time * 0.75
	swing_t = swing_total
	swing_dir = -swing_dir
	swing_base = aim.angle()
	var reach := w.reach * reach_mult
	game.sword_strike(self, center() + Vector2(0, -2), aim, w, reach, w.damage * dmg_mult, swing_dir)
	vel.x += aim.x * 35.0
	Audio.play("sword_swing", -2.0)


# ---------------------------------------------------------------------------
# Potion flasks
# ---------------------------------------------------------------------------
func _first_flask() -> Weapon:
	for w in weapons:
		if w != null and (w as Weapon).type == Weapon.FLASK:
			return w
	return null


func _flask_update(w: Weapon, delta: float) -> void:
	var tip := tip_position()
	var was_pouring := pouring
	pouring = false
	if Input.is_action_pressed("fire") and w.amount > 0.0 and w.liquid != 0:
		pouring = true
		_pour_t -= delta
		while _pour_t <= 0.0 and w.amount > 0.0:
			_pour_t += 0.02
			w.amount = maxf(0.0, w.amount - 1.0)
			var v := aim * randf_range(70.0, 115.0) + Vector2(randf_range(-12, 12), randf_range(-12, 12))
			game.particles.spawn_material(tip, v, w.liquid, w.liquid)
		if w.amount <= 0.0:
			w.liquid = 0
		_refresh_weapon_sprite_texture()
	elif w.amount < Weapon.FLASK_MAX:
		_fill_t -= delta
		if _fill_t <= 0.0:
			_fill_t = 0.03
			if _absorb(tip, w) > 0:
				_refresh_weapon_sprite_texture()
				_fill_snd -= 0.03
				if _fill_snd <= 0.0:
					_fill_snd = 0.3
					Audio.play("flask_fill", -8.0)
	if pouring and not was_pouring:
		Audio.loop_start("potion_pour", -10.0)
	elif was_pouring and not pouring:
		Audio.loop_stop("potion_pour")
	if Input.is_action_just_pressed("alt_fire"):
		_throw_flask(w)
	elif Input.is_action_just_pressed("drink"):
		_drink(w)


func _refresh_weapon_sprite_texture() -> void:
	var w := current_weapon()
	if w and weapon_sprite:
		weapon_sprite.texture = w.icon()


## Sucks liquid cells around the flask mouth into the flask.
func _absorb(tip: Vector2, w: Weapon) -> int:
	var got := 0
	var cx := int(tip.x)
	var cy := int(tip.y)
	for dy in range(-2, 3):
		for dx in range(-2, 3):
			if got >= 4 or w.amount >= Weapon.FLASK_MAX:
				return got
			var m := world.get_mat(cx + dx, cy + dy)
			if m == 0 or Mat.KIND[m] != Mat.K_LIQUID:
				continue
			if w.amount > 0.0 and w.liquid != m:
				continue
			w.liquid = m
			world.set_cell(cx + dx, cy + dy, Mat.EMPTY, 0)
			w.amount = minf(Weapon.FLASK_MAX, w.amount + 1.0)
			got += 1
	return got


func _throw_flask(w: Weapon) -> void:
	var tip := tip_position()
	if not world.line_clear(arm_pivot.global_position, tip):
		tip = arm_pivot.global_position
	game.throw_flask(w, tip, aim)
	weapons[slot] = null
	Audio.loop_stop("potion_pour")
	pouring = false
	Audio.play("shoot_bomb", -6.0, 1.3)
	_refresh_weapon_sprite()


func _drink(w: Weapon) -> void:
	if w == null:
		game.hud.message("Sinulla ei ole pulloa.", Color("a89cc0"))
		return
	if w.amount <= 0.0 or w.liquid == 0:
		game.hud.message("Pullo on tyhjä.", Color("a89cc0"))
		return
	var gulp := minf(25.0, w.amount)
	var liq := w.liquid
	w.amount -= gulp
	if w.amount <= 0.0:
		w.liquid = 0
	_refresh_weapon_sprite_texture()
	Audio.play("potion_drink")
	match liq:
		Mat.WATER:
			wet = 8.0
			burning = 0.0
			heal(3.0)
			game.hud.message("Virkistävää.", Color("8fc8ff"))
		Mat.ELONNESTE:
			heal(gulp * 2.0)
			Audio.play("heal", -4.0)
			game.hud.message("+%d elämää" % int(gulp * 2.0), Color("ff9cc4"))
			game.floating_text(position + Vector2(0, -14), "+%d" % int(gulp * 2.0), Color("ff9cc4"))
		Mat.AETHER:
			mana = mana_max
			lev = lev_max
			Audio.play("heal", -4.0, 1.4)
			game.hud.message("Taikavoimat virtaavat!", Color("8fe8ff"))
		Mat.BLOOD:
			heal(gulp * 0.4)
			game.hud.message("Rautainen maku.", Color("d86070"))
		Mat.OIL:
			oily = 25.0
			game.hud.message("Yäk, öljyä. Vältä tulta!", Color("c8a070"))
		Mat.ACID:
			take_damage(gulp * 1.2, "Happo", Vector2.ZERO, "env")
			game.hud.message("Happo polttaa kurkkua!", Color("b2ff63"))
		Mat.LAVA:
			take_damage(gulp * 3.0, "Laava", Vector2.ZERO, "env")
			ignite(4.0)
			game.hud.message("Huono idea.", Color("ff8a3a"))
		Mat.SLUDGE:
			poisoned = 8.0
			Audio.play("poison", -4.0)
			game.hud.message("Myrkkyä!", Color("a8d050"))
		_:
			game.hud.message("Ei vaikutusta.", Color("a89cc0"))


# ---------------------------------------------------------------------------
func take_damage(amount: float, source: String, knock: Vector2 = Vector2.ZERO, kind: String = "") -> void:
	if dead:
		return
	if kind != "env" and kind != "fire":
		if invuln > 0.0:
			return
		invuln = 0.55
		hurt_timer = 0.25
		Audio.play("player_hurt", -2.0)
		game.shake(3.0)
	if kind == "blast":
		amount *= 1.0 - blast_resist
	super.take_damage(amount, source, knock, kind)
	if amount >= 1.0:
		game.floating_text(position + Vector2(0, -12), str(int(round(amount))), Color("ff5a5a"), true)


func heal(amount: float) -> void:
	hp = minf(max_hp, hp + amount)


func die(source: String) -> void:
	dead = true
	death_timer = 0.0
	arm_pivot.visible = false
	body.play("death")
	Audio.loop_stop("levitate")
	Audio.play("player_die")
	game.shake(6.0)
	if game.particles:
		for k in 40:
			game.particles.spawn_material(center(), Vector2(randf_range(-80, 80), randf_range(-140, -20)), Mat.BLOOD if k % 3 == 0 else 0, Mat.BLOOD)
	game.on_player_died(source)


func _animate() -> void:
	body.flip_h = facing < 0
	var anim := "idle"
	if hurt_timer > 0.0:
		anim = "hurt"
	elif levitating:
		anim = "levitate"
	elif not on_ground and in_liquid == 0:
		anim = "jump" if vel.y < 0.0 else "fall"
	elif absf(vel.x) > 10.0:
		anim = "walk"
	if body.animation != anim:
		body.play(anim)
	var flash := invuln > 0.0 and int(invuln * 20.0) % 2 == 0
	body.modulate = Color(3, 3, 3) if hurt_flash > 0.0 else (Color(1, 1, 1, 0.5) if flash else Color.WHITE)
	if burning > 0.0:
		body.modulate = body.modulate * Color(1.4, 0.9, 0.7)
