class_name Game
extends Node2D
## One run in progress: owns the world, entities, camera, lighting and HUD.

signal died(info: Dictionary)
signal quit_to_menu

const VIEW := Vector2(480, 270)
const MAX_LIGHTS := 64

var world: PixelWorld
var particles: Particles
var player: Player
var entities: Node2D
var projectiles: Node2D
var fx_layer: Node2D
var texts: FloatingTexts
var camera: Camera2D
var light_layer: CanvasLayer
var light_rect: ColorRect
var light_mat: ShaderMaterial
var hud: Hud
var dim: Dictionary = {}
var dim_gravity := 1.0
var level := 1
var paused_for_ui := true
var portal: Portal
var enemies: Array[Enemy] = []
var boss: EnemyBoss = null
var nearby_pickup: Pickup = null
var cam_pos := Vector2.ZERO
var _shake := 0.0
var _lp_cur := PackedVector3Array()
var _lc_cur := PackedVector3Array()
var _lp_pub := PackedVector3Array()
var _lc_pub := PackedVector3Array()
var _flashes: Array = []
var _ending := false
var pause_menu: CanvasLayer
var perk_ui: CanvasLayer
var inventory_ui: CanvasLayer


func _ready() -> void:
	world = PixelWorld.new()
	world.name = "World"
	add_child(world)
	entities = Node2D.new()
	entities.name = "Entities"
	add_child(entities)
	player = Player.new()
	player.name = "Player"
	add_child(player)
	projectiles = Node2D.new()
	projectiles.name = "Projectiles"
	add_child(projectiles)
	particles = Particles.new()
	particles.name = "Particles"
	add_child(particles)
	particles.world = world
	world.particles = particles
	fx_layer = Node2D.new()
	fx_layer.name = "FX"
	fx_layer.z_index = 5
	add_child(fx_layer)
	texts = FloatingTexts.new()
	texts.z_index = 6
	add_child(texts)
	camera = Camera2D.new()
	add_child(camera)
	camera.make_current()
	light_layer = CanvasLayer.new()
	light_layer.layer = 5
	add_child(light_layer)
	light_rect = ColorRect.new()
	light_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	light_rect.position = Vector2.ZERO
	light_rect.size = VIEW
	light_mat = ShaderMaterial.new()
	light_mat.shader = load("res://shaders/light.gdshader")
	light_rect.material = light_mat
	light_layer.add_child(light_rect)
	hud = Hud.new()
	hud.game = self
	add_child(hud)
	Input.mouse_mode = Input.MOUSE_MODE_HIDDEN


func _exit_tree() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	Audio.stop_all_loops()


func start() -> void:
	load_level()


# ---------------------------------------------------------------------------
# Level lifecycle
# ---------------------------------------------------------------------------
func load_level() -> void:
	paused_for_ui = true
	hud.show_loading(true)
	Audio.stop_all_loops()
	await get_tree().process_frame
	await get_tree().process_frame
	_clear_level()
	level = int(GameState.run["level"])
	dim = Dimensions.get_def(GameState.dimension_for_level(level))
	dim_gravity = float(dim["gravity"])
	var saved := GameState.load_world_save()
	if not saved.is_empty():
		_restore_world(saved)
		return
	var gen := WorldGen.new()
	var info := gen.generate(world, GameState.level_seed(level), level, dim, GameState.is_boss_level(level))
	world.set_background(dim["bg_dark"], dim["bg_light"], dim["stars"])
	world.upload()
	_setup_lighting()
	# Player
	player.init_actor(self)
	player.load_state(GameState.run["player"])
	player.dim_gravity = dim_gravity
	player.place_at(info["spawn"])
	cam_pos = player.position
	_update_camera(1.0)
	# Enemies, items, portal
	for e in info["enemies"]:
		spawn_enemy(String(e[0]), e[1])
	for it in info["items"]:
		_spawn_item(it)
	portal = Portal.new()
	entities.add_child(portal)
	portal.setup(self, info["portal"])
	if info.has("boss"):
		var bi: Dictionary = info["boss"]
		boss = EnemyBoss.new()
		entities.add_child(boss)
		boss.setup_boss(self, level, dim, bi["pos"], bi["arena"])
		boss.place_at(bi["pos"])
		enemies.append(boss)
		portal.sealed = true
	var arrive := spawn_fx("portal", player.position + Vector2(0, -6), 0.0, Color(1, 1, 1, 0.9))
	if arrive:
		var tw := create_tween()
		tw.tween_property(arrive, "modulate:a", 0.0, 1.6)
		tw.tween_callback(arrive.queue_free)
	Audio.play_music(String(dim["music"]))
	Audio.play("level_start", -4.0)
	# Checkpoint: the run is saved at the start of every level.
	GameState.run["player"] = player.save_state()
	GameState.save_run()
	hud.show_loading(false)
	hud.show_title("Taso %d" % level, String(dim["name"]))
	paused_for_ui = false


func _setup_lighting() -> void:
	var amb: Color = dim["ambient"]
	light_mat.set_shader_parameter("cells", world.tex)
	light_mat.set_shader_parameter("palette", Mat.palette())
	light_mat.set_shader_parameter("world_size", Vector2(world.W, world.H))
	light_mat.set_shader_parameter("view_size", VIEW)
	light_mat.set_shader_parameter("ambient", Vector3(amb.r, amb.g, amb.b))


# ---------------------------------------------------------------------------
# Full world save (mid-level). Written on "save and quit" / window close,
# consumed (deleted) when the run continues, so it can't be reloaded twice.
# ---------------------------------------------------------------------------
func save_world() -> bool:
	if paused_for_ui or _ending or player == null or player.dead or world.W == 0:
		return false
	var data := {
		"version": 1,
		"seed": int(GameState.run["seed"]),
		"level": level,
		"W": world.W,
		"H": world.H,
		"cells": world.cells,
		"player": player.save_state(),
		"player_pos": player.position,
		"mana": player.mana,
		"lev": player.lev,
		"enemies": [],
		"pickups": [],
		"portal": {},
		"boss": {},
		"stats": (GameState.run["stats"] as Dictionary).duplicate(),
	}
	for e in enemies:
		if not is_instance_valid(e) or e.dead or e is EnemyBoss:
			continue
		data["enemies"].append({"kind": e.kind, "pos": e.position, "hp": e.hp})
	for c in entities.get_children():
		var pk := c as Pickup
		if pk and not pk.collected and not pk.is_queued_for_deletion():
			data["pickups"].append(pk.to_save())
	if portal:
		data["portal"] = {"pos": portal.position, "sealed": portal.sealed}
	if boss and is_instance_valid(boss) and not boss.dead:
		data["boss"] = {"pos": boss.position, "hp": boss.hp, "phase": boss.phase, "home": boss.home, "arena": boss.arena, "awake": boss.awake}
	return GameState.write_world_save(data)


func _restore_world(data: Dictionary) -> void:
	world.setup(int(data["W"]), int(data["H"]))
	var cells: PackedByteArray = data["cells"]
	if cells.size() == world.cells.size():
		world.cells = cells
	world.set_background(dim["bg_dark"], dim["bg_light"], dim["stars"])
	world.tex_dirty = true
	world.upload()
	world.wake_all()
	_setup_lighting()
	player.init_actor(self)
	player.load_state(data["player"])
	player.dim_gravity = dim_gravity
	player.place_at(data["player_pos"])
	player.mana = float(data.get("mana", player.mana_max))
	player.lev = float(data.get("lev", player.lev_max))
	cam_pos = player.position
	_update_camera(1.0)
	GameState.run["stats"] = data.get("stats", GameState.run["stats"])
	for e in data.get("enemies", []):
		var en := spawn_enemy(String(e["kind"]), e["pos"])
		en.hp = minf(float(e["hp"]), en.max_hp)
	for pd in data.get("pickups", []):
		_restore_pickup(pd)
	var pdata: Dictionary = data.get("portal", {})
	if not pdata.is_empty():
		portal = Portal.new()
		entities.add_child(portal)
		portal.setup(self, pdata["pos"])
		portal.sealed = bool(pdata.get("sealed", false))
	var bd: Dictionary = data.get("boss", {})
	if not bd.is_empty():
		boss = EnemyBoss.new()
		entities.add_child(boss)
		boss.setup_boss(self, level, dim, bd["home"], bd["arena"])
		boss.place_at(bd["pos"])
		boss.hp = float(bd["hp"])
		boss.phase = int(bd.get("phase", 1))
		if bool(bd.get("awake", false)):
			boss.awake = true
			Audio.play_music("boss", 1.0)
		enemies.append(boss)
	if not (boss and boss.awake):
		Audio.play_music(String(dim["music"]))
	# One-shot: the mid-level save is consumed when continuing.
	GameState.delete_world_save()
	hud.show_loading(false)
	hud.show_title("Taso %d" % level, String(dim["name"]) + " – jatketaan")
	paused_for_ui = false


func _restore_pickup(pd: Dictionary) -> void:
	var kind := String(pd.get("kind", "gold"))
	var pos: Vector2 = pd.get("pos", Vector2.ZERO)
	match kind:
		"weapon":
			var w := Weapon.from_dict(pd.get("weapon", {}))
			spawn_weapon_pickup(w, pos, bool(pd.get("float", false)))
		"spell":
			spawn_pickup("spell", pos, String(pd.get("spell", "spark")))
		"gold":
			spawn_pickup("gold", pos, int(pd.get("value", 5)))
		_:
			spawn_pickup(kind, pos, null)


func _clear_level() -> void:
	for c in entities.get_children():
		c.queue_free()
	for c in projectiles.get_children():
		c.queue_free()
	for c in fx_layer.get_children():
		c.queue_free()
	enemies.clear()
	boss = null
	particles.clear()
	texts.clear()
	_flashes.clear()
	nearby_pickup = null
	portal = null


func enter_portal() -> void:
	if _ending:
		return
	Audio.play("portal_enter")
	spawn_fx("sparkle", player.position, 0.0, Color(0.8, 0.6, 1.0))
	paused_for_ui = true
	player.heal(player.max_hp * 0.25)
	GameState.run["player"] = player.save_state()
	GameState.run["level"] = level + 1
	GameState.delete_world_save()
	GameState.save_run()
	var ui := PerkChoice.new()
	perk_ui = ui
	add_child(ui)
	ui.setup(Perks.choices(GameState.level_seed(level) ^ 0x5eed, player.perks), level)
	ui.chosen.connect(_on_perk_chosen)


func _on_perk_chosen(id: String) -> void:
	if perk_ui:
		perk_ui.queue_free()
		perk_ui = null
	Perks.apply(id, player)
	Audio.play("perk_choose")
	GameState.run["player"] = player.save_state()
	GameState.run["level"] = level + 1
	load_level()


func on_player_died(source: String) -> void:
	if _ending:
		return
	_ending = true
	GameState.record_death(source, "")
	Audio.stop_music(2.0)


func on_player_dead_finished() -> void:
	Audio.play("game_over")
	died.emit(GameState.last_death)


func on_boss_awake(_b: EnemyBoss) -> void:
	Audio.play_music("boss", 1.0)
	hud.message("Portinvartija herää!", Color("ff6b8a"))


func on_boss_killed(b: EnemyBoss) -> void:
	Audio.play_music(String(dim["music"]), 3.0)
	hud.message("Portinvartija on kukistettu! Portti aukeaa.", Color("ffe08a"))
	var c := b.center()
	for k in 5:
		get_tree().create_timer(0.25 * k).timeout.connect(func():
			if is_instance_valid(self):
				explosion(c + Vector2(randf_range(-14, 14), randf_range(-14, 14)), 8, 30.0, false, 0.0, 2, ""))
	get_tree().create_timer(1.4).timeout.connect(func():
		if not is_instance_valid(self):
			return
		if portal:
			portal.unseal()
		spawn_gold(c, 60 + 25 * b.boss_index)
		spawn_gold(c, 40)
		spawn_pickup("heart", c, null)
		var wpk := spawn_weapon_pickup(WeaponGen.generate(randi(), level + 2), c + Vector2(0, -6), false)
		wpk.vel = Vector2(randf_range(-40, 40), -100)
		for k in 2:
			var sp := spawn_pickup("spell", c, Spells.random_spell(randi(), level + 2))
			sp.vel = Vector2(randf_range(-70, 70), -110))
	boss = null


func on_enemy_killed(_e: Enemy, _source: String) -> void:
	var st: Dictionary = GameState.run["stats"]
	st["kills"] = int(st["kills"]) + 1
	if player and not player.dead and player.lifesteal > 0.0:
		player.heal(player.lifesteal)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
func _physics_process(delta: float) -> void:
	# publish the lights collected during the previous physics tick
	_lp_pub = _lp_cur
	_lc_pub = _lc_cur
	_lp_cur = PackedVector3Array()
	_lc_cur = PackedVector3Array()
	if paused_for_ui:
		return
	world.step()
	var n := 0
	while not world.pending_explosions.is_empty() and n < 4:
		var e: Vector3i = world.pending_explosions.pop_front()
		explosion(Vector2(e.x, e.y), e.z, 70.0, true, 18.0, 2, "Ruuti")
		n += 1
	if not player.dead:
		GameState.run["stats"]["time"] = float(GameState.run["stats"]["time"]) + delta
	# enemies bookkeeping
	var i := 0
	while i < enemies.size():
		if not is_instance_valid(enemies[i]):
			enemies.remove_at(i)
		else:
			i += 1
	_find_nearby_pickup()
	if nearby_pickup and Input.is_action_just_pressed("interact") and not player.dead:
		_pick_weapon(nearby_pickup)
	# flashes
	var k := 0
	while k < _flashes.size():
		var f: Array = _flashes[k]
		f[3] -= delta
		if f[3] <= 0.0:
			_flashes.remove_at(k)
			continue
		var c: Color = f[2]
		add_light(f[0], f[1], c * (f[3] / f[4]))
		k += 1


func _process(delta: float) -> void:
	if world.tex == null:
		return
	world.upload()
	_update_camera(delta)
	_upload_lights()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("pause") and not paused_for_ui and not player.dead:
		open_pause()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("inventory") and not paused_for_ui and not player.dead:
		open_inventory()
		get_viewport().set_input_as_handled()
	if event is InputEventKey and event.pressed and event.physical_keycode == KEY_F3:
		hud.debug = not hud.debug


func open_inventory() -> void:
	if inventory_ui:
		return
	var inv := InventoryMenu.new()
	inventory_ui = inv
	add_child(inv)
	inv.setup(self)
	inv.closed.connect(func():
		inventory_ui = null
		get_tree().paused = false
		Input.mouse_mode = Input.MOUSE_MODE_HIDDEN)
	get_tree().paused = true


func open_pause() -> void:
	if pause_menu:
		return
	var pm := PauseMenu.new()
	pause_menu = pm
	add_child(pm)
	pm.resumed.connect(func():
		pause_menu = null
		get_tree().paused = false
		Input.mouse_mode = Input.MOUSE_MODE_HIDDEN)
	pm.quit_requested.connect(func():
		get_tree().paused = false
		save_world()
		quit_to_menu.emit())
	get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _update_camera(delta: float) -> void:
	if player == null:
		return
	var target := player.position + Vector2(0, -8)
	var m := get_global_mouse_position() - player.position
	target += m.limit_length(160.0) * 0.18
	cam_pos = cam_pos.lerp(target, 1.0 - pow(0.0005, delta))
	var half := VIEW * 0.5
	if world.W > 0:
		cam_pos.x = clampf(cam_pos.x, half.x, maxf(half.x, world.W - half.x))
		cam_pos.y = clampf(cam_pos.y, half.y, maxf(half.y, world.H - half.y))
	camera.global_position = cam_pos.round()
	_shake = maxf(0.0, _shake - delta * 18.0)
	camera.offset = Vector2(randf_range(-1, 1), randf_range(-1, 1)) * _shake
	camera.offset = camera.offset.round()
	Audio.listener = cam_pos


func shake(amount: float) -> void:
	_shake = clampf(maxf(_shake, amount * GameState.settings.shake), 0.0, 9.0)


# ---------------------------------------------------------------------------
# Lights
# ---------------------------------------------------------------------------
func add_light(p: Vector2, r: float, c: Color) -> void:
	if _lp_cur.size() >= MAX_LIGHTS:
		return
	if absf(p.x - cam_pos.x) > VIEW.x * 0.5 + r or absf(p.y - cam_pos.y) > VIEW.y * 0.5 + r:
		return
	_lp_cur.append(Vector3(p.x, p.y, r))
	_lc_cur.append(Vector3(c.r, c.g, c.b))


func flash(p: Vector2, r: float, c: Color, dur: float) -> void:
	_flashes.append([p, r, c, dur, dur])


func _upload_lights() -> void:
	var lp := PackedVector3Array()
	var lc := PackedVector3Array()
	lp.resize(MAX_LIGHTS)
	lc.resize(MAX_LIGHTS)
	var n := mini(_lp_pub.size(), MAX_LIGHTS)
	for i in n:
		lp[i] = _lp_pub[i]
		lc[i] = _lc_pub[i]
	light_mat.set_shader_parameter("light_count", n)
	light_mat.set_shader_parameter("light_pos", lp)
	light_mat.set_shader_parameter("light_col", lc)
	light_mat.set_shader_parameter("cam_origin", camera.global_position + camera.offset - VIEW * 0.5)


# ---------------------------------------------------------------------------
# Spawning
# ---------------------------------------------------------------------------
func spawn_enemy(kind: String, pos: Vector2) -> Enemy:
	var e: Enemy
	match kind:
		"bat":
			e = EnemyBat.new()
		"caster":
			e = EnemyCaster.new()
		"wisp":
			e = EnemyWisp.new()
		"golem":
			e = EnemyGolem.new()
		_:
			e = EnemySlime.new()
	entities.add_child(e)
	e.setup(self, level, dim)
	e.place_at(pos)
	e.unstick()
	enemies.append(e)
	return e


func _spawn_item(it: Array) -> void:
	var kind := String(it[0])
	var pos: Vector2 = it[1]
	match kind:
		"weapon":
			var w := WeaponGen.generate(int(it[2]), level)
			spawn_weapon_pickup(w, pos, true)
		"gold":
			spawn_pickup("gold", pos, int(it[2]))
		"spell":
			spawn_pickup("spell", pos, Spells.random_spell(int(it[2]), level))
		"flask":
			spawn_weapon_pickup(WeaponGen.make_flask(int(it[2]), level), pos, false)
		_:
			spawn_pickup(kind, pos, null)


func spawn_pickup(kind: String, pos: Vector2, data) -> Pickup:
	var p := Pickup.new()
	entities.add_child(p)
	p.setup_pickup(self, kind, pos, data, false)
	return p


func spawn_weapon_pickup(w: Weapon, pos: Vector2, floating: bool) -> Pickup:
	var p := Pickup.new()
	entities.add_child(p)
	p.setup_pickup(self, "weapon", pos, w, floating)
	return p


func spawn_gold(pos: Vector2, amount: int) -> void:
	var n := clampi(amount / 5, 1, 4)
	for i in n:
		var p := spawn_pickup("gold", pos + Vector2(randf_range(-3, 3), -2), maxi(1, amount / n))
		p.vel = Vector2(randf_range(-50, 50), randf_range(-90, -40))


func spawn_fx(fx_name: String, pos: Vector2, rot: float, tint: Color = Color.WHITE, flip: bool = false, scale_f: float = 1.0) -> AnimatedSprite2D:
	var s := AnimatedSprite2D.new()
	var anim := ""
	match fx_name:
		"explosion":
			s.sprite_frames = Assets.frames("explosion", 32, 32, [["boom", 0, 8, 20, false]])
			anim = "boom"
		"slash":
			s.sprite_frames = Assets.frames("slash", 32, 32, [["slash", 0, 4, 26, false]])
			anim = "slash"
		"portal":
			s.sprite_frames = Assets.frames("portal", 24, 32, [["swirl", 0, 8, 10, true]])
			anim = "swirl"
		_:
			s.sprite_frames = Assets.frames("fx_small", 8, 8, [["sparkle", 0, 4, 16, false], ["hit", 1, 4, 20, false], ["muzzle", 2, 3, 24, false]])
			anim = fx_name if fx_name in ["sparkle", "hit", "muzzle"] else "sparkle"
	s.position = pos
	s.rotation = rot
	s.modulate = tint
	s.flip_v = flip
	s.scale = Vector2(scale_f, scale_f)
	fx_layer.add_child(s)
	s.play(anim)
	if anim != "swirl":
		s.animation_finished.connect(s.queue_free)
	return s


func floating_text(pos: Vector2, text: String, color: Color, is_damage: bool = false) -> void:
	if is_damage and not GameState.settings.damage_numbers:
		return
	texts.add(pos, text, color)


# ---------------------------------------------------------------------------
# Combat helpers
# ---------------------------------------------------------------------------
func cast_spell(id: String, pos: Vector2, dir: Vector2, faction: int, power: float, dmg_mult: float, speed_mult: float, mods: Dictionary = {}) -> void:
	var sp := Spells.get_spell(id)
	Audio.play_at(String(sp.get("sound", "shoot_spark")), pos, -5.0 if faction == 0 else -7.0)
	if sp.get("hitscan", false):
		_lightning(pos, dir.normalized(), faction, power, dmg_mult, sp)
		return
	var pr := Projectile.new()
	projectiles.add_child(pr)
	pr.setup(self, id, pos, dir, faction, power, dmg_mult, speed_mult, mods)


func throw_flask(w: Weapon, pos: Vector2, dir: Vector2) -> void:
	var pr := Projectile.new()
	projectiles.add_child(pr)
	pr.setup_flask(self, w, pos, dir)


func _hits(a: Actor, p: Vector2, r: float) -> bool:
	return p.x + r > a.bx and p.x - r < a.bx + a.hw * 2 and p.y + r > a.by and p.y - r < a.by + a.hh * 2


func find_actor_hit(p: Vector2, r: float, attacker_faction: int, exclude: Array) -> Actor:
	if attacker_faction != 0:
		if player and not player.dead and _hits(player, p, r) and not exclude.has(player):
			return player
		return null
	for e in enemies:
		if not is_instance_valid(e) or e.dead or exclude.has(e):
			continue
		if _hits(e, p, r):
			return e
	return null


## Actors hostile to `attacker_faction` within radius (or everyone if hit_all).
func actors_in_radius(p: Vector2, r: float, attacker_faction: int, hit_all: bool = false) -> Array[Actor]:
	var out: Array[Actor] = []
	if player and not player.dead and (hit_all or attacker_faction != 0):
		if player.center().distance_to(p) <= r + player.hw:
			out.append(player)
	if hit_all or attacker_faction != 1:
		for e in enemies:
			if is_instance_valid(e) and not e.dead and e.center().distance_to(p) <= r + e.hw:
				out.append(e)
	return out


func nearest_target(p: Vector2, attacker_faction: int, max_dist: float) -> Actor:
	if attacker_faction != 0:
		if player and not player.dead and player.center().distance_to(p) < max_dist:
			return player
		return null
	var best: Actor = null
	var bd := max_dist
	for e in enemies:
		if not is_instance_valid(e) or e.dead:
			continue
		var d := e.center().distance_to(p)
		if d < bd and world.line_clear(p, e.center()):
			bd = d
			best = e
	return best


func explosion(p: Vector2, r: int, power: float, fire: bool, damage: float, faction: int, source: String) -> void:
	world.explode(int(p.x), int(p.y), r, power, fire)
	for a in actors_in_radius(p, r + 6.0, faction, true):
		var d := a.center().distance_to(p)
		var f := clampf(1.0 - d / (r + 6.0), 0.25, 1.0)
		var dmg := damage * f
		if a == player and faction == 0:
			dmg *= 0.6
		a.take_damage(dmg, source, (a.center() - p).normalized() * (90.0 + power) * f + Vector2(0, -70.0 * f), "blast")
		if fire:
			a.ignite(2.0)
	var big := r > 14
	spawn_fx("explosion", p, randf() * TAU, Color.WHITE, false, 2.0 if r > 18 else 1.0)
	flash(p, r * 4.0 + 30.0, Color(1.0, 0.7, 0.35), 0.35)
	shake(2.0 + r * 0.22)
	Audio.play_at("explosion_big" if big else "explosion_small", p, 0.0)
	particles.burst(p, 10 + r, Color(1.0, 0.75, 0.3), 120.0 + r * 4.0, 0.5, 0.4)
	for k in 6 + r / 2:
		world.emit_gas(int(p.x) + randi_range(-r, r), int(p.y) + randi_range(-r, r), Mat.SMOKE, 30 + randi() % 40)


func sword_strike(owner: Player, origin: Vector2, dir: Vector2, w: Weapon, reach: float, damage: float, swing_dir: int) -> void:
	var ang := dir.angle()
	var half := deg_to_rad(w.arc * 0.5)
	var hit_any := false
	var col := w.main_color()
	for e in enemies:
		if not is_instance_valid(e) or e.dead:
			continue
		var to := e.center() - origin
		var d := to.length()
		if d <= reach + e.hw and absf(angle_difference(ang, to.angle())) <= half + 0.25:
			var dmg := damage * (1.25 if w.element == "void" else 1.0)
			e.take_damage(dmg, w.name, dir * 110.0 + Vector2(0, -50), "melee")
			match w.element:
				"fire":
					e.ignite(3.0)
				"ice":
					e.chilled = 2.5
				"acid":
					world.spawn_blob(int(e.center().x), int(e.center().y), 2, Mat.ACID)
			spawn_fx("hit", e.center(), 0.0, col)
			hit_any = true
	# Deflect hostile projectiles
	for pr in projectiles.get_children():
		var proj := pr as Projectile
		if proj == null or proj.dead or proj.faction != 1:
			continue
		var to2 := proj.position - origin
		if to2.length() <= reach + 4.0 and absf(angle_difference(ang, to2.angle())) <= half + 0.3:
			proj.faction = 0
			proj.vel = dir * proj.vel.length() * 1.3
			proj.dmg *= 1.5
			proj.hit_list.clear()
			spawn_fx("sparkle", proj.position, 0.0, Color(1, 1, 0.7))
			Audio.play_at("sword_hit", proj.position, -2.0, 1.5)
	# Cut soft terrain along the arc
	var cut := w.cut + (30 if w.element == "void" else 0)
	var removed := 0
	for k in 7:
		var a := ang + lerpf(-half, half, k / 6.0)
		for rr in [reach * 0.55, reach * 0.85]:
			var pt: Vector2 = origin + Vector2.from_angle(a) * rr
			removed += world.carve_circle(int(pt.x), int(pt.y), 3, cut, 0.12, true)
			match w.element:
				"fire":
					if randf() < 0.25:
						var fp := Vector2i(int(pt.x) + randi_range(-2, 2), int(pt.y) + randi_range(-2, 2))
						if Mat.FLAM[world.get_mat(fp.x, fp.y)] > 0:
							world.ignite(fp.x, fp.y)
						else:
							world.place_fire(fp.x, fp.y, 18)
				"ice":
					world.freeze(int(pt.x), int(pt.y), 3)
	if removed > 0:
		Audio.play_at("dig", origin, -6.0)
	if hit_any:
		Audio.play_at("sword_hit", origin, 0.0)
		shake(1.5)
	var tint := col if w.element != "" else Color(1, 1, 1, 0.9)
	spawn_fx("slash", origin + dir * 4.0, ang, tint, swing_dir < 0, maxf(1.0, round(reach / 22.0)))


func _lightning(from: Vector2, dir: Vector2, faction: int, power: float, dmg_mult: float, sp: Dictionary) -> void:
	var rng_len := float(sp.get("range", 200.0)) * (0.8 + power * 0.2)
	var dmg := float(sp.get("damage", 15.0)) * dmg_mult * power
	var p := from
	var hit: Actor = null
	for i in int(rng_len):
		var q := p + dir
		if world.is_solid_at(int(q.x), int(q.y)):
			break
		p = q
		hit = find_actor_hit(p, 2.0, faction, [])
		if hit:
			break
	_bolt(from, p)
	world.explode(int(p.x), int(p.y), int(sp.get("explode_r", 3)), float(sp.get("explode_power", 40.0)), false)
	particles.burst(p, 10, Color(0.8, 0.9, 1.0), 90.0, 0.3, 0.2)
	if hit:
		hit.take_damage(dmg, String(sp.get("name", "Salama")), dir * 60.0, "storm")
		var hits: Array = [hit]
		var last: Actor = hit
		for c in int(sp.get("chain", 0)):
			var nxt: Actor = null
			var bd := 80.0
			for e in enemies:
				if not is_instance_valid(e) or e.dead or hits.has(e):
					continue
				var d := e.center().distance_to(last.center())
				if d < bd and world.line_clear(last.center(), e.center()):
					bd = d
					nxt = e
			if nxt == null:
				break
			_bolt(last.center(), nxt.center())
			nxt.take_damage(dmg * 0.7, String(sp.get("name", "Salama")), Vector2.ZERO, "storm")
			hits.append(nxt)
			last = nxt


func _bolt(a: Vector2, b: Vector2) -> void:
	var glow := Line2D.new()
	var core := Line2D.new()
	var n := maxi(2, int(a.distance_to(b) / 7.0))
	var perp := (b - a).normalized().orthogonal()
	for i in n + 1:
		var t := float(i) / n
		var off := 0.0 if i == 0 or i == n else randf_range(-3.5, 3.5)
		var pt := a.lerp(b, t) + perp * off
		core.add_point(pt)
		glow.add_point(pt)
	core.width = 1.0
	core.default_color = Color(0.95, 0.97, 1.0)
	glow.width = 3.0
	glow.default_color = Color(0.55, 0.75, 1.0, 0.45)
	fx_layer.add_child(glow)
	fx_layer.add_child(core)
	flash(a.lerp(b, 0.5), a.distance_to(b) * 0.5 + 40.0, Color(0.6, 0.75, 1.0), 0.18)
	flash(b, 50.0, Color(0.7, 0.85, 1.0), 0.25)
	var tw := create_tween()
	tw.tween_property(core, "modulate:a", 0.0, 0.2)
	tw.parallel().tween_property(glow, "modulate:a", 0.0, 0.2)
	tw.tween_callback(core.queue_free)
	tw.tween_callback(glow.queue_free)


# ---------------------------------------------------------------------------
# Weapon pickups
# ---------------------------------------------------------------------------
func _find_nearby_pickup() -> void:
	nearby_pickup = null
	if player.dead:
		return
	var best := 18.0
	for c in entities.get_children():
		var pk := c as Pickup
		if pk == null or pk.kind != "weapon" or pk.collected:
			continue
		var d := pk.position.distance_to(player.position)
		if d < best:
			best = d
			nearby_pickup = pk


func _pick_weapon(pk: Pickup) -> void:
	var w := pk.weapon
	var empty := player.weapons.find(null)
	if empty >= 0:
		player.weapons[empty] = w
		player.slot = empty
	else:
		var old: Weapon = player.weapons[player.slot]
		player.weapons[player.slot] = w
		if old:
			var dp := spawn_weapon_pickup(old, player.position + Vector2(0, -4), false)
			dp.vel = Vector2(-player.facing * 40.0, -80.0)
			dp.age = -0.4
	player._refresh_weapon_sprite()
	pk.collected = true
	pk.queue_free()
	nearby_pickup = null
	Audio.play("pickup_item")
	hud.message("Poimit: %s" % w.name, Color("ffe08a"))
	spawn_fx("sparkle", player.position + Vector2(0, -6), 0.0, w.main_color())
