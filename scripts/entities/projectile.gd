class_name Projectile
extends Node2D
## A spell projectile. Moves in 1-pixel sub-steps so it never tunnels through
## thin walls; digs, bounces, pierces, explodes or splashes depending on spell.

var game: Game
var world: PixelWorld
var spell_id := "spark"
var spell: Dictionary
var vel := Vector2.ZERO
var faction := 0
var life := 1.0
var power := 1.0
var dmg := 5.0
var bounces := 0
var pierce := 0
var radius := 2
var hit_list: Array = []
var sprite: Sprite2D
var anim_t := 0.0
var trail_t := 0.0
var dead := false
var age := 0.0
var color := Color.WHITE
var reflected := false
var flask_liquid := 0
var flask_amount := 0.0


func setup(g: Game, id: String, pos: Vector2, dir: Vector2, fac: int, pow_mult: float, dmg_mult: float, speed_mult: float, mods: Dictionary = {}) -> void:
	game = g
	world = g.world
	spell_id = id
	spell = Spells.get_spell(id).duplicate()
	if mods.has("homing"):
		spell["homing"] = maxf(float(spell.get("homing", 0.0)), float(mods["homing"]))
	if mods.has("explode"):
		if spell.has("explode_r"):
			spell["explode_r"] = int(spell["explode_r"]) + 3
		else:
			spell["explode_r"] = int(mods["explode"])
			spell["explode_power"] = 45.0
	faction = fac
	power = pow_mult
	position = pos
	vel = dir.normalized() * float(spell.get("speed", 200.0)) * speed_mult
	life = float(spell.get("life", 1.0)) * (1.0 + (power - 1.0) * 0.25)
	dmg = float(spell.get("damage", 5.0)) * dmg_mult * power
	bounces = int(spell.get("bounces", 0)) + int(mods.get("bounces", 0))
	pierce = int(spell.get("pierce", 0)) + int(mods.get("pierce", 0))
	radius = int(spell.get("radius", 2))
	color = Spells.color_of(id)
	var row := int(spell.get("row", 0))
	var ptex := Assets.tex("projectiles")
	if row * 12 + 12 > ptex.get_height():
		row = 11
	sprite = Sprite2D.new()
	sprite.texture = ptex
	sprite.region_enabled = true
	sprite.region_rect = Rect2(0, row * 12, 12, 12)
	if power > 1.45:
		sprite.scale = Vector2(2, 2)
	add_child(sprite)
	z_index = 3
	_orient()


## Thrown potion flask: shatters on impact and releases its liquid.
func setup_flask(g: Game, w: Weapon, pos: Vector2, dir: Vector2) -> void:
	game = g
	world = g.world
	spell_id = "flask"
	spell = Spells.get_spell("flask").duplicate()
	faction = 0
	position = pos
	vel = dir.normalized() * float(spell["speed"])
	life = float(spell["life"])
	dmg = float(spell["damage"])
	radius = 3
	flask_liquid = w.liquid
	flask_amount = w.amount
	color = Color(0.7, 0.85, 1.0)
	sprite = Sprite2D.new()
	sprite.texture = w.icon()
	add_child(sprite)
	z_index = 3


func _orient() -> void:
	if spell_id == "flask":
		return
	if spell.get("rotate", false):
		sprite.rotation = vel.angle()


func _physics_process(delta: float) -> void:
	if dead:
		return
	age += delta
	life -= delta
	if life <= 0.0:
		if spell.get("expire_explode", false):
			impact(position)
		else:
			_fizzle()
		return
	vel.y += Actor.GRAVITY * float(spell.get("gravity", 0.0)) * delta
	if spell.has("accel"):
		var sp := minf(vel.length() + float(spell["accel"]) * delta, float(spell.get("max_speed", 300.0)))
		vel = vel.normalized() * sp
	if spell.has("homing") and age > 0.12:
		var t := game.nearest_target(position, faction, 170.0)
		if t:
			var want := (t.center() - position).angle()
			var cur := vel.angle()
			var turn := float(spell["homing"]) * delta
			vel = Vector2.from_angle(cur + clampf(angle_difference(cur, want), -turn, turn)) * vel.length()
	var travel := vel * delta
	var steps := maxi(1, int(ceil(travel.length())))
	var st := travel / float(steps)
	for s in steps:
		var np := position + st
		var cx := int(floor(np.x))
		var cy := int(floor(np.y))
		var m := world.get_mat(cx, cy)
		if Mat.SOLID[m] != 0:
			if spell.has("dig_r"):
				var r := int(round(float(spell["dig_r"]) * (0.8 + power * 0.3)))
				var removed := world.carve_circle(cx, cy, r, int(spell.get("dig_power", 60)), 0.2)
				if removed > 0 and randf() < 0.3:
					Audio.play_at("dig", position, -10.0)
				life -= 0.03
				position = np
			elif bounces > 0:
				bounces -= 1
				var damp := float(spell.get("bounce_damp", 0.85))
				var bxs := world.is_solid_at(int(floor(position.x + st.x)), int(floor(position.y)))
				var bys := world.is_solid_at(int(floor(position.x)), int(floor(position.y + st.y)))
				if bxs:
					vel.x = -vel.x
				if bys:
					vel.y = -vel.y
				if not bxs and not bys:
					vel = -vel
				vel *= damp
				if vel.length() > 40.0:
					Audio.play_at("shoot_orb", position, -16.0, 1.6)
				_orient()
				break
			else:
				impact(position)
				return
		else:
			if m != 0:
				var k := Mat.KIND[m]
				if k == Mat.K_LIQUID:
					if spell.get("element", "") == "fire" and (m == Mat.WATER or m == Mat.BLOOD):
						world.set_cell(cx, cy, Mat.STEAM, 50)
						Audio.play_at("steam_hiss", position, -8.0)
						_fizzle()
						return
					if spell_id == "ice":
						world.freeze(cx, cy, 2)
					vel *= 0.97
			position = np
		# Actor hits
		if spell_id != "flask" and (not spell.get("no_hit_die", false) or faction == 1):
			var hit: Actor = game.find_actor_hit(position, radius, faction, hit_list)
			if hit:
				_hit_actor(hit)
				if dead:
					return
	_trail(delta)
	_orient()
	anim_t += delta
	if spell_id == "flask":
		sprite.rotation += 14.0 * delta * signf(vel.x + 0.01)
	else:
		var frame := int(anim_t * 12.0) % 4
		sprite.region_rect.position.x = frame * 12
	game.add_light(position, float(spell.get("light_r", 20.0)) * (0.7 + power * 0.3), spell.get("light", Color.WHITE) * 0.9)


func _hit_actor(a: Actor) -> void:
	var knock := vel.normalized() * (40.0 + dmg * 2.0)
	a.take_damage(dmg, String(spell.get("name", "Loitsu")), knock, String(spell.get("element", "")))
	if spell.get("ignite", false):
		a.ignite(3.0)
	if spell.get("chill", false):
		a.chilled = 2.0
	game.spawn_fx("hit", position, 0.0, color)
	if pierce > 0:
		pierce -= 1
		hit_list.append(a)
	else:
		impact(position)


func impact(p: Vector2) -> void:
	if dead:
		return
	dead = true
	var ip := Vector2i(int(p.x), int(p.y))
	if spell_id == "flask":
		_shatter(ip)
		queue_free()
		return
	var ps := clampf(power, 0.5, 2.2)
	if spell.has("explode_r"):
		var r := int(round(float(spell["explode_r"]) * (0.7 + ps * 0.35)))
		game.explosion(p, r, float(spell.get("explode_power", 50.0)) * (0.7 + ps * 0.3), spell.get("fire", false), dmg * 1.1 + r * 0.6, faction, String(spell.get("name", "")))
	if spell.has("liquid"):
		var lr := int(round(float(spell.get("liquid_r", 4)) * (0.8 + ps * 0.35)))
		world.spawn_blob(ip.x, ip.y, lr, int(spell["liquid"]))
		Audio.play_at("splash", p, -6.0)
		if game.particles:
			game.particles.burst(p, 14, Mat.color_of(int(spell["liquid"]), 0.5), 80.0, 0.6, 1.0)
	if spell.has("crumble_r"):
		var cr := int(round(float(spell["crumble_r"]) * (0.7 + ps * 0.35)))
		world.crumble(ip.x, ip.y, cr, int(spell.get("crumble_power", 80)))
		game.shake(4.0 + cr * 0.2)
		Audio.play_at("crumble", p, 0.0)
		for a in game.actors_in_radius(p, cr, faction):
			a.take_damage(dmg, String(spell.get("name", "")), (a.center() - p).normalized() * 60.0, "earth")
		if game.particles:
			game.particles.burst(p, 30, Color("a8743a"), 90.0, 0.8, 1.0)
	if spell.has("freeze_r"):
		world.freeze(ip.x, ip.y, int(spell["freeze_r"]) + 1)
	if spell.has("extinguish_r"):
		world.extinguish(ip.x, ip.y, int(spell["extinguish_r"]))
	if not spell.has("explode_r"):
		game.spawn_fx("hit", p, 0.0, color)
		if game.particles:
			game.particles.burst(p, 6, color, 60.0, 0.3, 0.3)
	queue_free()


func _shatter(ip: Vector2i) -> void:
	Audio.play_at("glass_break", position, 0.0)
	if game.particles:
		game.particles.burst(position, 14, Color(0.8, 0.9, 1.0), 90.0, 0.5, 1.0)
	if flask_liquid != 0 and flask_amount > 0.0:
		var r := clampi(int(round(sqrt(flask_amount) * 0.8)), 2, 8)
		world.spawn_blob(ip.x, ip.y, r, flask_liquid)
		if game.particles:
			game.particles.burst(position, 10, Mat.color_of(flask_liquid, 0.6), 70.0, 0.6, 1.0)
		if flask_liquid == Mat.LAVA or flask_liquid == Mat.OIL:
			for a in game.actors_in_radius(position, r + 4.0, 0, true):
				if flask_liquid == Mat.LAVA:
					a.ignite(3.0)
				else:
					a.oily = 20.0


func _fizzle() -> void:
	dead = true
	game.spawn_fx("sparkle", position, 0.0, color)
	queue_free()


func _trail(delta: float) -> void:
	trail_t -= delta
	if trail_t > 0.0 or game.particles == null:
		return
	trail_t = 0.025
	var tr := String(spell.get("trail", ""))
	var back := -vel.normalized()
	match tr:
		"spark", "spark_pink", "spark_violet", "ice", "dark":
			var c := color
			if tr == "spark_pink":
				c = Color("ff7ad9")
			elif tr == "dark":
				c = Color("ff3050")
			game.particles.spawn(position + back * 2.0, back * 20.0 + Vector2(randf_range(-10, 10), randf_range(-10, 10)), c, randf_range(0.15, 0.35), 0.0)
		"fire":
			game.particles.spawn(position + back * 2.0, back * 25.0 + Vector2(randf_range(-12, 12), randf_range(-25, 0)), Color(1.0, randf_range(0.35, 0.85), 0.1), randf_range(0.2, 0.45), -0.3)
			if randf() < 0.08:
				world.place_fire(int(position.x + back.x * 4.0), int(position.y + back.y * 4.0), 15)
		"acid", "water":
			game.particles.spawn(position, Vector2(randf_range(-10, 10), randf_range(0, 20)), color, 0.4, 1.0)
		"dust":
			game.particles.spawn(position + back * 2.0, Vector2(randf_range(-20, 20), randf_range(-20, 10)), Color("a8743a"), 0.3, 0.5)
		"fuse":
			game.particles.spawn(position + Vector2(0, -3), Vector2(randf_range(-15, 15), randf_range(-30, -5)), Color(1.0, 0.85, 0.3), 0.25, 0.4)
