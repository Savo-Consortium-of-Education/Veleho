extends Node
## Scripted play-test: runs a level with simulated input, prints timings and
## saves screenshots. Start with:
## godot --path . -- --autotest --shots <dir> [--dim caves] [--level 1] [--seconds 14]

var game: Game
var t := 0.0
var shots_dir := "user://"
var shot_times: Array = [1.0, 3.0, 5.0, 7.0, 9.0, 11.0, 13.0]

var next_shot := 0
var seconds := 14.0
var tag := "run"
var scenario := "basic"
var _did := false
var _perk_shot := false
var _phys_acc := 0.0
var _frames := 0
var _sec := 0.0


func _arg(args: PackedStringArray, key: String, def: String) -> String:
	var i := args.find(key)
	return args[i + 1] if i >= 0 and i + 1 < args.size() else def


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	shots_dir = _arg(args, "--shots", "user://")
	seconds = float(_arg(args, "--seconds", "14"))
	GameState.force_dim = _arg(args, "--dim", "")
	tag = GameState.force_dim if GameState.force_dim != "" else "run"
	scenario = _arg(args, "--scenario", "basic")
	if scenario != "basic":
		tag = scenario
	if scenario == "combat":
		shot_times = [1.0, 1.6, 2.4, 3.2, 4.4, 5.2, 6.0, 7.4, 8.2]
	if scenario == "boss":
		shot_times = [1.5, 3.0, 4.5, 6.0, 7.5, 9.0, 10.5, 12.0]
	if scenario == "items":
		shot_times = [2.0, 2.6, 3.6, 5.3, 6.0]
	if scenario == "spells":
		shot_times = [0.45, 1.15, 1.85, 2.55, 3.25, 3.95, 4.65, 5.35, 6.05, 6.75, 7.45, 8.15, 8.9, 9.6, 10.3, 11.0]
	if scenario == "resume":
		print("AUTOTEST resume load_run=", GameState.load_run(), " world_save=", GameState.has_world_save())
	else:
		GameState.new_run()
		GameState.run["level"] = int(_arg(args, "--level", "1"))
	game = Game.new()
	add_child(game)
	game.died.connect(_on_died)
	game.start()


func _physics_process(delta: float) -> void:
	if game == null:
		return
	if game.perk_ui and not _did:
		_did = true
		var ui := game.perk_ui as PerkChoice
		print("AUTOTEST perk ui shown")
		get_tree().create_timer(1.0).timeout.connect(func(): ui._pick(Perks.LIST.keys()[0]))
		return
	if game.paused_for_ui:
		return
	t += delta
	var p := game.player
	_release_all()
	if scenario == "portal" and t > 2.0 and not _did and game.portal:
		p.place_at(game.portal.position)
		return
	if scenario == "save":
		p.invuln = 1.0
		if t < 3.0:
			p.debug_aim = Vector2(1, 0.5)
			Input.action_press("move_right")
			Input.action_press("fire")
		elif not _did:
			_did = true
			var ok := game.save_world()
			print("AUTOTEST saved=", ok, " pos=", p.position, " hp=", p.hp, " enemies=", game.enemies.size(), " size=", FileAccess.get_file_as_bytes(GameState.WORLD_PATH).size())
			_shot("save_before")
			get_tree().create_timer(0.5).timeout.connect(func(): get_tree().quit())
		return
	if scenario == "resume":
		if not _did:
			_did = true
			print("AUTOTEST resumed pos=", p.position, " hp=", p.hp, " enemies=", game.enemies.size(), " world_save_left=", GameState.has_world_save())
			_shot("resume_after")
		if t > 1.0:
			GameState.delete_save()
			get_tree().quit()
		return
	if scenario == "boss":
		_boss_test(p)
		if t >= seconds:
			print("AUTOTEST done tag=%s hp=%.1f kills=%d boss=%s sealed=%s" % [tag, p.hp, int(GameState.run["stats"]["kills"]), str(game.boss), str(game.portal.sealed if game.portal else "-")])
			GameState.delete_save()
			get_tree().quit()
		return
	if scenario == "items":
		_items(p)
		if t >= seconds:
			print("AUTOTEST done tag=%s hp=%.1f bag=%s" % [tag, p.hp, str(p.spell_bag.slice(0, 4))])
			GameState.delete_save()
			get_tree().quit()
		return
	if scenario == "spells":
		_spells(p)
		if t >= seconds:
			print("AUTOTEST done tag=%s hp=%.1f kills=%d" % [tag, p.hp, int(GameState.run["stats"]["kills"])])
			GameState.delete_save()
			get_tree().quit()
		return
	if scenario == "combat":
		_combat(p)
		if t >= seconds:
			print("AUTOTEST done tag=%s hp=%.1f kills=%d" % [tag, p.hp, int(GameState.run["stats"]["kills"])])
			GameState.delete_save()
			get_tree().quit()
		return
	if scenario == "death" and t > 3.0 and not p.dead:
		p.invuln = 0.0
		p.take_damage(9999.0, "Testi", Vector2.ZERO, "melee")
		return
	if t < 1.0:
		pass
	elif t < 3.0:
		Input.action_press("move_right")
		p.debug_aim = Vector2(1, 0.3)
		Input.action_press("fire")
	elif t < 3.3:
		Input.action_press("jump")
	elif t < 5.0:
		Input.action_press("jump")
		Input.action_press("move_left")
		p.debug_aim = Vector2(-1, 0.6)
		Input.action_press("fire")
	elif t < 7.0:
		p.select_slot(1)
		p.debug_aim = Vector2(0.4, 1)
		if fmod(t, 1.6) < 1.2:
			Input.action_press("fire")
	elif t < 9.0:
		p.select_slot(2)
		p.debug_aim = Vector2(1, 0.2) if fmod(t, 1.0) < 0.5 else Vector2(-1, 0.2)
		Input.action_press("fire")
		Input.action_press("move_right" if fmod(t, 2.0) < 1.0 else "move_left")
	elif t < 12.0:
		p.select_slot(0)
		p.debug_aim = Vector2(1, -0.5).rotated(sin(t * 2.0))
		Input.action_press("fire")
	if t >= seconds:
		print("AUTOTEST done tag=%s hp=%.1f pos=%s kills=%d" % [tag, p.hp, str(p.position), int(GameState.run["stats"]["kills"])])
		GameState.delete_save()
		get_tree().quit()


func _make(type: int, spell: String, element: String = "") -> Weapon:
	var w := WeaponGen.generate(randi(), 3, type)
	if spell != "":
		w.spells.clear()
		w.spells.append(spell)
	w.element = element
	w.name = "Testi " + spell + element
	return w


func _combat(p: Player) -> void:
	if not _did:
		_did = true
		p.weapons = [_make(Weapon.WAND, "lightning"), _make(Weapon.STAFF, "bomb"), _make(Weapon.SWORD, "", "fire"), _make(Weapon.STAFF, "meteor")]
		p.mana_max = 999.0
		p.mana = 999.0
		p.hp = 9999.0
		p.max_hp = 9999.0
		p.slot = 0
		p._refresh_weapon_sprite()
		var c := p.position
		game.world.carve_circle(int(c.x) + 40, int(c.y) - 10, 34, 200)
		for y in range(int(c.y) + 7, int(c.y) + 12):
			for x in range(int(c.x) - 20, int(c.x) + 90):
				if game.world.get_mat(x, y) == Mat.EMPTY:
					game.world.set_cell(x, y, Mat.ROCK)
		game.spawn_enemy("slime", c + Vector2(30, 0))
		game.spawn_enemy("bat", c + Vector2(35, -25))
		game.spawn_enemy("caster", c + Vector2(55, -2))
		game.spawn_enemy("golem", c + Vector2(70, -6))
	p.mana = 999.0
	if t < 2.0:
		p.debug_aim = Vector2(1, 0.05)
		Input.action_press("fire")
	elif t < 4.0:
		p.select_slot(1)
		p.debug_aim = Vector2(1, -0.4)
		if fmod(t, 1.0) < 0.6:
			Input.action_press("fire")
	elif t < 6.5:
		p.select_slot(2)
		p.debug_aim = Vector2(1, 0.1)
		Input.action_press("fire")
		Input.action_press("move_right")
	elif t < 9.0:
		p.select_slot(3)
		p.debug_aim = Vector2(1, 0.5)
		if fmod(t, 1.25) < 1.0:
			Input.action_press("fire")


var _step := 0


func _boss_test(p: Player) -> void:
	p.max_hp = 9999.0
	p.hp = 9999.0
	p.mana = 999.0
	if _step == 0:
		_step = 1
		var b := game.boss
		print("AUTOTEST boss present=", b != null, " hp=", b.max_hp if b else 0.0)
		if b:
			p.place_at(Vector2(b.arena.position.x + 40, b.arena.end.y - 8))
			var w := _make(Weapon.WAND, "lightning")
			w.cast_delay = 0.05
			w.recharge = 0.05
			w.dmg_mult = 3.0
			p.weapons[0] = w
			p.slot = 0
			p._refresh_weapon_sprite()
		return
	var b2 := game.boss
	if b2 and is_instance_valid(b2):
		p.debug_aim = (b2.center() - p.arm_pivot.global_position).normalized()
		if t > 2.5:
			Input.action_press("fire")
		if int(t * 2.0) != int((t - get_physics_process_delta_time()) * 2.0):
			print("AUTOTEST boss t=%.1f hp=%.0f phase=%d action=%s awake=%s" % [t, b2.hp, b2.phase, b2.action, str(b2.awake)])


func _items(p: Player) -> void:
	p.invuln = 1.0
	if _step == 0 and t > 0.5:
		_step = 1
		p.spell_bag[2] = "multi3"
		p.spell_bag[3] = "explosive"
		game.open_inventory()
		var inv := game.inventory_ui as InventoryMenu
		# simulate drags: bag[2] -> wand slot 2, bag[0] -> wand slot 1
		var wand_slots: Array = []
		var bag_slots: Array = []
		for sl in inv._slots:
			if sl.kind == "spell" and sl.arr == p.weapons[0].spells:
				wand_slots.append(sl)
			elif sl.kind == "spell" and sl.arr == p.spell_bag:
				bag_slots.append(sl)
		inv.swap(bag_slots[2], wand_slots[0])
		inv.swap(bag_slots[0], wand_slots[2])
		inv._set_hover(wand_slots[0])
		print("AUTOTEST wand spells after edit: ", p.weapons[0].spells)
		get_tree().create_timer(0.8).timeout.connect(func(): _shot_then_close(inv))
		return
	if _step == 1 and t > 1.5:
		_step = 2
	if _step == 2:
		p.select_slot(0)
		p.debug_aim = Vector2(1, -0.2)
		if t < 3.0:
			Input.action_press("fire")
		elif t < 3.1:
			p.select_slot(3)
		elif t < 4.0:
			p.select_slot(3)
			p.debug_aim = Vector2(1, 0.4)
			Input.action_press("fire")
		elif t < 4.1:
			_step = 3
			Input.action_press("drink")
	if _step == 3 and t > 4.6:
		_step = 4
		print("AUTOTEST flask after pour+drink: ", p.weapons[3].liquid_name(), " ", p.weapons[3].amount)
		p.select_slot(3)
		p.debug_aim = Vector2(1, -0.6)
		Input.action_press("alt_fire")
	if _step == 4 and t > 5.0:
		_step = 5
		print("AUTOTEST flask slot after throw: ", p.weapons[3])


const ALL_SPELLS := ["spark", "fireball", "orb", "ice", "acid", "bomb", "missile", "meteor", "drill", "water", "quake", "lightning"]
var _spell_i := -1


func _spells(p: Player) -> void:
	p.mana = 999.0
	p.hp = p.max_hp
	p.invuln = 1.0
	var idx := int(t / 0.7)
	if idx < ALL_SPELLS.size():
		if idx != _spell_i:
			_spell_i = idx
			var staff := idx % 2 == 1
			p.weapons[0] = _make(Weapon.STAFF if staff else Weapon.WAND, ALL_SPELLS[idx])
			p.slot = 0
			p._refresh_weapon_sprite()
			print("AUTOTEST spell ", ALL_SPELLS[idx])
		p.debug_aim = Vector2(1, 0.3).rotated(idx * 0.9)
		if fmod(t, 0.7) < 0.5:
			Input.action_press("fire")
	else:
		var el: String = ["", "fire", "ice", "acid", "void"][(idx - ALL_SPELLS.size()) % 5]
		if idx != _spell_i:
			_spell_i = idx
			p.weapons[2] = _make(Weapon.SWORD, "", el)
			p.slot = 2
			p._refresh_weapon_sprite()
			print("AUTOTEST sword ", el)
			# weapon pickup swap with a full inventory
			p.weapons[3] = _make(Weapon.WAND, "spark")
			var pk := game.spawn_weapon_pickup(_make(Weapon.WAND, "orb"), p.position, true)
			game._pick_weapon(pk)
		p.debug_aim = Vector2(1, 0).rotated(idx * 1.3)
		Input.action_press("fire")


func _on_died(info: Dictionary) -> void:
	print("AUTOTEST died: ", info)
	var d := DeathScreen.new()
	add_child(d)
	d.setup(info)
	await get_tree().create_timer(0.5).timeout
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(shots_dir.path_join("death_screen.png"))


func _release_all() -> void:
	for a in ["move_left", "move_right", "jump", "fire", "interact"]:
		Input.action_release(a)


func _process(delta: float) -> void:
	if game == null or not is_instance_valid(game):
		return
	if game.paused_for_ui:
		if game.perk_ui and not _perk_shot:
			_perk_shot = true
			_shot("%s_perk" % tag)
		return
	_frames += 1
	_sec += delta
	_phys_acc += Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)
	if _sec >= 1.0:
		print("AUTOTEST t=%.1f fps=%d phys_ms=%.2f chunks=%d particles=%d enemies=%d proj=%d" % [t, Engine.get_frames_per_second(), _phys_acc / _frames * 1000.0, game.world.active_count, game.particles.count, game.enemies.size(), game.projectiles.get_child_count()])
		_sec = 0.0
		_frames = 0
		_phys_acc = 0.0
	if next_shot < shot_times.size() and t >= float(shot_times[next_shot]):
		next_shot += 1
		_shot("%s_%02d" % [tag, next_shot])


func _shot_then_close(inv: InventoryMenu) -> void:
	await _shot("items_inventory")
	inv._close()


func _shot(name: String) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var path := shots_dir.path_join(name + ".png")
	var err := img.save_png(path)
	print("AUTOTEST shot ", path, " err=", err, " size=", img.get_size())
	if err != OK:
		print("AUTOTEST shot failed ", name, " err=", err)
