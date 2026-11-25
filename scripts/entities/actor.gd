class_name Actor
extends Node2D
## Base class for everything that moves through the pixel world with an
## axis-aligned hitbox: pixel-exact collision, step-up, liquids, burning.

const GRAVITY := 480.0

var game: Game
var world: PixelWorld
var hw := 3          # hitbox half width
var hh := 6          # hitbox half height
var bx := 0          # hitbox top-left (pixels)
var by := 0
var vel := Vector2.ZERO
var rem := Vector2.ZERO
var on_ground := false
var gravity_scale := 1.0
var max_step := 3
var hp := 10.0
var max_hp := 10.0
var dead := false
var faction := 1     # 0 = player, 1 = enemies
var burning := 0.0
var wet := 0.0
var chilled := 0.0
var hurt_flash := 0.0
var in_liquid := 0
var fire_immune := false
var acid_immune := false
var poisoned := 0.0
var oily := 0.0
var last_hit_by := ""
var _env_tick := 0.0


func init_actor(g: Game) -> void:
	game = g
	world = g.world


func place_at(p: Vector2) -> void:
	bx = int(round(p.x)) - hw
	by = int(round(p.y)) - hh
	rem = Vector2.ZERO
	_sync()


func center() -> Vector2:
	return Vector2(bx + hw, by + hh)


func hit_rect() -> Rect2:
	return Rect2(bx, by, hw * 2, hh * 2)


func _sync() -> void:
	position = Vector2(bx + hw, by + hh)


func is_free_at(x: int, y: int) -> bool:
	return world.rect_free(x, y, hw * 2, hh * 2)


func move_x(amount: float) -> bool:
	rem.x += amount
	var mv := int(round(rem.x))
	if mv == 0:
		return false
	rem.x -= mv
	var s := 1 if mv > 0 else -1
	var w := hw * 2
	var h := hh * 2
	while mv != 0:
		var nx := bx + s
		var edge := nx + w - 1 if s > 0 else nx
		if world.col_free(edge, by, by + h - 1):
			bx = nx
			mv -= s
			continue
		var stepped := false
		if on_ground or gravity_scale == 0.0:
			for up in range(1, max_step + 1):
				if world.rect_free(nx, by - up, w, h):
					bx = nx
					by -= up
					stepped = true
					break
		if stepped:
			mv -= s
		else:
			rem.x = 0.0
			_sync()
			return true
	_sync()
	return false


func move_y(amount: float) -> bool:
	rem.y += amount
	var mv := int(round(rem.y))
	if mv == 0:
		return false
	rem.y -= mv
	var s := 1 if mv > 0 else -1
	var w := hw * 2
	var h := hh * 2
	while mv != 0:
		var ny := by + s
		var edge := ny + h - 1 if s > 0 else ny
		if world.row_free(edge, bx, bx + w - 1):
			by = ny
			mv -= s
		else:
			rem.y = 0.0
			_sync()
			return true
	_sync()
	return false


func check_ground() -> bool:
	return not world.row_free(by + hh * 2, bx, bx + hw * 2 - 1)


## If sand or debris fell into the hitbox, push the actor out.
func unstick() -> void:
	if is_free_at(bx, by):
		return
	for up in range(1, 6):
		if is_free_at(bx, by - up):
			by -= up
			_sync()
			return
	for side in [1, -1, 2, -2, 3, -3]:
		if is_free_at(bx + side, by):
			bx += side
			_sync()
			return


## Standard gravity + liquid physics + movement. Returns true if landed hard.
func physics_move(delta: float, dim_gravity: float = 1.0) -> void:
	in_liquid = 0
	var cm := world.get_mat(bx + hw, by + hh)
	if Mat.KIND[cm] == Mat.K_LIQUID:
		in_liquid = cm
	var g := GRAVITY * gravity_scale * dim_gravity
	if in_liquid != 0 and gravity_scale > 0.0:
		g *= 0.18
		vel *= pow(0.12, delta)
	vel.y += g * delta
	vel.y = minf(vel.y, 330.0)
	if move_x(vel.x * delta):
		vel.x = 0.0
	if move_y(vel.y * delta):
		if vel.y > 0.0:
			on_ground = true
		vel.y = 0.0
	on_ground = check_ground()
	unstick()


## Material contact: acid, lava, fire, water...
func env_effects(delta: float) -> void:
	_env_tick -= delta
	var pts := [Vector2i(bx + hw, by + hh * 2 - 1), Vector2i(bx + hw, by + hh), Vector2i(bx + hw, by + 1)]
	var dmg := 0.0
	var ign := false
	var water := false
	var cause := ""
	var heal_rate := 0.0
	for p in pts:
		var m := world.get_mat(p.x, p.y)
		if m == 0:
			continue
		heal_rate = maxf(heal_rate, Mat.CONTACT_HEAL[m])
		var d := Mat.CONTACT_DMG[m]
		if m == Mat.ACID and acid_immune:
			d = 0.0
		if d > dmg:
			dmg = d
			cause = Mat.NAMES[m]
		if Mat.IGNITES[m] != 0:
			ign = true
			if cause == "":
				cause = Mat.NAMES[m]
		if m == Mat.WATER or m == Mat.SNOW or m == Mat.BLOOD:
			water = true
	if water:
		wet = 2.5
		burning = 0.0
		oily = 0.0
	if heal_rate > 0.0 and hp < max_hp and not dead:
		hp = minf(max_hp, hp + heal_rate * delta)
	if ign and not fire_immune and wet <= 0.0:
		if burning <= 0.0:
			Audio.play_at("fire_ignite", position, -6.0)
		burning = maxf(burning, 9.0 if oily > 0.0 else 3.0)
	if poisoned > 0.0:
		poisoned -= delta
		take_damage(3.0 * delta, "Myrkky", Vector2.ZERO, "env")
	oily = maxf(0.0, oily - delta)
	if dmg > 0.0:
		take_damage(dmg * delta, cause, Vector2.ZERO, "env")
	wet = maxf(0.0, wet - delta)
	chilled = maxf(0.0, chilled - delta)
	if burning > 0.0:
		burning -= delta
		if not fire_immune:
			take_damage(burn_dps() * delta, "Tuli", Vector2.ZERO, "fire")
		if game and game.particles and randf() < 0.6:
			game.particles.spawn(center() + Vector2(randf_range(-hw, hw), randf_range(-hh, hh)), Vector2(randf_range(-10, 10), randf_range(-40, -15)), Color(1.0, randf_range(0.4, 0.8), 0.1), randf_range(0.2, 0.5), -0.2)
		if _env_tick <= 0.0:
			_env_tick = 0.15
			var fx := bx + randi_range(-1, hw * 2)
			var fy := by + randi_range(0, hh * 2)
			var fm := world.get_mat(fx, fy)
			if fm != 0 and Mat.FLAM[fm] > 0:
				world.ignite(fx, fy)
			elif fm == 0 and randf() < 0.3:
				world.place_fire(fx, fy, 20)
	hurt_flash = maxf(0.0, hurt_flash - delta)


func burn_dps() -> float:
	return 6.0


func ignite(t: float = 3.0) -> void:
	if fire_immune or wet > 0.0:
		return
	burning = maxf(burning, t * (3.0 if oily > 0.0 else 1.0))


## Override in subclasses for death handling etc.
func take_damage(amount: float, source: String, knock: Vector2 = Vector2.ZERO, kind: String = "") -> void:
	if dead or amount <= 0.0:
		return
	hp -= amount
	last_hit_by = source
	vel += knock
	if kind != "env" and kind != "fire":
		hurt_flash = 0.15
	if hp <= 0.0:
		hp = 0.0
		die(source)


func die(_source: String) -> void:
	dead = true
