extends Node
## Dev tool: generates a level and saves a full-map PNG.
## Usage: godot --path . --scene res://tests/worldgen_test.tscn -- <dimension> <seed> <out.png> [level]

func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var dim_id := args[0] if args.size() > 0 else "caves"
	var seed_value := int(args[1]) if args.size() > 1 else 1234
	var out := args[2] if args.size() > 2 else "user://worldgen_preview.png"
	var lvl := int(args[3]) if args.size() > 3 else 2
	var vp := SubViewport.new()
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)
	var world := PixelWorld.new()
	vp.add_child(world)
	var d := Dimensions.get_def(dim_id)
	var t0 := Time.get_ticks_msec()
	var gen := WorldGen.new()
	var info := gen.generate(world, seed_value, lvl, d)
	var gen_ms := Time.get_ticks_msec() - t0
	world.set_background(d["bg_dark"], d["bg_light"], d["stars"])
	vp.size = Vector2i(world.W, world.H)
	# markers
	var marks := Node2D.new()
	vp.add_child(marks)
	_mark(marks, info["spawn"], Color.GREEN, 6)
	_mark(marks, info["portal"], Color.MAGENTA, 8)
	for e in info["enemies"]:
		_mark(marks, e[1], Color.RED, 3)
	for it in info["items"]:
		var col := Color.YELLOW if it[0] == "gold" else (Color.CYAN if it[0] == "weapon" else Color.PINK)
		_mark(marks, it[1], col, 3)
	# simulation timing
	var t1 := Time.get_ticks_usec()
	var steps := 120
	for i in steps:
		world.step()
	var sim_us := Time.get_ticks_usec() - t1
	var act := world.active_count
	# Diagnose what keeps chunks awake: diff one step
	var before := world.cells.duplicate()
	world.step()
	var tally := {}
	for i in range(0, before.size(), 2):
		if before[i] != world.cells[i]:
			var key := "%s>%s" % [Mat.NAMES[before[i]], Mat.NAMES[world.cells[i]]]
			tally[key] = tally.get(key, 0) + 1
	var keys := tally.keys()
	keys.sort_custom(func(a, b): return tally[a] > tally[b])
	for k in keys.slice(0, 12):
		print("  change ", k, " x", tally[k])
	world.upload()
	print("WORLDGEN dim=%s seed=%d size=%dx%d gen=%dms sim=%.2fms/step active_chunks=%d enemies=%d items=%d" % [dim_id, seed_value, world.W, world.H, gen_ms, sim_us / 1000.0 / steps, act, info["enemies"].size(), info["items"].size()])
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var img := vp.get_texture().get_image()
	img.save_png(out)
	print("saved ", out)
	get_tree().quit()


func _mark(parent: Node, p: Vector2, col: Color, s: int) -> void:
	var r := ColorRect.new()
	r.color = col
	r.size = Vector2(s, s)
	r.position = p - Vector2(s, s) * 0.5
	parent.add_child(r)
